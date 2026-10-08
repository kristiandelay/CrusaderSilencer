"""Real movement input while holding H, upper/lower body separation and moving releases."""
import json,math,time,traceback
from pathlib import Path
import unreal as u

tm_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
tm_test=dict(next=0,busy=False,results=[],deadline=time.monotonic()+200,report='movement.json',observe_release=False)

def tm_key(p,name,down):
    key=u.Key();assert key.import_text(name);u.CRBlueprintTools.inject_pie_key(p,key,down)

def tm_context():
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    pawns=[p for w in worlds for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if isinstance(p.get_controller(),u.PlayerController) and not p.crowd_agent.enabled]
    p=next(p for p in pawns if p.is_locally_controlled() and (not p.has_authority() if len(worlds)>1 else True))
    server=next(p for p in pawns if p.has_authority() and not p.is_locally_controlled()) if len(worlds)>1 else p
    return p,server

def tm_pose(p,left):
    hand='hand_l' if left else 'hand_r';other='hand_r' if left else 'hand_l'
    mesh=p.baseline_equipment.get_presentation_mesh()
    floor=p.get_actor_location().z-p.capsule_component.get_scaled_capsule_half_height()
    # GASP lowers the pelvis during starts and strides; stationary aim is >70 cm.
    assert mesh.get_socket_location('pelvis').z-floor>55,('Pelvis collapsed while walking',mesh.get_socket_location('pelvis').z-floor,p.mesh.get_socket_location('pelvis').z-floor,p.get_velocity())
    assert mesh.get_socket_location(hand).z-mesh.get_socket_location(other).z>15,'Throw arm lost its aim pose'
    held=next(c for c in p.get_components_by_class(u.StaticMeshComponent) if c.static_mesh and c.static_mesh.get_name() in ['SM_Grenade','SM_Smoke'])
    assert held.is_visible() and str(held.get_attach_socket_name())==hand
    return [(m.get_socket_location('foot_r')-m.get_socket_location('pelvis')) for m in [p.mesh,mesh]]

def tm_cancel(p):
    for key in ['W','A','S','D']:tm_key(p,key,False)
    tm_key(p,'Z',True)
    yield .08
    tm_key(p,'Z',False);tm_key(p,'H',False)
    yield .35

def tm_capture(p,left):
    location=p.get_actor_location()+u.Vector(300,-320,100)
    camera=u.CRBlueprintTools.spawn_pie_test_actor(p,u.SceneCapture2D,u.Transform(location=location))
    camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(location,p.get_actor_location()+u.Vector(0,0,5)),False)
    c=camera.get_component_by_class(u.SceneCaptureComponent2D)
    c.set_editor_properties(dict(capture_every_frame=False,capture_on_movement=False,fov_angle=60,capture_source=u.SceneCaptureSource.SCS_FINAL_COLOR_LDR))
    target=u.RenderingLibrary.create_render_target2d(p,1200,760,u.TextureRenderTargetFormat.RTF_RGBA8)
    c.set_editor_property('texture_target',target);c.capture_scene()
    u.RenderingLibrary.export_render_target(p,target,str(tm_root/'Artifacts/Throw'),'ThrowWalking'+('Left' if left else 'Right')+'.png')
    camera.destroy_actor()

def tm_run():
    while True:
        try:p,server=tm_context();break
        except StopIteration:yield .2
    while not p.physical_interaction.controls_created or not server.physical_interaction.controls_created:yield .2
    if p!=server:tm_test['report']='movement-network.json'
    pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(server.get_world(),u.BaselineWeaponPickup) if 'Rifle' in a.item_definition.get_name())
    pos=pickup.get_actor_location();server.set_actor_location(pos+u.Vector(-110,0,94-pos.z),False,True);server.baseline_equipment.server_pickup(pickup)
    yield 1
    directions=[(['W'],0),(['W','D'],45),(['D'],90),(['S','D'],135),(['S'],180),(['S','A'],225),(['A'],270),(['W','A'],315)]
    for index,(keys,angle) in enumerate(directions):
        left=bool(index%2);kind=u.CRThrowableType.SMOKE if index%4>=2 else u.CRThrowableType.GRENADE
        server.character_movement.stop_movement_immediately();server.set_actor_location(u.Vector(5000,2500,94),False,True)
        server.set_actor_rotation(u.Rotator(yaw=0),False);server.force_net_update();p.get_controller().set_control_rotation(u.Rotator(yaw=0))
        yield .5
        if p.baseline_equipment.is_left_shoulder()!=left:
            tm_key(p,'Q',True);yield .08;tm_key(p,'Q',False);yield .4
        if p.throwable.selected_type!=kind:
            tm_key(p,'X',True);yield .08;tm_key(p,'X',False);yield .2
        tm_key(p,'H',True);yield .35
        assert p.throwable.phase==server.throwable.phase==u.CRThrowPhase.AIMING
        start=p.get_actor_location();samples=[[],[]]
        for key in keys:tm_key(p,key,True)
        for sample in range(9):
            yield .1
            assert p.throwable.phase==server.throwable.phase==u.CRThrowPhase.AIMING
            for i,v in enumerate(tm_pose(p,left)):samples[i].append(v)
        delta=p.get_actor_location()-start;distance=math.hypot(delta.x,delta.y)
        dot=(delta.x*math.cos(math.radians(angle))+delta.y*math.sin(math.radians(angle)))/max(distance,1)
        assert distance>90 and dot>.92,('Movement blocked or wrong direction',keys,distance,dot)
        ranges=[max((a-b).length() for a in values for b in values) for values in samples]
        assert min(ranges)>15,('Frozen walking feet',ranges)
        assert server.get_velocity().length()>80,'Server did not move'
        assert p.throwable.preview_visible and not p.throwable.launch_blocked
        expected=p.get_actor_location()+u.Vector(38,-24 if left else 24,48)
        preview_error=(p.throwable.preview_points[0]-expected).length()
        assert preview_error<2,('Preview left behind moving pawn',preview_error)
        assert abs(u.MathLibrary.normalized_delta_rotator(p.get_actor_rotation(),p.get_base_aim_rotation()).yaw)<5,'Facing follows travel instead of aim'
        tm_test['results'].append(dict(case='aim_walk',keys=keys,left=left,type=str(kind),distance_cm=distance,direction_agreement=dot,foot_motion_cm=ranges,preview_origin_error_cm=preview_error))
        if p==server and index<2:
            tm_capture(p,left);yield .3
        yield from tm_cancel(p)
        assert server.throwable.throws_released==0,'Cancel consumed inventory'

    # Turn and transfer the object while walking, then release without stopping.
    for left in [False,True]:
        server.character_movement.stop_movement_immediately();server.set_actor_location(u.Vector(5000,2500,94),False,True)
        server.force_net_update();p.get_controller().set_control_rotation(u.Rotator(yaw=0));yield .5
        if p.baseline_equipment.is_left_shoulder()==left:
            tm_key(p,'Q',True);yield .08;tm_key(p,'Q',False);yield .4
        tm_key(p,'H',True);tm_key(p,'W',True);yield .5
        p.get_controller().set_control_rotation(u.Rotator(yaw=35));tm_key(p,'Q',True);yield .08;tm_key(p,'Q',False);yield .5
        tm_pose(p,left);tm_pose(server,left)
        assert p.throwable.is_left_throw_hand()==server.throwable.is_left_throw_hand()==left
        assert abs(u.MathLibrary.normalized_delta_rotator(p.get_actor_rotation(),u.Rotator(yaw=35)).yaw)<5
        before=server.throwable.throws_released;count=server.throwable.get_remaining();start=p.get_actor_location()
        tm_test.update(observe_release=True,release_sample=None,committed_position=server.get_actor_location(),release_left=left)
        tm_key(p,'H',False);yield .4
        assert p.throwable.phase==u.CRThrowPhase.THROWING and p.get_velocity().length()>80,'Movement stopped during release'
        assert (p.get_actor_location()-start).length()>50
        assert server.throwable.throws_released==before+1 and server.throwable.get_remaining()==count-1
        assert tm_test['release_sample'] is not None,'Release not observed'
        release=tm_test['release_sample']
        assert release['travel_before_release_cm']>15,'Fixture did not move during windup'
        assert release['current_origin_error_cm']<release['stale_origin_error_cm'],('Object spawned behind walking character',release)
        assert release['current_origin_error_cm']<2,release
        tm_test['observe_release']=False
        yield .7
        assert not p.throwable.is_busy() and not server.throwable.is_busy()
        tm_test['results'].append(dict(case='turn_swap_moving_release',left=left,**release))
        for key in ['W','A','S','D']:tm_key(p,key,False)
        for a in u.GameplayStatics.get_all_actors_of_class(server.get_world(),u.CRThrownObject):a.destroy_actor()
        yield .5

def tm_finish(error=None):
    u.unregister_slate_post_tick_callback(tm_test['handle']);tm_test.update(finished=True,error=error)
    try:
        p,_=tm_context()
        for key in ['W','A','S','D','H','Q','Z','X']:tm_key(p,key,False)
    except Exception:pass
    (tm_root/'Artifacts/Throw'/tm_test['report']).write_text(json.dumps(dict(passed=error is None,error=error,results=tm_test['results']),indent=2)+'\n')
    print('THROW_MOVEMENT',error)

tm_generator=tm_run()

def tm_tick(dt):
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    if not worlds or tm_test['busy']:return
    tm_test['busy']=True
    try:
        if tm_test['observe_release'] and tm_test['release_sample'] is None:
            p,server=tm_context()
            objects=u.GameplayStatics.get_all_actors_of_class(server.get_world(),u.CRThrownObject)
            if objects:
                a=objects[0];yaw=u.Rotator(yaw=35)
                offset=u.MathLibrary.get_forward_vector(yaw)*38+u.MathLibrary.get_right_vector(yaw)*(-24 if tm_test['release_left'] else 24)+u.Vector(0,0,48)
                expected=server.get_actor_location()+offset;stale=tm_test['committed_position']+offset
                # A newly spawned projectile can already have its first movement
                # tick. Recover its launch point from vertical velocity/gravity.
                velocity=a.movement.velocity;flight_time=max(0,(300-velocity.z)/980)
                origin=a.get_actor_location()-velocity*flight_time-u.Vector(0,0,490*flight_time*flight_time)
                tm_test['release_sample']=dict(current_origin_error_cm=(origin-expected).length(),stale_origin_error_cm=(origin-stale).length(),travel_before_release_cm=(server.get_actor_location()-tm_test['committed_position']).length(),projectile_age_seconds=flight_time)
        now=u.GameplayStatics.get_time_seconds(worlds[0])
        if now<tm_test['next']:return
        assert time.monotonic()<tm_test['deadline'],'Throw movement timed out'
        tm_test['next']=now+next(tm_generator)
    except StopIteration:tm_finish()
    except Exception:tm_finish(traceback.format_exc())
    finally:tm_test['busy']=False

tm_test['handle']=u.register_slate_post_tick_callback(tm_tick)
print('THROW_MOVEMENT_STARTED')
