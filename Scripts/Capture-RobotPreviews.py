"""Inspect actual Unreal animation evaluation in temporary PIE actors.

Run through Send-Editor.py with PIE stopped. Captures and the result are written
under Artifacts/Robots; no level actors or map packages are saved.
"""
import json
import time
import traceback
from pathlib import Path
import unreal as u

robot_capture_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
robot_capture_names=list(json.loads((robot_capture_root/'resources/RobotRigs.json').read_text()))
assert not u.EditorLevelLibrary.get_pie_worlds(False),'Stop PIE before preview validation'
robot_capture_editor=u.get_editor_subsystem(u.UnrealEditorSubsystem)
robot_capture_view=robot_capture_editor.get_level_viewport_camera_info()
robot_capture=dict(phase='start',busy=False,deadline=time.monotonic()+120,actors=[],rows=[])

def robot_capture_finish(error=None):
    if error:robot_capture['error']=error
    robot_capture['finished']=True
    u.unregister_slate_post_tick_callback(robot_capture['handle'])
    u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
    robot_capture_editor.set_level_viewport_camera_info(*robot_capture_view)
    output=dict(passed=not error,robots=robot_capture['rows'],error=error)
    (robot_capture_root/'Artifacts/Robots/unreal-preview-validation.json').write_text(json.dumps(output,indent=2)+'\n')

def robot_capture_image(world,actor,name,label):
    center=actor.get_actor_location()+u.Vector(0,0,90)
    location=center+u.Vector(-280,380,155)
    camera=u.CRBlueprintTools.spawn_pie_test_actor(world,u.SceneCapture2D,u.Transform(location=location))
    camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(location,center),False)
    component=camera.get_component_by_class(u.SceneCaptureComponent2D)
    component.set_editor_property('capture_every_frame',False)
    component.set_editor_property('capture_on_movement',False)
    component.set_editor_property('fov_angle',32)
    component.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    texture=u.RenderingLibrary.create_render_target2d(world,1000,1000,u.TextureRenderTargetFormat.RTF_RGBA8)
    component.set_editor_property('texture_target',texture)
    component.capture_scene()
    u.RenderingLibrary.export_render_target(world,texture,str(robot_capture_root/'Artifacts/Robots'/name),'Unreal'+label+'.png')
    camera.destroy_actor()

def robot_capture_tick(dt):
    if robot_capture['busy']:return
    robot_capture['busy']=True
    try:
        assert time.monotonic()<robot_capture['deadline'],'Robot preview capture timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        world=worlds[0]
        if robot_capture['phase']=='start':
            for i,name in enumerate(robot_capture_names):
                folder='/Game/Crusader/Robots/'+name
                bp=u.load_asset(folder+'/BP_'+name+'_Preview')
                actor=u.CRBlueprintTools.spawn_pie_test_actor(world,bp.generated_class(),u.Transform(location=u.Vector(i*800,30000,3000)))
                assert actor,name
                mesh=actor.skeletal_mesh_component
                mesh.set_editor_property('visibility_based_anim_tick_option',u.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
                mesh.set_forced_lod(1);mesh.prestream_mesh_lods(30);mesh.prestream_textures(30,True)
                for kind in ['BaseColor','Normal','Roughness','Metallic']:
                    u.load_asset(folder+'/Textures/'+name+'_'+kind).set_force_mip_levels_to_be_resident(30)
                mesh.set_position(0,False);mesh.set_play_rate(0)
                robot_capture['actors'].append((name,actor))
                light=u.CRBlueprintTools.spawn_pie_test_actor(world,u.PointLight,u.Transform(location=actor.get_actor_location()+u.Vector(-180,250,350)))
                light.point_light_component.set_intensity(30000)
                light.point_light_component.set_attenuation_radius(1000)
            robot_capture.update(phase='rest',next=time.monotonic()+4)
            return
        if time.monotonic()<robot_capture['next']:return
        if robot_capture['phase']=='rest':
            for name,actor in robot_capture['actors']:
                mesh=actor.skeletal_mesh_component
                origin=mesh.get_socket_location('foot_l')
                robot_capture['rows'].append(dict(name=name,rest_foot=[origin.x,origin.y,origin.z]))
                robot_capture_image(world,actor,name,'Rest')
                mesh.set_position(1,False)
            robot_capture.update(phase='bent',next=time.monotonic()+1)
        elif robot_capture['phase']=='bent':
            for row,(name,actor) in zip(robot_capture['rows'],robot_capture['actors']):
                mesh=actor.skeletal_mesh_component
                position=mesh.get_socket_location('foot_l')
                row['bent_foot']=[position.x,position.y,position.z]
                row['foot_travel_cm']=(position-u.Vector(*row['rest_foot'])).length()
                assert row['foot_travel_cm']>5,(name,'Animation did not move foot',row)
                robot_capture_image(world,actor,name,'Bent')
                row['passed']=True
            robot_capture_finish()
    except Exception:
        robot_capture_finish(traceback.format_exc())
        print(robot_capture['error'])
    finally:robot_capture['busy']=False

robot_capture['handle']=u.register_slate_post_tick_callback(robot_capture_tick)
u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_begin_play()
print('ROBOT_PREVIEW_CAPTURE_STARTED')
