"""Render the actual roofed facility from human-height and exterior cameras in PIE."""
import time,traceback
from pathlib import Path
import unreal as u

fc_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
fc_out=fc_root/'Artifacts/FacilityMockup';fc_out.mkdir(exist_ok=True)
fc_origin=u.Vector(12600,8100,30)
fc_views=[
 ('Entrance',(-1160,-2070,220),(-1000,-200,215),75),
 ('MainRoom',(-1170,-140,210),(-280,980,250),85),
 ('Office',(780,1290,205),(1250,850,200),82),
 ('FreightBay',(0,-570,210),(1050,-1450,270),85),
 ('RoofExterior',(2500,-3800,2700),(0,0,230),70)]
fc_test=dict(index=0,phase='spawn',next=0,busy=False,deadline=time.monotonic()+120)
def fc_tick(dt):
    if fc_test['busy']:return
    fc_test['busy']=True
    try:
        assert time.monotonic()<fc_test['deadline'],'Facility capture timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        world=worlds[0];now=u.GameplayStatics.get_time_seconds(world)
        if now<fc_test['next']:return
        name,position,target,fov=fc_views[fc_test['index']]
        if fc_test['phase']=='spawn':
            loc=fc_origin+u.Vector(*position);look=fc_origin+u.Vector(*target)
            a=u.CRBlueprintTools.spawn_pie_test_actor(world,u.SceneCapture2D,u.Transform(location=loc))
            a.set_actor_rotation(u.MathLibrary.find_look_at_rotation(loc,look),False)
            c=a.get_component_by_class(u.SceneCaptureComponent2D)
            c.set_editor_property('capture_every_frame',True);c.set_editor_property('always_persist_rendering_state',True)
            c.set_editor_property('fov_angle',fov);c.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
            texture=u.RenderingLibrary.create_render_target2d(world,1920,1080,u.TextureRenderTargetFormat.RTF_RGBA8)
            c.set_editor_property('texture_target',texture)
            fc_test.update(actor=a,texture=texture,phase='export',next=now+1.5)
        else:
            u.RenderingLibrary.export_render_target(world,fc_test['texture'],str(fc_out),name+'.png')
            fc_test['actor'].destroy_actor();fc_test['index']+=1
            if fc_test['index']==len(fc_views):
                u.unregister_slate_post_tick_callback(fc_test['handle']);fc_test['finished']=True;return
            fc_test.update(phase='spawn',next=now+.1)
    except Exception:
        fc_test['error']=traceback.format_exc();print(fc_test['error']);u.unregister_slate_post_tick_callback(fc_test['handle'])
    finally:fc_test['busy']=False
fc_test['handle']=u.register_slate_post_tick_callback(fc_tick)
