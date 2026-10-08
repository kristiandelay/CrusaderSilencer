"""Render the actual Level2 control room from human-height and exterior cameras in PIE."""
import time,traceback
from pathlib import Path
import unreal as u

ccap_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
ccap_out=ccap_root/'Artifacts/ControlRoom';ccap_out.mkdir(exist_ok=True)
ccap_origin=u.Vector(20600,7900,30)
ccap_views=[
 ('Entrance',(0,-2750,240),(0,450,300),82),
 ('Hall',(0,-1100,240),(0,1600,240),85),
 ('Command',(-700,650,210),(0,1650,150),72),
 ('Service',(-2030,-260,210),(-2600,360,180),85),
 ('Storage',(2060,-390,210),(2740,280,170),85),
 ('RoofExterior',(4900,-5500,4900),(0,0,230),70)]
ccap_test=dict(index=0,phase='spawn',next=0,busy=False,deadline=time.monotonic()+120)
def ccap_tick(dt):
    if ccap_test['busy']:return
    ccap_test['busy']=True
    try:
        assert time.monotonic()<ccap_test['deadline'],'Control room capture timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        world=worlds[0];now=u.GameplayStatics.get_time_seconds(world)
        if now<ccap_test['next']:return
        name,position,target,fov=ccap_views[ccap_test['index']]
        if ccap_test['phase']=='spawn':
            loc=ccap_origin+u.Vector(*position);look=ccap_origin+u.Vector(*target)
            a=u.CRBlueprintTools.spawn_pie_test_actor(world,u.SceneCapture2D,u.Transform(location=loc))
            a.set_actor_rotation(u.MathLibrary.find_look_at_rotation(loc,look),False)
            c=a.get_component_by_class(u.SceneCaptureComponent2D)
            c.set_editor_property('capture_every_frame',True);c.set_editor_property('always_persist_rendering_state',True)
            c.set_editor_property('fov_angle',fov);c.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
            texture=u.RenderingLibrary.create_render_target2d(world,1920,1080,u.TextureRenderTargetFormat.RTF_RGBA8)
            c.set_editor_property('texture_target',texture)
            ccap_test.update(actor=a,texture=texture,phase='export',next=now+1.5)
        else:
            u.RenderingLibrary.export_render_target(world,ccap_test['texture'],str(ccap_out),name+'.png')
            ccap_test['actor'].destroy_actor();ccap_test['index']+=1
            if ccap_test['index']==len(ccap_views):
                u.unregister_slate_post_tick_callback(ccap_test['handle']);ccap_test['finished']=True;return
            ccap_test.update(phase='spawn',next=now+.1)
    except Exception:
        ccap_test['error']=traceback.format_exc();print(ccap_test['error']);u.unregister_slate_post_tick_callback(ccap_test['handle'])
    finally:ccap_test['busy']=False
ccap_test['handle']=u.register_slate_post_tick_callback(ccap_tick)
