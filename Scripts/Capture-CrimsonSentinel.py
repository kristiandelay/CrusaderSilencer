"""Inspect grip from a separate scene capture without changing gameplay aim."""
import unreal as u
import time
from pathlib import Path

grip_capture={'phase':0,'next':0,'busy':False}
def grip_tick(dt):
    if grip_capture['busy']:return
    grip_capture['busy']=True
    try:
        world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
        pawn=u.GameplayStatics.get_player_pawn(world,0)
        eq=pawn.baseline_equipment
        now=u.GameplayStatics.get_time_seconds(world)
        cs_input(pawn,'Aim',1)
        if now<grip_capture['next']:return
        phase=grip_capture['phase']
        if phase==0:
            pawn.character_movement.stop_movement_immediately()
            pawn.set_actor_location(u.Vector(2100,-1100,94),False,True)
            pawn.set_actor_rotation(u.Rotator(yaw=0),False)
            pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
            if eq.is_left_shoulder():eq.toggle_shoulder()
            grip_capture['lights']=[]
            for loc in [u.Vector(2250,-950,230),u.Vector(2250,-1250,230)]:
                light=u.CRBlueprintTools.spawn_pie_test_actor(world,u.PointLight,u.Transform(location=loc))
                lc=light.get_component_by_class(u.PointLightComponent)
                lc.set_intensity(6500);lc.set_attenuation_radius(700);lc.set_cast_shadows(False)
                grip_capture['lights'].append(light)
            grip_capture.update(phase=1,next=now+2)
        elif phase in [1,2]:
            sign=1 if phase==1 else -1
            actor=u.CRBlueprintTools.spawn_pie_test_actor(world,u.SceneCapture2D,u.Transform(location=u.Vector(2230,-1100+sign*145,162)))
            actor.set_actor_rotation(u.MathLibrary.find_look_at_rotation(actor.get_actor_location(),u.Vector(2125,-1100,132)),False)
            component=actor.get_component_by_class(u.SceneCaptureComponent2D)
            component.set_editor_property('capture_every_frame',False)
            component.set_editor_property('capture_on_movement',False)
            component.set_editor_property('fov_angle',45)
            component.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
            target=u.RenderingLibrary.create_render_target2d(world,1600,1200,u.TextureRenderTargetFormat.RTF_RGBA8)
            component.set_editor_property('texture_target',target)
            component.capture_scene()
            folder=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/CrimsonSentinel'
            u.RenderingLibrary.export_render_target(world,target,str(folder),'GripRight.png' if phase==1 else 'GripLeft.png')
            actor.destroy_actor()
            if phase==1:
                eq.toggle_shoulder();grip_capture.update(phase=2,next=now+2)
            else:
                cs_input(pawn,'Aim',0)
                for light in grip_capture.pop('lights'):light.destroy_actor()
                u.unregister_slate_post_tick_callback(grip_capture['handle']);grip_capture['finished']=True
    finally:grip_capture['busy']=False
grip_capture['handle']=u.register_slate_post_tick_callback(grip_tick)
