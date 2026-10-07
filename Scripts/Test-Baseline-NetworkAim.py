"""Two-player listen-server PIE: an observer sees the same pitch/yaw weapon aim."""
import math
net_aim={'phase':'equip','next':0,'results':[],'busy':False,'deadline':time.monotonic()+120,'role':'host'}

def net_aim_input(pawn,value,name='Aim'):
    pc=pawn.get_controller()
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
             if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pc)
    path='/Game/Baseline/Input/IA_Interact' if name=='Interact' else '/Game/Input/IA_Aim'
    sub.inject_input_vector_for_action(u.load_asset(path),u.Vector(value,0,0),[],[])

def net_aim_context():
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    pawns=[p for w in worlds for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if 'TrainingPartner' not in p.get_class().get_name() and not p.crowd_agent.enabled]
    host=next(p for p in pawns if p.has_authority() and p.is_locally_controlled())
    client=next(p for p in pawns if not p.has_authority() and p.is_locally_controlled())
    observer=next(p for p in pawns if not p.has_authority() and not p.is_locally_controlled())
    server_client=next(p for p in pawns if p.has_authority() and not p.is_locally_controlled())
    world=next(w for w in worlds if observer in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter))
    return world,host,client,observer,server_client

def net_aim_finish(error=None):
    u.unregister_slate_post_tick_callback(net_aim['handle'])
    net_aim['finished']=True
    try:
        _,host,client,_,_=net_aim_context()
        net_aim_input(host,0);net_aim_input(client,0)
    except Exception:pass
    output=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/AimTests/network-aim.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'passed':error is None,'error':error,'results':net_aim['results']},indent=2))

def net_aim_tick(dt):
    if net_aim['busy']:return
    net_aim['busy']=True
    try:
        assert time.monotonic()<net_aim['deadline'],'Network aim test timed out'
        try:world,host,client,observer,server_client=net_aim_context()
        except StopIteration:return  # PIE clients can finish spawning after the script starts.
        owner=host if net_aim['role']=='host' else client
        remote=observer if net_aim['role']=='host' else server_client
        net_aim_input(owner,1 if net_aim['phase'] in ['rotate','verify'] else 0)
        now=u.GameplayStatics.get_time_seconds(world)
        if now<net_aim['next']:return
        if net_aim['phase']=='equip':
            server_client.set_actor_location(u.Vector(1700,-1400,94),False,True)
            client.get_controller().set_control_rotation(u.Rotator(pitch=0,yaw=37,roll=0))
            host.get_controller().set_control_rotation(u.Rotator(pitch=0,yaw=0,roll=0))
            net_aim_input(host,1,'Interact')
            net_aim.update(phase='rotate',next=now+2,index=0)
        elif net_aim['phase']=='rotate':
            pitch,yaw=[(40,60),(-40,-60)][net_aim['index']]
            owner.get_controller().set_control_rotation(u.Rotator(pitch=pitch,yaw=yaw,roll=0))
            net_aim.update(phase='verify',next=now+1.5,pitch=pitch,yaw=yaw)
        elif net_aim['phase']=='verify':
            equipment=remote.get_component_by_class(u.BaselineEquipmentComponent)
            assert equipment.is_weapon_ready(),'Ready stance was not replicated'
            replicated=equipment.get_weapon_aim_rotation()
            pitch=(replicated.pitch+180)%360-180
            yaw=(replicated.yaw+180)%360-180
            assert abs(pitch-net_aim['pitch'])<1 and abs(yaw-net_aim['yaw'])<1,str(replicated)
            anim=equipment.get_presentation_mesh().get_anim_instance()
            assert abs(anim.aim_pitch-net_aim['pitch'])<1,str(anim.aim_pitch)
            weapon=remote.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
            assert weapon and not weapon.get_spawned_actors()[0].get_editor_property('bHidden')
            rotation=weapon.get_spawned_actors()[0].get_component_by_class(u.SkeletalMeshComponent).get_socket_rotation('Muzzle')
            def direction(r):
                p,y=math.radians(r.pitch),math.radians(r.yaw)
                return (math.cos(p)*math.cos(y),math.cos(p)*math.sin(y),math.sin(p))
            dot=sum(a*b for a,b in zip(direction(rotation),direction(replicated)))
            error=math.degrees(math.acos(max(-1,min(1,dot))))
            assert error<18, f'Observer muzzle error {error}'
            net_aim['results'].append({'owner':net_aim['role'],'pitch':pitch,'yaw':yaw,'observer_muzzle_error_degrees':error})
            net_aim['index']+=1
            if net_aim['index']==2:net_aim.update(phase='release',next=now+1.2)
            else:net_aim.update(phase='rotate',next=now+.1)
        elif net_aim['phase']=='release':
            equipment=remote.get_component_by_class(u.BaselineEquipmentComponent)
            assert not equipment.is_weapon_ready(),'Aim release was not replicated'
            assert equipment.get_presentation_mesh().get_anim_instance().weapon_ready_weight<.02
            net_aim['results'].append({'owner':net_aim['role'],'case':'replicated_lowered_carry'})
            if net_aim['role']=='client':net_aim_finish()
            else:
                server_world=next(w for w in u.EditorLevelLibrary.get_pie_worlds(False)
                                  if server_client in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter))
                pickup=next(p for p in u.GameplayStatics.get_all_actors_of_class(server_world,u.BaselineWeaponPickup) if p.item_definition.get_name()=='ID_Pistol_C')
                location=pickup.get_actor_location()
                server_client.set_actor_location(u.Vector(location.x-100,location.y,94),False,True)
                client.get_controller().set_control_rotation(u.Rotator(pitch=0,yaw=0,roll=0))
                net_aim.update(phase='client_equip',role='client',next=now+1)
        elif net_aim['phase']=='client_equip':
            # Input runs inside the client's world tick. Calling RPC wrappers
            # directly from an editor Slate callback has the wrong PIE context.
            net_aim_input(client,1,'Interact')
            net_aim.update(phase='rotate',next=now+2,index=0)
    except Exception:net_aim_finish(traceback.format_exc())
    finally:net_aim['busy']=False

net_aim['handle']=u.register_slate_post_tick_callback(net_aim_tick)
print('Started observer aim replication checks')
