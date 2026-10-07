"""Capture both grips with an independent camera; requires Test-PistolShotgun helpers."""
import traceback
import unreal as u

wc={'index':0,'phase':'select','next':0,'busy':False,'lights':[]}

def wc_finish(error=None):
    u.unregister_slate_post_tick_callback(wc['handle'])
    for actor in wc.pop('lights',[]):actor.destroy_actor()
    wc.update(finished=True,error=error)
    print('WEAPON_GRIP_CAPTURE_COMPLETE',error)

def wc_tick(dt):
    if wc['busy']:return
    wc['busy']=True
    try:
        world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
        pawn=u.GameplayStatics.get_player_pawn(world,0);eq=pawn.baseline_equipment
        now=u.GameplayStatics.get_time_seconds(world)
        if now<wc['next']:
            if wc['phase'] in ['right','left']:wr_input(pawn,'Aim',1)
            return
        name=wr_specs[wc['index']][1]
        if wc['phase']=='select':
            if wr_component(pawn).get_editor_property('skeletal_mesh_asset').get_name()!=name:
                eq.cycle_weapon();wc['next']=now+.5;return
            pawn.character_movement.stop_movement_immediately()
            pawn.set_actor_location(u.Vector(2100,-1100,94),False,True)
            pawn.set_actor_rotation(u.Rotator(yaw=0),False)
            pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
            if eq.is_left_shoulder():eq.toggle_shoulder()
            if not wc['lights']:
                for loc in [u.Vector(2250,-950,230),u.Vector(2250,-1250,230)]:
                    light=u.CRBlueprintTools.spawn_pie_test_actor(world,u.PointLight,u.Transform(location=loc))
                    component=light.get_component_by_class(u.PointLightComponent)
                    component.set_intensity(6500);component.set_attenuation_radius(700);component.set_cast_shadows(False)
                    wc['lights'].append(light)
            wr_input(pawn,'Aim',1);wc.update(phase='right',next=now+2)
        else:
            wr_input(pawn,'Aim',1)
            sign=1 if wc['phase']=='right' else -1
            capture=u.CRBlueprintTools.spawn_pie_test_actor(world,u.SceneCapture2D,u.Transform(location=u.Vector(2245,-1100+sign*160,164)))
            capture.set_actor_rotation(u.MathLibrary.find_look_at_rotation(capture.get_actor_location(),u.Vector(2135,-1100,139)),False)
            component=capture.get_component_by_class(u.SceneCaptureComponent2D)
            component.set_editor_property('capture_every_frame',False);component.set_editor_property('capture_on_movement',False)
            component.set_editor_property('fov_angle',43);component.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
            target=u.RenderingLibrary.create_render_target2d(world,1600,1200,u.TextureRenderTargetFormat.RTF_RGBA8)
            component.set_editor_property('texture_target',target);component.capture_scene()
            u.RenderingLibrary.export_render_target(world,target,str(wr_out),name+'-Grip-'+wc['phase']+'.png')
            capture.destroy_actor()
            if wc['phase']=='right':
                eq.toggle_shoulder();wc.update(phase='left',next=now+2)
            else:
                wr_input(pawn,'Aim',0);eq.toggle_shoulder()
                if wc['index']+1==len(wr_specs):wc_finish()
                else:wc.update(index=wc['index']+1,phase='select',next=now+.5)
    except Exception:wc_finish(traceback.format_exc())
    finally:wc['busy']=False

wc['handle']=u.register_slate_post_tick_callback(wc_tick)
