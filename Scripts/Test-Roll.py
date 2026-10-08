"""Exercise eight directions, repeated input, collision and traversal/weapon gates in PIE."""
import json,math,time,traceback
from pathlib import Path
import unreal as u

rt_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
rt_out=rt_root/'Artifacts/Roll';rt_out.mkdir(exist_ok=True)
rt_test=dict(phase='setup',index=0,next=0,busy=False,results=[],deadline=time.monotonic()+200)
rt_cases=['direction_'+str(i) for i in range(8)]+['held_input','spam','airborne','slide','wall','ragdoll']

def rt_input(p,name,value):
    paths={'Move':'/Game/Input/IA_Move','Aim':'/Game/Input/IA_Aim','Roll':'/Game/Baseline/Input/IA_Roll','Jump':'/Game/Input/IA_Jump','Fire':'/Game/Input/Actions/IA_Weapon_Fire_Auto'}
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==p.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(paths[name]),u.Vector(*value) if isinstance(value,tuple) else u.Vector(value,0,0),[],[])

def rt_finish(error=None):
    u.unregister_slate_post_tick_callback(rt_test['handle']);rt_test.update(finished=True,error=error)
    if rt_test.get('wall'):rt_test['wall'].destroy_actor()
    report=dict(passed=error is None,error=error,results=rt_test['results'])
    (rt_out/'standalone.json').write_text(json.dumps(report,indent=2)+'\n');print('ROLL_STANDALONE',error)

def rt_tick(dt):
    if rt_test['busy']:return
    rt_test['busy']=True
    try:
        assert time.monotonic()<rt_test['deadline'],'Roll test timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        w=worlds[0];p=u.GameplayStatics.get_player_pawn(w,0)
        if not p or not p.physical_interaction.controls_created:return
        now=u.GameplayStatics.get_time_seconds(w);phase=rt_test['phase']
        case=rt_cases[rt_test['index']]
        if rt_test.pop('release',False):
            for action in ['Move','Roll','Jump','Fire']:rt_input(p,action,0)
        if phase=='settle':
            rt_input(p,'Aim',1)
            if case.startswith('direction_'):rt_input(p,'Move',(rt_test['direction'].y,rt_test['direction'].x,0))
        if phase=='observe' and case=='held_input':rt_input(p,'Roll',1)
        if phase=='observe' and case=='spam':rt_input(p,'Roll',int((now-rt_test['began'])*12)%2)
        if phase=='observe' and p.roll.is_rolling():
            rt_test['rolling_frames']+=1
            rt_test['visible']|=all(not a.get_editor_property('bHidden') for a in rt_test['weapon'].get_spawned_actors())
            rt_test['blocked_jump']|=not p.can_use_movement_actions()
            rt_test['reduced_capsule']|=p.capsule_component.get_scaled_capsule_half_height()<70
            if case.startswith('direction_'):
                assert p.roll.active_direction==int(case.split('_')[1]),(case,p.roll.active_direction)
        if now<rt_test['next']:return
        if phase=='setup':
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.BaselineWeaponPickup) if 'Rifle' in a.item_definition.get_name())
            pos=pickup.get_actor_location();p.set_actor_location(pos+u.Vector(-110,0,94-pos.z),False,True)
            p.baseline_equipment.server_pickup(pickup)
            rt_test.update(phase='place',next=now+1)
        elif phase=='place':
            weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance);assert weapon
            rt_test['weapon']=weapon
            p.character_movement.stop_movement_immediately();p.un_crouch()
            p.set_actor_location(u.Vector(5000,2500,94),False,True);p.set_actor_rotation(u.Rotator(),False)
            p.get_controller().set_control_rotation(u.Rotator());rt_input(p,'Aim',1)
            direction=int(case.split('_')[1]) if case.startswith('direction_') else 0
            rt_test.update(direction=u.Vector(math.cos(math.radians(direction*45)),math.sin(math.radians(direction*45)),0),phase='settle',next=now+.4)
        elif phase=='settle':
            p.character_movement.stop_movement_immediately()
            # Keep facing stable for the directional tests; aim supplies strafe locomotion.
            p.set_actor_rotation(u.Rotator(),False)
            rt_test.update(before=p.roll.rolls_started,start=p.get_actor_location(),began=now,rolling_frames=0,visible=False,blocked_jump=False,reduced_capsule=False)
            if case=='airborne':p.launch_character(u.Vector(0,0,550),False,True);rt_test.update(phase='blocked_press',next=now+.1);return
            if case=='slide':
                p.character_movement.velocity=u.Vector(800,0,0);p.character_movement.set_slide_requested(True);p.crouch()
                rt_test.update(phase='blocked_press',next=now+.12);return
            if case=='ragdoll':
                p.physical_interaction.toggle_ragdoll();rt_test.update(phase='blocked_press',next=now+.2);return
            if case=='wall':
                wall=u.CRBlueprintTools.spawn_pie_test_actor(w,u.StaticMeshActor,u.Transform(location=p.get_actor_location()+u.Vector(190,0,56)))
                wall.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE)
                wall.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
                wall.set_actor_scale3d(u.Vector(.4,8,3));wall.static_mesh_component.set_collision_profile_name('BlockAll');rt_test['wall']=wall
            rt_input(p,'Roll',1)
            rt_test.update(phase='observe',next=now+(2.6 if case in ['held_input','spam'] else 1.2),release=case not in ['held_input','spam'])
        elif phase=='blocked_press':
            if case=='slide':assert p.character_movement.is_sliding(),'Slide fixture did not start'
            rt_input(p,'Roll',1);rt_test.update(phase='blocked_check',next=now+.25,release=True)
        elif phase=='blocked_check':
            assert p.roll.rolls_started==rt_test['before'] and not p.roll.is_rolling(),case+' allowed roll'
            rt_test['results'].append(dict(case=case,blocked=True))
            p.character_movement.set_slide_requested(False);p.un_crouch()
            if case=='ragdoll':p.physical_interaction.request_recovery()
            rt_test.update(phase='advance',next=now+(4 if case=='ragdoll' else 1.5))
        elif phase=='observe':
            delta=p.get_actor_location()-rt_test['start'];distance=math.hypot(delta.x,delta.y)
            count=p.roll.rolls_started-rt_test['before']
            assert rt_test['rolling_frames']>0 and rt_test['visible'] and rt_test['blocked_jump'] and rt_test['reduced_capsule'],(case,rt_test)
            if case=='spam':assert 1<=count<=2,(case,count)
            else:assert count==1,(case,count)
            if case.startswith('direction_'):
                dot=(delta.x*rt_test['direction'].x+delta.y*rt_test['direction'].y)/max(distance,1)
                assert 300<distance<540 and dot>.92,(case,distance,dot)
            if case=='wall':assert 40<distance<155,('Wall penetration',distance)
            rt_test['results'].append(dict(case=case,rolls=count,distance_cm=distance,delta=[delta.x,delta.y,delta.z],weapon_visible=rt_test['visible'],jump_blocked=rt_test['blocked_jump'],capsule_lowered=rt_test['reduced_capsule']))
            rt_input(p,'Roll',0);rt_test.update(phase='restore',next=now+.5)
        elif phase=='restore':
            assert not p.roll.is_rolling() and p.can_use_movement_actions(),case+' movement stayed locked'
            assert all(not a.get_editor_property('bHidden') for a in rt_test['weapon'].get_spawned_actors()),case+' weapon did not return'
            if rt_test.get('wall'):rt_test.pop('wall').destroy_actor()
            rt_test.update(phase='advance',next=now+.4)
        elif phase=='advance':
            rt_test['index']+=1
            if rt_test['index']==len(rt_cases):rt_input(p,'Aim',0);rt_finish();return
            rt_test.update(phase='place',next=now+.1)
    except Exception:rt_finish(traceback.format_exc())
    finally:rt_test['busy']=False
rt_test['handle']=u.register_slate_post_tick_callback(rt_tick)
print('ROLL_STANDALONE_STARTED')
