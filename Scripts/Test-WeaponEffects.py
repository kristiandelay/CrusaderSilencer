"""Real firing against every physical surface; misses, pellets and both shoulders."""
import json
import time
import traceback
from pathlib import Path
import unreal as u

fx_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
fx_targets=json.loads((fx_root/'resources/SurfaceRange.json').read_text())['targets']
fx_cases=[dict(weapon='Pistol',target=t,left=i%2==1) for i,t in enumerate(fx_targets)]
fx_cases += [dict(weapon=k,target=fx_targets[2],left=left) for k in ['Rifle','Shotgun'] for left in [False,True]]
fx_cases += [dict(weapon=k,target=None,left=False) for k in ['Pistol','Rifle','Shotgun']]
fx_test=dict(phase='pickup',index=0,next=0,busy=False,results=[],deadline=time.monotonic()+300)

def fx_input(pawn,name,value):
    paths={'Aim':'/Game/Input/IA_Aim','Fire':'/Game/Input/Actions/IA_Weapon_Fire','FireAuto':'/Game/Input/Actions/IA_Weapon_Fire_Auto'}
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(paths.get(name,'/Game/Baseline/Input/IA_'+name)),u.Vector(value,0,0),[],[])
def fx_finish(error=None):
    u.unregister_slate_post_tick_callback(fx_test['handle']);fx_test.update(finished=True,error=error)
    (fx_root/'Artifacts/WeaponFX/gameplay-validation.json').write_text(json.dumps(dict(passed=not error,error=error,results=fx_test['results']),indent=2))
    print('WEAPON_EFFECTS_TEST_COMPLETE',error)
def fx_tick(dt):
    if fx_test['busy']:return
    fx_test['busy']=True
    try:
        assert time.monotonic()<fx_test['deadline'],'Effects test timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        world=worlds[0];pawn=u.GameplayStatics.get_player_pawn(world,0)
        if not pawn or not pawn.physical_interaction.controls_created:return
        if not fx_test.get('isolated'):
            pawn.get_controller().set_ignore_move_input(True);pawn.get_controller().set_ignore_look_input(True);fx_test['isolated']=True
        now=u.GameplayStatics.get_time_seconds(world);case=fx_cases[fx_test['index']];phase=fx_test['phase'];effects=pawn.weapon_effects
        if fx_test.pop('release',False):
            for action in ['Interact','Shoulder','Fire','FireAuto']:fx_input(pawn,action,0)
        if phase in ['settle','fire','check']:
            fx_input(pawn,'Aim',1)
            if case['target']:
                camera=u.GameplayStatics.get_player_camera_manager(world,0).get_camera_location()
                pawn.get_controller().set_control_rotation(u.MathLibrary.find_look_at_rotation(camera,u.Vector(*case['target']['target'])))
            else:pawn.get_controller().set_control_rotation(u.Rotator(pitch=80,yaw=90))
        if now<fx_test['next']:return
        if phase=='pickup':
            current=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
            if current and current.effects_profile.get_name()=='FX_'+case['weapon']:
                fx_test.update(phase='position');return
            for slot,item in enumerate(pawn.get_controller().quick_bar.get_slots()):
                if item and case['weapon']+'_C' in u.CRBlueprintTools.describe_object(item):
                    pawn.get_controller().quick_bar.set_active_slot_index(slot)
                    fx_test.update(phase='position',next=now+.6);return
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup) if a.item_definition.get_name() in ['ID_'+case['weapon']+'_C']+(['ID_BlackIronRifle_C'] if case['weapon']=='Rifle' else []))
            loc=pickup.get_actor_location();pawn.character_movement.stop_movement_immediately()
            pawn.set_actor_location(u.Vector(loc.x-110,loc.y,94),False,True)
            fx_input(pawn,'Aim',0)
            fx_test.update(phase='pickup_wait',next=now+.6,pickup_name=pickup.get_name())
        elif phase=='pickup_wait':
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup) if a.get_name()==fx_test['pickup_name'])
            pawn.baseline_equipment.server_pickup(pickup)
            fx_test.update(phase='position',next=now+1.2,release=True)
        elif phase=='position':
            weapon=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
            assert weapon and weapon.effects_profile.get_name()=='FX_'+case['weapon']
            if pawn.baseline_equipment.is_left_shoulder()!=case['left']:fx_input(pawn,'Shoulder',1)
            target=case['target'];position=target['standing'] if target else [1100,-5700,94]
            pawn.character_movement.stop_movement_immediately();pawn.set_actor_location(u.Vector(*position),False,True)
            pawn.set_actor_rotation(u.Rotator(yaw=-90),False)
            fx_test.update(phase='settle',next=now+1.3,release=True)
        elif phase=='settle':fx_test.update(phase='fire',next=now+.3)
        elif phase=='fire':
            fx_test.update(before_shots=effects.shots_played,before_impacts=effects.impacts_played,before_trails=effects.trails_played)
            for action in ['Fire','FireAuto']:fx_input(pawn,action,1)
            fx_test.update(phase='check',next=now+.35,release=True)
        elif phase=='check':
            hits=effects.last_impacts
            result=dict(weapon=case['weapon'],surface=case['target']['name'] if case['target'] else 'Miss',left=case['left'],shots=effects.shots_played-fx_test['before_shots'],impacts=effects.impacts_played-fx_test['before_impacts'],trails=effects.trails_played-fx_test['before_trails'],pellets=len(hits),hit_surfaces=[h.surface for h in hits],blocking=[h.blocking_hit for h in hits])
            fx_test['results'].append(result)
            assert result['shots']==1,result
            assert result['trails']==len(hits)>0,result
            if case['target']:
                assert result['impacts']>0 and all(h.surface==case['target']['surface'] for h in hits if h.blocking_hit),result
            else:assert result['impacts']==0 and not any(result['blocking']),result
            if case['weapon']=='Shotgun':assert len(hits)>1,result
            legacy=[a for a in u.GameplayStatics.get_all_actors_of_class(world,u.Actor) if a.get_class().get_name() in ['B_WeaponFire_C','B_WeaponImpacts_C','B_WeaponDecals_C']]
            assert not legacy,'Legacy effects duplicated new effects'
            fx_input(pawn,'Aim',0)
            fx_test['index']+=1
            if fx_test['index']==len(fx_cases):fx_finish()
            else:fx_test.update(phase='pickup',next=now+.2)
    except Exception:fx_finish(traceback.format_exc())
    finally:fx_test['busy']=False
fx_test['handle']=u.register_slate_post_tick_callback(fx_tick)
print('Started real weapon/surface effects checks')
