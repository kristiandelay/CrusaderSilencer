"""Mapped C/H/Q input: aim/release during slides and slide entry while aiming."""
import json,math,time,traceback
from pathlib import Path
import unreal as u

tsl_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
tsl_test=dict(next=0,busy=False,results=[],deadline=time.monotonic()+240,report='slide.json')

def tsl_key(p,key,down):
    k=u.Key();assert k.import_text(key);u.CRBlueprintTools.inject_pie_key(p,k,down)

def tsl_context():
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    pawns=[p for w in worlds for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if isinstance(p.get_controller(),u.PlayerController) and not p.crowd_agent.enabled]
    p=next(p for p in pawns if p.is_locally_controlled() and (not p.has_authority() if len(worlds)>1 else True))
    server=next(p for p in pawns if p.has_authority() and not p.is_locally_controlled()) if len(worlds)>1 else p
    return p,server

def tsl_prepare(p,server,left,kind):
    for key in ['W','A','S','D','LeftShift','C','H','Q','Z']:tsl_key(p,key,False)
    for a in u.GameplayStatics.get_all_actors_of_class(server.get_world(),u.CRThrownObject):a.destroy_actor()
    p.character_movement.set_slide_requested(False);p.un_crouch()
    server.character_movement.set_slide_requested(False);server.un_crouch()
    yield .4
    server.character_movement.stop_movement_immediately();server.set_actor_location(u.Vector(5000,2500,94),False,True)
    server.set_actor_rotation(u.Rotator(yaw=0),False);server.force_net_update();p.get_controller().set_control_rotation(u.Rotator(yaw=0))
    yield .8
    if p.baseline_equipment.is_left_shoulder()!=left:
        tsl_key(p,'Q',True);yield .07;tsl_key(p,'Q',False);yield .4
    if p.throwable.selected_type!=kind:
        tsl_key(p,'X',True);yield .07;tsl_key(p,'X',False);yield .2
    tsl_key(p,'W',True);tsl_key(p,'LeftShift',True)
    deadline=u.GameplayStatics.get_time_seconds(p)+5
    while p.get_velocity().length()<680:
        assert u.GameplayStatics.get_time_seconds(p)<deadline,'Could not reach slide speed'
        yield .05

def tsl_pose(p,left):
    anim=p.mesh.get_anim_instance()
    assert p.character_movement.is_sliding(),'Slide movement interrupted'
    assert anim.is_slot_active('DefaultSlot') and anim.is_slot_active('ThrowUpperBody'),'Both animation layers must run'
    hand='hand_l' if left else 'hand_r';other='hand_r' if left else 'hand_l'
    heights=[]
    for mesh in [p.mesh,p.baseline_equipment.get_presentation_mesh()]:
        floor=p.get_actor_location().z-p.capsule_component.get_scaled_capsule_half_height()
        height=mesh.get_socket_location('pelvis').z-floor;heights.append(height)
        assert 5<height<78,('Lost low slide pose',height)
        assert mesh.get_socket_location(hand).z>mesh.get_socket_location(other).z+15,('Throw pose not layered over slide',left,mesh.get_name(),mesh.get_socket_location(hand).z-mesh.get_socket_location(other).z,anim.blueprint_get_slot_montage_local_weight('DefaultSlot'),anim.blueprint_get_slot_montage_local_weight('ThrowUpperBody'))
    held=next(c for c in p.get_components_by_class(u.StaticMeshComponent) if c.static_mesh and c.static_mesh.get_name() in ['SM_Grenade','SM_Smoke'])
    assert held.is_visible() and str(held.get_attach_socket_name())==hand
    return heights

def tsl_run():
    while True:
        try:p,server=tsl_context();break
        except StopIteration:yield .2
    while not p.physical_interaction.controls_created or not server.physical_interaction.controls_created:yield .2
    if p!=server:tsl_test['report']='slide-network.json'
    pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(server.get_world(),u.BaselineWeaponPickup) if 'Rifle' in a.item_definition.get_name())
    pos=pickup.get_actor_location();server.set_actor_location(pos+u.Vector(-110,0,94-pos.z),False,True);server.baseline_equipment.server_pickup(pickup)
    yield 1
    for aim_first in [False,True]:
        for kind in [u.CRThrowableType.GRENADE,u.CRThrowableType.SMOKE]:
            for left in [False,True]:
                yield from tsl_prepare(p,server,not left if not aim_first else left,kind)
                if aim_first:
                    tsl_key(p,'H',True);yield .001
                    assert p.throwable.phase==u.CRThrowPhase.AIMING
                tsl_test['entry']=dict(aim_first=aim_first,left=left,speed=p.get_velocity().length(),can_start_slide=p.character_movement.can_start_slide())
                tsl_key(p,'C',True);yield .07;tsl_key(p,'C',False)
                tsl_key(p,'W',False);tsl_key(p,'LeftShift',False)
                yield .16
                assert p.character_movement.is_sliding() and server.character_movement.is_sliding(),('Slide rejected while preparing throw',tsl_test['entry'],p.character_movement.is_sliding(),server.character_movement.is_sliding())
                if not aim_first:tsl_key(p,'H',True);yield .2
                assert p.throwable.phase==server.throwable.phase==u.CRThrowPhase.AIMING,'Aim rejected during slide'
                p.get_controller().set_control_rotation(u.Rotator(yaw=35 if not left else -35))
                if not aim_first:
                    tsl_key(p,'Q',True);yield .07;tsl_key(p,'Q',False)
                yield .25
                heights=tsl_pose(p,left);tsl_pose(server,left)
                assert p.throwable.is_left_throw_hand()==server.throwable.is_left_throw_hand()==left
                assert abs(p.get_actor_rotation().yaw)<8,'Slide legs turned with camera instead of momentum'
                yaw=p.mesh.get_anim_instance().throw_root_rotation.yaw
                assert abs(yaw-(35 if not left else -35))<8,('Torso failed to track sideways aim',yaw)
                assert p.throwable.preview_visible and not p.throwable.launch_blocked
                aim=p.get_control_rotation();offset=u.MathLibrary.get_forward_vector(aim)*38+u.MathLibrary.get_right_vector(aim)*(-24 if left else 24)+u.Vector(0,0,48)
                error=(p.throwable.preview_points[0]-p.get_actor_location()-offset).length()
                assert error<2,('Sliding trajectory did not follow capsule',error)
                before=server.throwable.throws_released;count=server.throwable.get_remaining();start=p.get_actor_location()
                tsl_key(p,'H',False);yield .4
                assert p.throwable.phase==server.throwable.phase==u.CRThrowPhase.THROWING
                assert p.character_movement.is_sliding() and server.character_movement.is_sliding(),'Release cancelled slide'
                anim=p.mesh.get_anim_instance()
                assert anim.is_slot_active('DefaultSlot'),'Release replaced leg montage'
                assert anim.montage_is_playing(p.throwable.get_editor_property('left_throw_montage' if left else 'throw_montage'))
                assert server.throwable.throws_released==before+1 and server.throwable.get_remaining()==count-1
                assert (p.get_actor_location()-start).length()>80,'Throw stopped slide momentum'
                for w in u.EditorLevelLibrary.get_pie_worlds(False):
                    assert len(u.GameplayStatics.get_all_actors_of_class(w,u.CRThrownObject))==1,'Projectile replication or duplicate release'
                yield .65
                assert not p.throwable.is_busy() and not server.throwable.is_busy()
                tsl_test['results'].append(dict(case='slide_throw',aim_before_slide=aim_first,type=str(kind),left=left,slide_pelvis_height_cm=heights,torso_yaw_degrees=yaw,preview_error_cm=error,one_replicated_projectile=True))

    # Cancel only the upper-body aim: slide must continue. A later aim can survive
    # manual slide exit and become a normal walking throw without spending twice.
    yield from tsl_prepare(p,server,False,u.CRThrowableType.GRENADE)
    tsl_key(p,'C',True);yield .07;tsl_key(p,'C',False);tsl_key(p,'W',False);tsl_key(p,'LeftShift',False)
    tsl_key(p,'H',True);yield .4;before=server.throwable.throws_released
    tsl_key(p,'Z',True);yield .07;tsl_key(p,'Z',False);tsl_key(p,'H',False);yield .2
    assert not p.throwable.is_busy() and not server.throwable.is_busy()
    assert p.character_movement.is_sliding() and p.mesh.get_anim_instance().is_slot_active('DefaultSlot')
    assert server.throwable.throws_released==before
    tsl_test['results'].append(dict(case='cancel_preserves_slide',no_inventory_spent=True))
    tsl_key(p,'H',True);yield .25
    assert p.throwable.phase==u.CRThrowPhase.AIMING
    tsl_key(p,'C',True);yield .07;tsl_key(p,'C',False);yield .25
    assert not p.character_movement.is_sliding() and not server.character_movement.is_sliding()
    assert p.throwable.phase==server.throwable.phase==u.CRThrowPhase.AIMING and p.throwable.preview_visible
    tsl_key(p,'H',False);yield .5
    assert server.throwable.throws_released==before+1
    tsl_test['results'].append(dict(case='aim_survives_slide_exit',one_release=True))

def tsl_finish(error=None):
    u.unregister_slate_post_tick_callback(tsl_test['handle']);tsl_test.update(finished=True,error=error)
    try:
        p,_=tsl_context()
        if error:
            (tsl_root/'Artifacts/Throw/slide-pose-debug.txt').write_text(u.CRBlueprintTools.describe_object(p.mesh.get_anim_instance()))
            location=p.get_actor_location()+u.Vector(300,-320,100)
            camera=u.CRBlueprintTools.spawn_pie_test_actor(p,u.SceneCapture2D,u.Transform(location=location))
            camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(location,p.get_actor_location()),False)
            capture=camera.get_component_by_class(u.SceneCaptureComponent2D)
            flag=u.EngineShowFlagsSetting();flag.set_editor_properties(dict(show_flag_name='Lighting',enabled=False))
            capture.set_editor_properties(dict(capture_every_frame=False,capture_on_movement=False,fov_angle=60,show_flag_settings=[flag],capture_source=u.SceneCaptureSource.SCS_FINAL_COLOR_LDR))
            target=u.RenderingLibrary.create_render_target2d(p,1200,760,u.TextureRenderTargetFormat.RTF_RGBA8)
            capture.set_editor_property('texture_target',target);capture.capture_scene()
            u.RenderingLibrary.export_render_target(p,target,str(tsl_root/'Artifacts/Throw'),'SlidePoseDebug.png');camera.destroy_actor()
        for key in ['W','A','S','D','LeftShift','C','H','Q','Z','X']:tsl_key(p,key,False)
    except Exception:pass
    (tsl_root/'Artifacts/Throw'/tsl_test['report']).write_text(json.dumps(dict(passed=error is None,error=error,results=tsl_test['results']),indent=2)+'\n')
    print('THROW_SLIDE',error)

tsl_generator=tsl_run()
def tsl_tick(dt):
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    if not worlds or tsl_test['busy']:return
    now=u.GameplayStatics.get_time_seconds(worlds[0])
    if now<tsl_test['next']:return
    tsl_test['busy']=True
    try:
        assert time.monotonic()<tsl_test['deadline'],'Slide throw tests timed out'
        tsl_test['next']=now+next(tsl_generator)
    except StopIteration:tsl_finish()
    except Exception:tsl_finish(traceback.format_exc())
    finally:tsl_test['busy']=False
tsl_test['handle']=u.register_slate_post_tick_callback(tsl_tick)
print('THROW_SLIDE_STARTED')
