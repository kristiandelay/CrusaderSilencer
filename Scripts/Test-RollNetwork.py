"""Use the real Enhanced Input action on both players; inspect all four network views."""
import json, math, time, traceback
from pathlib import Path
import unreal as u

rn_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
rn_test=dict(phase='setup',index=0,next=0,busy=False,results=[],deadline=time.monotonic()+200)

def rn_context():
    pawns=[p for w in u.EditorLevelLibrary.get_pie_worlds(False) for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter)
           if 'TrainingPartner' not in p.get_class().get_name() and not p.crowd_agent.enabled]
    return [next(p for p in pawns if p.has_authority() and p.is_locally_controlled()),
            next(p for p in pawns if p.has_authority() and not p.is_locally_controlled()),
            next(p for p in pawns if not p.has_authority() and p.is_locally_controlled()),
            next(p for p in pawns if not p.has_authority() and not p.is_locally_controlled())]

def rn_input(p,name,value):
    path='/Game/Input/IA_'+name if name in ['Aim','Move'] else '/Game/Baseline/Input/IA_Roll'
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
             if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==p.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(path),u.Vector(*value) if isinstance(value,tuple) else u.Vector(value,0,0),[],[])

def rn_finish(error=None):
    u.unregister_slate_post_tick_callback(rn_test['handle']);rn_test.update(finished=True,error=error)
    (rn_root/'Artifacts/Roll/network.json').write_text(json.dumps(dict(passed=error is None,error=error,results=rn_test['results']),indent=2)+'\n')
    print('ROLL_NETWORK',error)

def rn_tick(dt):
    if rn_test['busy']:return
    rn_test['busy']=True
    try:
        assert time.monotonic()<rn_test['deadline'],'Network roll test timed out'
        try:roles=rn_context()
        except StopIteration:return
        host,server,client,observer=roles
        if not all(p.physical_interaction.controls_created for p in roles):return
        now=u.GameplayStatics.get_time_seconds(host);phase=rn_test['phase'];index=rn_test['index']
        if rn_test.pop('release',False):
            for p in [host,client]:rn_input(p,'Roll',0);rn_input(p,'Move',0)
        if phase not in ['setup','equip']:
            for p in [host,client]:
                p.get_controller().set_control_rotation(u.Rotator());rn_input(p,'Aim',1)
        if phase=='settle':
            for p,d in [(host,(index+4)%8),(client,index)]:
                rn_input(p,'Move',(math.sin(math.radians(d*45)),math.cos(math.radians(d*45)),0))
        if phase=='observe':
            for n,p in enumerate(roles):
                if p.roll.is_rolling():
                    rn_test['seen'][n]=True
                    expected=index if n in [1,2] else (index+4)%8
                    assert p.roll.active_direction==expected,('Direction',index,n,p.roll.active_direction)
                    weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
                    rn_test['visible'][n]|=weapon is not None and all(not a.get_editor_property('bHidden') for a in weapon.get_spawned_actors())
        if now<rn_test['next']:return
        if phase=='setup':
            for p,kind in [(host,'Pistol'),(server,'Rifle')]:
                pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(p.get_world(),u.BaselineWeaponPickup) if kind in a.item_definition.get_name())
                pos=pickup.get_actor_location();p.set_actor_location(pos+u.Vector(-110,0,94-pos.z),False,True)
                p.baseline_equipment.server_pickup(pickup)
            rn_test.update(phase='equip',next=now+2)
        elif phase=='equip':
            assert all(p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance) for p in roles),'Equipment replication'
            rn_test.update(phase='place',next=now+.1)
        elif phase=='place':
            for p,y in [(host,2000),(server,3200)]:
                p.character_movement.stop_movement_immediately();p.un_crouch()
                p.set_actor_location(u.Vector(5000,y,94),False,True);p.set_actor_rotation(u.Rotator(),False);p.force_net_update()
            rn_test.update(phase='settle',next=now+1.2)
        elif phase=='settle':
            for p in [host,client]:
                p.character_movement.stop_movement_immediately();p.set_actor_rotation(u.Rotator(),False)
            rn_test.update(before=[p.roll.rolls_started for p in roles],start=[p.get_actor_location() for p in roles],seen=[False]*4,visible=[False]*4)
            for p in [host,client]:rn_input(p,'Roll',1)
            rn_test.update(phase='observe',next=now+1.4,release=True)
        elif phase=='observe':
            assert all(rn_test['seen']),('Missing montage',index,rn_test['seen'])
            assert all(rn_test['visible']),('Weapon hidden during roll',index,rn_test['visible'])
            counts=[p.roll.rolls_started-rn_test['before'][n] for n,p in enumerate(roles)]
            assert counts==[1]*4,('Montage restarted',index,counts)
            distances=[]
            for n,p in enumerate(roles):
                delta=p.get_actor_location()-rn_test['start'][n];distance=math.hypot(delta.x,delta.y)
                expected=index if n in [1,2] else (index+4)%8
                dot=(delta.x*math.cos(math.radians(expected*45))+delta.y*math.sin(math.radians(expected*45)))/max(distance,1)
                assert 280<distance<620 and dot>.87,('Movement',index,n,distance,dot)
                assert not p.roll.is_rolling() and p.can_use_movement_actions(),('Locked',index,n)
                weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
                assert all(not a.get_editor_property('bHidden') for a in weapon.get_spawned_actors()),('Weapon did not return',index,n)
                distances.append(distance)
            errors=[(host.get_actor_location()-observer.get_actor_location()).length(),(server.get_actor_location()-client.get_actor_location()).length()]
            assert max(errors)<35,('Position disagreement',index,errors)
            rn_test['results'].append(dict(client_direction=index,host_direction=(index+4)%8,roll_counts=counts,distance_cm=distances,replication_error_cm=errors,weapon_visible_all=True))
            rn_test['index']+=1
            if rn_test['index']==8:
                for p in [host,client]:rn_input(p,'Aim',0)
                rn_finish();return
            rn_test.update(phase='place',next=now+.4)
    except Exception:rn_finish(traceback.format_exc())
    finally:rn_test['busy']=False
rn_test['handle']=u.register_slate_post_tick_callback(rn_tick)
print('ROLL_NETWORK_STARTED')
