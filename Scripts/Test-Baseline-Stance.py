"""Fresh single-player PIE: relaxed carry, fire stance and animated foot turns."""
import math
stance_out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/StanceTests'
stance_out.mkdir(parents=True,exist_ok=True)
stance={'phase':'equip','next':0,'results':[],'busy':False,'deadline':time.monotonic()+180}

def stance_context():
    world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
    pawn=u.GameplayStatics.get_player_pawn(world,0)
    pc=pawn.get_controller()
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
             if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pc)
    equipment=pawn.get_component_by_class(u.BaselineEquipmentComponent)
    return world,pawn,pc,sub,equipment

def stance_input(sub,name,value):
    path='/Game/Input/Actions/IA_Weapon_Fire_Auto' if name=='Fire' else '/Game/Input/IA_'+name
    sub.inject_input_vector_for_action(u.load_asset(path),u.Vector(value,0,0),[],[])

def stance_delta(a,b):return (a-b+180)%360-180

def stance_muzzle(pawn):
    weapon=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
    return weapon.get_spawned_actors()[0].get_component_by_class(u.SkeletalMeshComponent).get_socket_rotation('Muzzle')

def stance_error(a,b):
    def direction(r):
        p,y=math.radians(r.pitch),math.radians(r.yaw)
        return (math.cos(p)*math.cos(y),math.cos(p)*math.sin(y),math.sin(p))
    return math.degrees(math.acos(max(-1,min(1,sum(x*y for x,y in zip(direction(a),direction(b)))))))

def stance_finish(error=None):
    u.unregister_slate_post_tick_callback(stance['handle'])
    stance['finished']=True
    try:
        _,pawn,_,sub,_=stance_context()
        for name in ['Aim','Fire']:stance_input(sub,name,0)
        pawn.un_crouch()
    except Exception:pass
    stance.pop('capture',None)
    (stance_out/'stance.json').write_text(json.dumps({'passed':error is None,'error':error,'results':stance['results']},indent=2))

def stance_tick(dt):
    if stance['busy']:return
    stance['busy']=True
    try:
        assert time.monotonic()<stance['deadline'],'Stance test timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds or not u.GameplayStatics.get_player_pawn(worlds[0],0):return
        world,pawn,pc,sub,equipment=stance_context()
        now=u.GameplayStatics.get_time_seconds(world)
        phase=stance['phase']
        stance_input(sub,'Aim',1 if phase in ['turn_start','turn_measure'] else 0)
        stance_input(sub,'Fire',1 if phase=='fire_measure' else 0)
        if now<stance['next']:return
        anim=equipment.get_presentation_mesh().get_anim_instance()
        if phase=='equip':
            if not equipment.get_active_item():equipment.interact()
            stance.update(phase='relaxed',next=now+2)
        elif phase in ['relaxed','relaxed_look']:
            muzzle=stance_muzzle(pawn)
            assert not equipment.is_weapon_ready()
            assert anim.weapon_ready_weight<.02
            assert anim.weapon_upper_body_weight<.02,'Relaxed carry still locks the upper body'
            assert abs(anim.aim_pitch)<.1,'Relaxed carry is still a downward aim offset'
            assert muzzle.pitch<-35,str(muzzle)
            stance['results'].append({'case':phase,'muzzle_pitch':muzzle.pitch,'ready_weight':anim.weapon_ready_weight})
            if phase=='relaxed':
                pc.set_control_rotation(u.Rotator(pitch=45,yaw=120,roll=0))
                stance.update(phase='relaxed_look',next=now+1)
            else:
                stance['capture']=u.AutomationLibrary.take_high_res_screenshot(1440,900,str(stance_out/'relaxed-carry.png'),delay=0.0)
                stance.update(phase='fire_measure',next=now+1)
        elif phase=='fire_measure':
            assert equipment.is_weapon_ready()
            error=stance_error(stance_muzzle(pawn),pc.get_control_rotation())
            assert error<18,f'Fire-only muzzle error {error}'
            stance['results'].append({'case':'fire_without_aim','muzzle_error':error})
            stance.update(phase='fire_release',next=now+.3)
        elif phase=='fire_release':
            assert equipment.is_weapon_ready(),'Weapon dropped between shots'
            stance.update(phase='lowered_again',next=now+1.2)
        elif phase=='lowered_again':
            assert not equipment.is_weapon_ready() and anim.weapon_ready_weight<.02
            stance['results'].append({'case':'lowered_after_firing','ready_weight':anim.weapon_ready_weight})
            pc.set_control_rotation(u.Rotator(pitch=0,yaw=120,roll=0))
            stance.update(phase='turn_start',next=now+1,index=0)
        elif phase=='turn_start':
            yaw,crouched=[(165,False),(-100,False),(100,False),(-175,False),(0,True),(100,True),(-90,True)][stance['index']]
            if crouched:pawn.crouch()
            else:pawn.un_crouch()
            pc.set_control_rotation(u.Rotator(pitch=10,yaw=yaw,roll=0))
            stance.update(phase='turn_measure',next=now,started=now,yaw=yaw,crouched=crouched,samples=[])
        elif phase=='turn_measure':
            source=pawn.mesh.get_anim_instance()
            mesh=equipment.get_presentation_mesh()
            stance['samples'].append({'t':now-stance['started'],
                'root':stance_delta(pawn.mesh.get_socket_rotation('root').yaw+90,0),
                'aim_yaw':anim.aim_yaw,
                'left_z':mesh.get_socket_location('foot_l').z,
                'right_z':mesh.get_socket_location('foot_r').z,
                'turn': 'TurnInPlace' in str(source.get_editor_property('CurrentDatabaseTags'))})
            assert abs(anim.aim_yaw)<=65.01,anim.aim_yaw
            if now-stance['started']>2.2:
                samples=stance['samples']
                root_error=abs(stance_delta(samples[-1]['root'],stance['yaw']))
                left_range=max(s['left_z'] for s in samples)-min(s['left_z'] for s in samples)
                right_range=max(s['right_z'] for s in samples)-min(s['right_z'] for s in samples)
                muzzle_error=stance_error(stance_muzzle(pawn),pc.get_control_rotation())
                assert any(s['turn'] for s in samples),'No turn animation selected'
                assert max(left_range,right_range)>1,'Feet never lifted during turn'
                assert root_error<35,f'Feet lag aim by {root_error}'
                assert muzzle_error<18,f'Muzzle error {muzzle_error}'
                stance['results'].append({'case':'crouched_turn' if stance['crouched'] else 'standing_turn','yaw':stance['yaw'],
                    'root_error':root_error,'foot_lift_range':max(left_range,right_range),'muzzle_error':muzzle_error,
                    'max_torso_yaw':max(abs(s['aim_yaw']) for s in samples)})
                if stance['index']==2:
                    stance['capture']=u.AutomationLibrary.take_high_res_screenshot(1440,900,str(stance_out/'aim-turn.png'),delay=0.0)
                stance['index']+=1
                if stance['index']==7:stance_finish()
                else:stance.update(phase='turn_start',next=now+.2)
    except Exception:stance_finish(traceback.format_exc())
    finally:stance['busy']=False

stance['handle']=u.register_slate_post_tick_callback(stance_tick)
print('Started relaxed carry and foot turn checks')
