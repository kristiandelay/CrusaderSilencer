"""Verify camera input and collision retraction against the actual course."""
camera_test = {'phase': 'clear', 'next':0, 'result':{}, 'busy':False}

def camera_finish(error=None):
    u.unregister_slate_post_tick_callback(camera_test['handle'])
    report = {'passed':error is None,'error':error,**camera_test['result']}
    output=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/GymTests/camera.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2))
    u.log('CR_GYM_CAMERA_RESULT '+json.dumps(report))

def camera_tick(dt):
    if camera_test['busy']:
        return
    camera_test['busy']=True
    try:
        world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
        now=u.GameplayStatics.get_time_seconds(world)
        if now<camera_test['next']:return
        pawn=u.GameplayStatics.get_player_pawn(world,0)
        controller=pawn.get_controller()
        phase=camera_test['phase']
        if phase=='clear':
            pawn.character_movement.stop_movement_immediately()
            pawn.set_actor_location(u.Vector(2100,-1100,94),False,True)
            controller.set_control_rotation(u.Rotator(pitch=0,yaw=0,roll=0))
            camera_test.update(phase='look',next=now+1,started=now+1)
        elif phase=='look':
            if now-camera_test['started'] < .3:
                subs=[s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==controller]
                assert len(subs)==1
                subs[0].inject_input_vector_for_action(u.load_asset('/Game/Input/IA_Look'),u.Vector(3,1,0),[],[])
            else:
                rotation=controller.get_control_rotation()
                assert abs(rotation.yaw)>10 and abs(rotation.pitch)>1
                camera_test['result']['look_rotation']={'yaw':rotation.yaw,'pitch':rotation.pitch}
                controller.set_control_rotation(u.Rotator(pitch=0,yaw=0,roll=0))
                camera_test.update(phase='measure_clear',next=now+1)
        elif phase=='measure_clear':
            p=pawn.get_actor_location(); c=controller.player_camera_manager.get_camera_location()
            distance=((c.x-p.x)**2+(c.y-p.y)**2)**.5
            assert distance>290
            camera_test['result']['clear_horizontal_distance_cm']=distance
            pawn.set_actor_location(u.Vector(5000,-800,94),False,True)
            camera_test.update(phase='measure_blocked',next=now+1)
        elif phase=='measure_blocked':
            p=pawn.get_actor_location(); c=controller.player_camera_manager.get_camera_location()
            distance=((c.x-p.x)**2+(c.y-p.y)**2)**.5
            assert distance<200, 'Camera did not retract behind the course obstacle: '+str(distance)
            camera_test['result']['blocked_horizontal_distance_cm']=distance
            pawn.set_actor_location(u.Vector(2100,-1100,94),False,True)
            controller.set_control_rotation(u.Rotator(pitch=-10,yaw=0,roll=0))
            camera_finish()
    except Exception:
        camera_finish(traceback.format_exc())
    finally:
        camera_test['busy']=False

camera_test['handle']=u.register_slate_post_tick_callback(camera_tick)
print('Started camera input/retraction check')
