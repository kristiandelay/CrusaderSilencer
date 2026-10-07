"""Two-player listen-server PIE; send requests through the real input tick."""
import json
import time
import traceback
from pathlib import Path
import unreal as u

net_physical={'phase':'position','next':0,'index':0,'results':[],'deadline':time.monotonic()+160,'busy':False}
net_physical_out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/PhysicalTests/network-physical.json'

def np_input(pawn,name,value):
    pc=pawn.get_controller()
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pc)
    sub.inject_input_vector_for_action(u.load_asset('/Game/Baseline/Input/IA_'+name),u.Vector(value,0,0),[],[])

def np_context():
    pawns=[p for w in u.EditorLevelLibrary.get_pie_worlds(False) for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if 'TrainingPartner' not in p.get_class().get_name() and not p.crowd_agent.enabled]
    host=next(p for p in pawns if p.has_authority() and p.is_locally_controlled())
    server_client=next(p for p in pawns if p.has_authority() and not p.is_locally_controlled())
    client=next(p for p in pawns if not p.has_authority() and p.is_locally_controlled())
    observer=next(p for p in pawns if not p.has_authority() and not p.is_locally_controlled())
    return host,server_client,client,observer

def np_finish(error=None):
    u.unregister_slate_post_tick_callback(net_physical['handle'])
    net_physical['finished']=True
    net_physical_out.write_text(json.dumps({'passed':error is None,'error':error,'results':net_physical['results'],'observed':net_physical.get('observed')},indent=2))
    print('NETWORK_PHYSICAL_COMPLETE',error)

def np_tick(dt):
    if net_physical['busy']:return
    net_physical['busy']=True
    try:
        assert time.monotonic()<net_physical['deadline'],'Network physical timeout'
        try:host,server_client,client,observer=np_context()
        except StopIteration:return
        if not all(p.physical_interaction.controls_created for p in [host,server_client,client,observer]):return
        now=time.monotonic()
        # Capture every rendered tick, including ticks between phase polls, so
        # replication cannot hide a one-frame jump out of the physical pose.
        if net_physical['phase']=='observe':
            for i,p in enumerate([host,server_client,client,observer]):
                phase=str(p.physical_interaction.get_phase())
                game_time=u.GameplayStatics.get_time_seconds(p)
                pose={bone:p.mesh.get_socket_location(bone) for bone in ['pelvis','head','foot_l','foot_r']}
                visible={bone:p.baseline_equipment.get_presentation_mesh().get_socket_location(bone) for bone in pose}
                previous=net_physical.setdefault('previous_poses',{}).get(i)
                if previous and 'RAGDOLL' in previous[0] and 'RECOVERY' in phase:
                    jump=max((pose[b]-previous[1][b]).length() for b in pose)
                    visible_jump=max((visible[b]-previous[2][b]).length() for b in visible)
                    weight=p.mesh.get_anim_instance().recovery_pose_weight
                    elapsed=game_time-previous[3]
                    alpha=max(0,min(1,elapsed/.45))
                    minimum_weight=1-alpha*alpha*(3-2*alpha)
                    net_physical.setdefault('getup_jumps',[]).append({'role_index':i,'jump_cm':jump,'visible_jump_cm':visible_jump,'initial_snapshot_weight':weight,'game_elapsed':elapsed,'minimum_snapshot_weight':minimum_weight})
                    assert weight+.001>=minimum_weight,'Network animation updates advanced recovery faster than elapsed game time: '+str(weight)
                    assert jump<45,'Replicated get-up popped: '+str(jump)
                    assert visible_jump<45,'Visible replicated get-up popped: '+str(visible_jump)
                net_physical['previous_poses'][i]=(phase,pose,visible,game_time)
        if net_physical.pop('release',False):
            for p in [host,client]:
                for name in ['Shove','Tackle','Takedown','Ragdoll']:np_input(p,name,0)
        if now<net_physical['next']:return
        index=net_physical['index']
        owner=client if index!=1 else host
        server_owner=server_client if index!=1 else host
        server_target=host if index!=1 else server_client
        if net_physical['phase']=='position':
            for p in [host,server_client]:
                assert not p.physical_interaction.is_busy(),'Participants not released'
                p.character_movement.stop_movement_immediately()
            server_owner.set_actor_location(u.Vector(1500,-3200,94),False,True)
            server_owner.set_actor_rotation(u.Rotator(yaw=0),False)
            server_target.set_actor_location(u.Vector(1650,-3200,94),False,True)
            server_target.set_actor_rotation(u.Rotator(yaw=180),False)
            owner.get_controller().set_control_rotation(u.Rotator(yaw=0))
            (host if owner==client else client).get_controller().set_control_rotation(u.Rotator(yaw=180))
            host.force_net_update();server_client.force_net_update()
            net_physical.update(phase='trigger',next=now+1.5)
        elif net_physical['phase']=='trigger':
            action=['Shove','Tackle','Takedown'][index]
            np_input(owner,action,1)
            net_physical.update(phase='observe',next=now+.2,started=now,action=action,release=True,observed={str(i):[] for i in range(4)},max_pelvis_error=0.,previous_poses={},getup_jumps=[])
        else:
            elapsed=now-net_physical['started']
            pawns=[host,server_client,client,observer]
            for i,p in enumerate(pawns):
                phase=str(p.physical_interaction.get_phase())
                if phase not in net_physical['observed'][str(i)]:net_physical['observed'][str(i)].append(phase)
                if 'RAGDOLL' in phase:
                    assert p.mesh.is_simulating_physics('pelvis'),'Replicated ragdoll is not simulated'
                    assert not any(p.physics_control.get_control_enabled(name) for name in p.physics_control.get_all_control_names()),'Replicated ragdoll has active pose motors'
            for server,remote in [(host,observer),(server_client,client)]:
                if 'RAGDOLL' in str(server.physical_interaction.get_phase()) and 'RAGDOLL' in str(remote.physical_interaction.get_phase()):
                    error=(server.mesh.get_socket_location('pelvis')-remote.mesh.get_socket_location('pelvis')).length()
                    net_physical['max_pelvis_error']=max(error,net_physical['max_pelvis_error'])
            if elapsed>4:
                for p in [host,client]:
                    if 'RAGDOLL' in str(p.physical_interaction.get_phase()):np_input(p,'Ragdoll',1);net_physical['release']=True
            if elapsed>2 and not any(p.physical_interaction.is_busy() for p in pawns):
                assert all(any('INTERACTION' in phase for phase in phases) for phases in net_physical['observed'].values()),str(net_physical['observed'])
                target_indices=[0,3] if owner==client else [1,2]
                if index==1:target_indices=list(range(4))
                for i in target_indices:
                    phases=net_physical['observed'][str(i)]
                    assert any('RAGDOLL' in phase for phase in phases) and any('RECOVERY' in phase for phase in phases),str(net_physical['observed'])
                assert net_physical['max_pelvis_error']<160,net_physical['max_pelvis_error']
                assert len(net_physical['getup_jumps'])>=len(target_indices),'Missing replicated get-up transition samples'
                net_physical['results'].append({'initiator':'client' if owner==client else 'host','action':net_physical['action'],'all_roles_observed':net_physical['observed'],'max_pelvis_error_cm':net_physical['max_pelvis_error'],'getup_transition_jumps':net_physical['getup_jumps']})
                net_physical['index']+=1
                if net_physical['index']==3:np_finish()
                else:net_physical.update(phase='position',next=now+1)
            else:
                assert elapsed<25,'Action did not complete: '+str(net_physical['observed'])
                net_physical['next']=now+.08
    except Exception:np_finish(traceback.format_exc())
    finally:net_physical['busy']=False

net_physical['handle']=u.register_slate_post_tick_callback(np_tick)
print('Started network physical interaction checks')
