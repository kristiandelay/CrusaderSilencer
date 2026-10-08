"""Capture the actual native robot gait in PIE, without editing level assets."""
import time,traceback,json
from pathlib import Path
import unreal as u

rv_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/RobotGameplay'
rv_state=dict(next=time.monotonic()+4,busy=False,rows=[],index=0)
rv_world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
rv_robots=u.GameplayStatics.get_all_actors_of_class(rv_world,u.CRRobotCharacter)
for r in rv_robots:
    r.mesh.prestream_mesh_lods(30);r.mesh.prestream_textures(30,True)
    name=r.mesh.skeletal_mesh_asset.get_name()
    for kind in ['BaseColor','Normal','Metallic','Roughness']:
        u.load_asset('/Game/Crusader/Robots/'+name+'/Textures/'+name+'_'+kind).set_force_mip_levels_to_be_resident(30)

def rv_tick(dt):
    if rv_state['busy'] or time.monotonic()<rv_state['next']:return
    rv_state['busy']=True
    try:
        r=rv_robots[rv_state['index']];name=r.mesh.skeletal_mesh_asset.get_name()
        center=r.get_actor_location()+u.Vector(0,0,8)
        location=center+r.get_actor_forward_vector()*360+r.get_actor_right_vector()*245+u.Vector(0,0,80)
        camera=u.CRBlueprintTools.spawn_pie_test_actor(rv_world,u.SceneCapture2D,u.Transform(location=location))
        camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(location,center),False)
        component=camera.get_component_by_class(u.SceneCaptureComponent2D)
        component.set_editor_property('capture_every_frame',False);component.set_editor_property('capture_on_movement',False)
        component.set_editor_property('fov_angle',35);component.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        texture=u.RenderingLibrary.create_render_target2d(rv_world,850,850,u.TextureRenderTargetFormat.RTF_RGBA8)
        component.set_editor_property('texture_target',texture);component.capture_scene()
        u.RenderingLibrary.export_render_target(rv_world,texture,str(rv_root),name+'Gameplay.png');camera.destroy_actor()
        rv_state['rows'].append(dict(name=name,speed=r.mesh.get_anim_instance().ground_speed,foot_error_cm=r.mesh.get_anim_instance().maximum_foot_error,foot_plants=r.mesh.get_anim_instance().foot_plants,muzzle=[r.get_mounted_muzzle().x,r.get_mounted_muzzle().y,r.get_mounted_muzzle().z]))
        rv_state['index']+=1;rv_state['next']=time.monotonic()+.5
        if rv_state['index']==len(rv_robots):
            (rv_root/'captures.json').write_text(json.dumps(rv_state['rows'],indent=2)+'\n')
            rv_state['finished']=True;u.unregister_slate_post_tick_callback(rv_state['handle'])
    except Exception:
        rv_state['error']=traceback.format_exc();rv_state['finished']=True;u.unregister_slate_post_tick_callback(rv_state['handle'])
        print(rv_state['error'])
    finally:rv_state['busy']=False

rv_state['handle']=u.register_slate_post_tick_callback(rv_tick)
print('ROBOT_GAMEPLAY_CAPTURE_STARTED')
