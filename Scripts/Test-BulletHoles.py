"""Real shotgun pellets: attached marks, bounded population, lifetime and fade."""
import json,time,traceback,math
from pathlib import Path
import unreal as u
bh_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
bh_test=dict(phase='pickup',next=0,busy=False,results=[],deadline=time.monotonic()+100)

def bh_input(p,name,value):
    paths={'Aim':'/Game/Input/IA_Aim','Fire':'/Game/Input/Actions/IA_Weapon_Fire','FireAuto':'/Game/Input/Actions/IA_Weapon_Fire_Auto'}
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==p.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(paths[name]),u.Vector(value,0,0),[],[])

def bh_finish(error=None):
    if bh_test.get('profile'):
        bh_test['profile'].set_editor_property('max_bullet_holes',bh_test['original_cap'])
        bh_test['profile'].set_editor_property('decal_lifetime',bh_test['original_lifetime'])
    u.unregister_slate_post_tick_callback(bh_test['handle']);bh_test.update(finished=True,error=error)
    (bh_root/'Artifacts/Environment/bullet-holes.json').write_text(json.dumps(dict(passed=not error,error=error,results=bh_test['results']),indent=2))
    print('BULLET_HOLES_COMPLETE',error)

def bh_tick(dt):
    if bh_test['busy']:return
    bh_test['busy']=True
    try:
        assert time.monotonic()<bh_test['deadline'],'Bullet holes timed out'
        ws=u.EditorLevelLibrary.get_pie_worlds(False)
        if not ws:return
        w=ws[0];p=u.GameplayStatics.get_player_pawn(w,0)
        if not p or not p.physical_interaction.controls_created:return
        now=u.GameplayStatics.get_time_seconds(w);phase=bh_test['phase'];fx=p.weapon_effects
        if bh_test.pop('release',False):
            for n in ['Fire','FireAuto']:bh_input(p,n,0)
        if phase in ['aim','fire','check']:
            camera=u.GameplayStatics.get_player_camera_manager(w,0).get_camera_location()
            p.get_controller().set_control_rotation(u.MathLibrary.find_look_at_rotation(camera,bh_test['target']))
            bh_input(p,'Aim',1)
        if now<bh_test['next']:return
        if phase=='pickup':
            for slot,item in enumerate(p.get_controller().quick_bar.get_slots()):
                if item and 'ID_Shotgun_C' in u.CRBlueprintTools.describe_object(item):
                    p.get_controller().quick_bar.set_active_slot_index(slot);break
            else:
                pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.BaselineWeaponPickup) if 'Shotgun' in a.item_definition.get_name())
                p.set_actor_location(pickup.get_actor_location()+u.Vector(-100,0,40),False,True);p.baseline_equipment.server_pickup(pickup)
            bh_test.update(phase='position',next=now+1)
        elif phase=='position':
            weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
            assert weapon and weapon.effects_profile.get_name()=='FX_Shotgun'
            profile=weapon.effects_profile
            bh_test.update(profile=profile,original_cap=profile.max_bullet_holes,original_lifetime=profile.decal_lifetime)
            profile.set_editor_property('max_bullet_holes',3);profile.set_editor_property('decal_lifetime',1.5)
            prop=next(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.StaticMeshActor) if a.actor_has_tag('BulletHoleAttachmentTest'))
            center,extent=prop.get_actor_bounds(True)
            p.get_controller().set_ignore_move_input(True);p.get_controller().set_ignore_look_input(True)
            p.character_movement.stop_movement_immediately();p.set_actor_location(u.Vector(center.x,center.y+600,94),False,True)
            bh_test.update(prop=prop,target=center,phase='aim',next=now+1)
        elif phase=='aim':bh_test.update(phase='fire',next=now+.3)
        elif phase=='fire':
            bh_test['before']=fx.decals_spawned
            for n in ['Fire','FireAuto']:bh_input(p,n,1)
            bh_test.update(phase='check',next=now+.15,release=True)
        elif phase=='check':
            assert fx.decals_spawned-bh_test['before']>3,[(h.surface,h.blocking_hit) for h in fx.last_impacts]
            assert fx.get_active_bullet_hole_count()==3,fx.get_active_bullet_hole_count()
            decal=fx.last_decal;prop=bh_test['prop']
            assert decal.get_attach_parent()==prop.static_mesh_component
            before=decal.get_world_location();prop.set_actor_location(prop.get_actor_location()+u.Vector(120,75,0),False,True)
            after=decal.get_world_location();delta=after-before
            assert (delta-u.Vector(120,75,0)).length()<.1,delta
            bh_test['results'].append(dict(case='pellet_cap_and_moving_receiver',spawned=fx.decals_spawned-bh_test['before'],active=3,moved_with_prop=True,material=decal.get_decal_material().get_path_name()))
            bh_input(p,'Aim',0);bh_test.update(phase='expire',next=now+2)
        elif phase=='expire':
            assert fx.get_active_bullet_hole_count()==0,fx.get_active_bullet_hole_count()
            bh_test['results'].append(dict(case='timed_fade_and_cleanup',active=0));bh_finish()
    except Exception:bh_finish(traceback.format_exc())
    finally:bh_test['busy']=False
bh_test['handle']=u.register_slate_post_tick_callback(bh_tick)
