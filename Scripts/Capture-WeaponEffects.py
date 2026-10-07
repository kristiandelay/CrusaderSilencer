"""Capture the actual rifle muzzle/impact and the authored range without changing aim."""
import time
import traceback
from pathlib import Path
import unreal as u

capture_fx=dict(phase='pickup',next=0,busy=False,deadline=time.monotonic()+70)
capture_folder=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/WeaponFX'
def cfx_input(pawn,name,value):
    paths={'Aim':'/Game/Input/IA_Aim','Fire':'/Game/Input/Actions/IA_Weapon_Fire','FireAuto':'/Game/Input/Actions/IA_Weapon_Fire_Auto'}
    subsystem=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    subsystem.inject_input_vector_for_action(u.load_asset(paths[name]),u.Vector(value,0,0),[],[])
def cfx_image(world,name,location,target,fov=60):
    actor=u.CRBlueprintTools.spawn_pie_test_actor(world,u.SceneCapture2D,u.Transform(location=location))
    actor.set_actor_rotation(u.MathLibrary.find_look_at_rotation(location,target),False)
    component=actor.get_component_by_class(u.SceneCaptureComponent2D)
    component.set_editor_property('capture_every_frame',False);component.set_editor_property('capture_on_movement',False)
    component.set_editor_property('fov_angle',fov);component.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    target_texture=u.RenderingLibrary.create_render_target2d(world,1600,1000,u.TextureRenderTargetFormat.RTF_RGBA8)
    component.set_editor_property('texture_target',target_texture);component.capture_scene()
    u.RenderingLibrary.export_render_target(world,target_texture,str(capture_folder),name+'.png');actor.destroy_actor()
def cfx_tick(dt):
    if capture_fx['busy']:return
    capture_fx['busy']=True
    try:
        assert time.monotonic()<capture_fx['deadline'],'Capture timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        world=worlds[0];pawn=u.GameplayStatics.get_player_pawn(world,0)
        if not pawn or not pawn.physical_interaction.controls_created:return
        now=u.GameplayStatics.get_time_seconds(world);phase=capture_fx['phase']
        if capture_fx.pop('release',False):
            for action in ['Fire','FireAuto']:cfx_input(pawn,action,0)
        if phase in ['settle','fire','wait','capture']:
            cfx_input(pawn,'Aim',1)
            camera=u.GameplayStatics.get_player_camera_manager(world,0).get_camera_location()
            pawn.get_controller().set_control_rotation(u.MathLibrary.find_look_at_rotation(camera,u.Vector(370,-6920,170)))
        if now<capture_fx['next']:return
        if phase=='pickup':
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup) if 'Rifle' in a.item_definition.get_name())
            loc=pickup.get_actor_location();pawn.set_actor_location(u.Vector(loc.x-110,loc.y,94),False,True)
            pawn.baseline_equipment.server_pickup(pickup)
            capture_fx.update(phase='position',next=now+1)
        elif phase=='position':
            assert pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
            pawn.get_controller().set_ignore_move_input(True);pawn.get_controller().set_ignore_look_input(True)
            pawn.set_actor_location(u.Vector(370,-5710,94),False,True)
            capture_fx.update(phase='settle',next=now+1)
        elif phase=='settle':
            cfx_image(world,'SurfaceRange',u.Vector(1700,-4350,1500),u.Vector(1200,-6440,70),78)
            u.GameplayStatics.set_global_time_dilation(world,.15)
            capture_fx.update(phase='fire',next=now+.15)
        elif phase=='fire':
            capture_fx['before']=pawn.weapon_effects.shots_played
            for action in ['Fire','FireAuto']:cfx_input(pawn,action,1)
            capture_fx.update(phase='wait',release=True)
        elif phase=='wait':
            if pawn.weapon_effects.shots_played==capture_fx['before']:return
            capture_fx.update(phase='capture',next=now+.02)
        elif phase=='capture':
            weapon=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_spawned_actors()[0]
            muzzle=weapon.get_component_by_class(u.SkeletalMeshComponent).get_socket_location('Muzzle')
            cfx_image(world,'RifleMuzzle',muzzle+u.Vector(130,150,55),muzzle+u.Vector(0,-25,0),60)
            cfx_image(world,'MetalImpact',u.Vector(660,-6570,235),u.Vector(370,-6920,170),55)
            u.GameplayStatics.set_global_time_dilation(world,1)
            cfx_input(pawn,'Aim',0)
            capture_fx['finished']=True;u.unregister_slate_post_tick_callback(capture_fx['handle'])
    except Exception:
        capture_fx.update(finished=True,error=traceback.format_exc());u.unregister_slate_post_tick_callback(capture_fx['handle']);print(capture_fx['error'])
    finally:capture_fx['busy']=False
capture_fx['handle']=u.register_slate_post_tick_callback(cfx_tick)
