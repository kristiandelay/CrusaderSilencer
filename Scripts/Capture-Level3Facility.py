"""Capture the actual enclosed three-storey facility and its stairwell in PIE."""
import time,traceback
from pathlib import Path
import unreal as u

lp_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
lp_out=lp_root/'Artifacts/Level3';lp_out.mkdir(exist_ok=True)
lp_origin=u.Vector(33000,7900,30)
lp_views=[('Exterior',(7800,-9200,6500),(650,0,950),74),
          ('Entrance',(0,-3370,240),(0,450,290),83),
          ('LoadingAndReactor',(-1000,-1800,240),(0,1600,190),86),
          ('Operations',(-920,-500,960),(0,1750,920),83),
          ('Research',(-1050,-380,1680),(0,1600,1630),83),
          ('Medbay',(-1740,560,1660),(-2500,1700,1550),86),
          ('Stairwell',(4300,-1920,960),(4200,1050,1350),90)]
lp_test=dict(index=0,phase='spawn',next=0,busy=False,deadline=time.monotonic()+180)
def lp_tick(delta):
    if lp_test['busy']:return
    lp_test['busy']=True
    try:
        assert time.monotonic()<lp_test['deadline'],'Facility capture timeout'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        world=worlds[0];now=u.GameplayStatics.get_time_seconds(world)
        if now<lp_test['next']:return
        name,pos,target,fov=lp_views[lp_test['index']]
        if lp_test['phase']=='spawn':
            location=lp_origin+u.Vector(*pos);look=lp_origin+u.Vector(*target)
            a=u.CRBlueprintTools.spawn_pie_test_actor(world,u.SceneCapture2D,u.Transform(location=location))
            a.set_actor_rotation(u.MathLibrary.find_look_at_rotation(location,look),False)
            c=a.get_component_by_class(u.SceneCaptureComponent2D)
            c.set_editor_property('capture_every_frame',True);c.set_editor_property('always_persist_rendering_state',True)
            c.set_editor_property('fov_angle',float(fov));c.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
            texture=u.RenderingLibrary.create_render_target2d(world,1600,1000,u.TextureRenderTargetFormat.RTF_RGBA8)
            c.set_editor_property('texture_target',texture)
            lp_test.update(actor=a,texture=texture,phase='export',next=now+2.)
        else:
            u.RenderingLibrary.export_render_target(world,lp_test['texture'],str(lp_out),name+'.png')
            lp_test['actor'].destroy_actor();lp_test['index']+=1
            if lp_test['index']==len(lp_views):
                u.unregister_slate_post_tick_callback(lp_test['handle']);lp_test['finished']=True;print('LEVEL3_CAPTURES_COMPLETE');return
            lp_test.update(phase='spawn',next=now+.1)
    except Exception:
        lp_test.update(error=traceback.format_exc(),finished=True);print(lp_test['error']);u.unregister_slate_post_tick_callback(lp_test['handle'])
    finally:lp_test['busy']=False
lp_test['handle']=u.register_slate_post_tick_callback(lp_tick)
