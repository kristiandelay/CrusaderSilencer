"""Real weapon inputs, Chaos fracture, replicated state, and grenade/smoke checks."""
import json,time,traceback
from pathlib import Path
import unreal as u

dt_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
dt_test=dict(next=0,busy=False,results=[],deadline=time.monotonic()+650,report='standalone.json')
dt_catalog=json.loads((dt_root/'resources/DestructionRange.json').read_text())['targets']

def dt_key(p,key,down):
    k=u.Key();assert k.import_text(key);u.CRBlueprintTools.inject_pie_key(p,k,down)

def dt_context():
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    pawns=[p for w in worlds for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter)
           if isinstance(p.get_controller(),u.PlayerController) and not p.crowd_agent.enabled]
    p=next(p for p in pawns if p.is_locally_controlled() and (not p.has_authority() if len(worlds)>1 else True))
    server=next(p for p in pawns if p.has_authority() and not p.is_locally_controlled()) if len(worlds)>1 else p
    return p,server

def dt_capture(w,name,location,target):
    a=u.CRBlueprintTools.spawn_pie_test_actor(w,u.SceneCapture2D,u.Transform(location=location))
    a.set_actor_rotation(u.MathLibrary.find_look_at_rotation(location,target),False)
    c=a.get_component_by_class(u.SceneCaptureComponent2D)
    c.set_editor_property('capture_every_frame',False);c.set_editor_property('capture_on_movement',False)
    c.set_editor_property('fov_angle',70.);c.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    tex=u.RenderingLibrary.create_render_target2d(w,1500,1000,u.TextureRenderTargetFormat.RTF_RGBA8)
    c.set_editor_property('texture_target',tex);c.capture_scene()
    u.RenderingLibrary.export_render_target(w,tex,str(dt_root/'Artifacts/Destruction'),name+'.png');a.destroy_actor()

def dt_run():
    while True:
        try:p,s=dt_context();break
        except StopIteration:yield .2
    while not p.physical_interaction.controls_created or not s.physical_interaction.controls_created:yield .2
    net=p!=s
    if net:dt_test['report']='network.json'
    sw=s.get_world();cw=p.get_world()
    p.get_controller().set_ignore_look_input(True)
    p.get_controller().set_ignore_move_input(True)
    targets={a.get_actor_label():a for a in u.GameplayStatics.get_all_actors_of_class(sw,u.CRDestructibleActor) if a.actor_has_tag('CrusaderDestructionRange')}
    clients={a.get_actor_label():a for a in u.GameplayStatics.get_all_actors_of_class(cw,u.CRDestructibleActor) if a.actor_has_tag('CrusaderDestructionRange')}
    assert len(targets)==len(dt_catalog)==19,(len(targets),len(dt_catalog))
    # Initial pieces must stay intact without a shot or explosion.
    yield 2.
    assert all(a.local_break_events==0 for a in targets.values()),[(k,a.local_break_events) for k,a in targets.items() if a.local_break_events]
    dt_test['results'].append(dict(case='intact_at_start',count=len(targets)))
    if not net:
        dt_capture(sw,'RangeOverview',u.Vector(-2800,-2180,3600),u.Vector(-4300,-6600,140));yield .3

    def equip(kind):
        current=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
        if current and current.effects_profile.get_name()=='FX_'+kind:return
        for slot,item in enumerate(s.get_controller().quick_bar.get_slots()):
            if item and (kind+'_C' in u.CRBlueprintTools.describe_object(item) or (kind=='Rifle' and 'ID_BlackIronRifle_C' in u.CRBlueprintTools.describe_object(item))):
                # Use the real input path for an owned weapon. Python calls to
                # reflected RPC implementations bypass normal network routing.
                for attempt in range(4):
                    active=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
                    if active and active.effects_profile.get_name()=='FX_'+kind:return
                    dt_key(p,'Tab',True);yield .06;dt_key(p,'Tab',False);yield .6
                until=u.GameplayStatics.get_time_seconds(p)+4.
                while True:
                    yield .1
                    active=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
                    if active and active.effects_profile.get_name()=='FX_'+kind:break
                    assert u.GameplayStatics.get_time_seconds(p)<until,('Weapon switch timeout',kind,slot,u.CRBlueprintTools.describe_object(item),active.effects_profile.get_name() if active else None)
                return
        pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(sw,u.BaselineWeaponPickup)
                    if a.get_actor_label()=='CR_Destruction_Pickup_'+kind)
        loc=pickup.get_actor_location();s.set_actor_location(u.Vector(loc.x-100,loc.y,94),False,True);s.force_net_update()
        yield .7
        s.baseline_equipment.server_pickup(pickup);yield 1.
        assert p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).effects_profile.get_name()=='FX_'+kind

    cases=dt_catalog[:15] if not net else [dt_catalog[i] for i in [0,3,4,6,8,12]]
    for index,row in enumerate(cases):
        kind=['Rifle','Pistol','Shotgun'][index%3] if net else ('Pistol' if index==12 else 'Shotgun' if index==13 else 'Rifle')
        yield from equip(kind)
        a=targets[row['actor']];client=clients[row['actor']]
        s.character_movement.stop_movement_immediately();s.set_actor_location(u.Vector(*row['standing']),False,True)
        s.set_actor_rotation(u.Rotator(yaw=-90),False);s.force_net_update()
        p.get_controller().set_control_rotation(u.Rotator(yaw=-90));yield .5
        dt_key(p,'RightMouseButton',True)
        aim=u.Vector(*row['target'])
        dt_test['aim']=aim
        for _ in range(12):
            cam=u.GameplayStatics.get_player_camera_manager(cw,0).get_camera_location()
            p.get_controller().set_control_rotation(u.MathLibrary.find_look_at_rotation(cam,aim));yield .08
        before=a.weapon_hits;local_before=a.local_break_events;client_before=client.local_break_events
        client_transforms_before=[u.Vector(t.translation.x,t.translation.y,t.translation.z) for t in client.get_destructible_geometry().get_current_transforms()]
        count=0
        while a.local_break_events==local_before and count<10:
            dt_key(p,'LeftMouseButton',True);yield .001;dt_key(p,'LeftMouseButton',False)
            yield .65;count+=1
        record=dict(case='weapon_fracture',name=row['name'],weapon=kind,trigger_presses=count,
                    server_hits=a.weapon_hits-before,server_breaks=a.local_break_events-local_before,
                    client_hits=client.weapon_hits,client_breaks=client.local_break_events-client_before)
        dt_test['results'].append(record)
        assert record['server_hits']>0,('Weapon did not reach toolkit',record,[(h.position,h.surface) for h in p.weapon_effects.last_impacts])
        assert record['server_breaks']>0,('Hit did not fracture',record)
        if net:
            yield 1.
            assert client.weapon_hits==a.weapon_hits,('Hit state not replicated',record)
            # The receiving solver must have actually changed its piece transforms.
            transforms=client.get_destructible_geometry().get_current_transforms()
            record['client_transform_count']=len(transforms)
            record['client_breaks']=client.local_break_events-client_before
            record['client_piece_motion_cm']=max((t.translation-b).length() for t,b in zip(transforms,client_transforms_before))
            assert record['client_piece_motion_cm']>3,('Client pieces did not move',record)
            assert client.received_break_effects>0,('Client did not receive break effects',record)
            record['client_break_effect_updates']=client.received_break_effects
        dt_test.pop('aim',None)
        dt_key(p,'RightMouseButton',False);yield .3

    # Drive an actual thrown object through its fuse/detonation path, near a
    # clean test cluster. Only its initial fixture position is controlled here.
    blast=targets['CR_Destruction_Blast_Table'];other=targets['CR_Destruction_Small_Window']
    origin=u.Vector(-4480,-8690,35)
    s.set_actor_location(u.Vector(-4480,-8240,94),False,True);s.force_net_update();yield .5
    p.get_controller().set_control_rotation(u.Rotator(pitch=-15,yaw=-90))
    if p.throwable.selected_type!=u.CRThrowableType.GRENADE:
        dt_key(p,'X',True);yield .08;dt_key(p,'X',False);yield .2
    dt_key(p,'H',True);yield .4;dt_key(p,'H',False);yield .35
    g=next(a for a in u.GameplayStatics.get_all_actors_of_class(sw,u.CRThrownObject) if a.type==u.CRThrowableType.GRENADE and not a.detonated)
    g.movement.stop_movement_immediately();g.movement.deactivate();g.set_actor_location(origin,False,True);g.force_net_update()
    before=blast.local_break_events;outside=other.explosion_hits
    yield 3.0
    assert blast.explosion_hits>0 and blast.local_break_events>before,('Grenade did not fracture',blast.explosion_hits,blast.local_break_events)
    assert other.explosion_hits==outside,'Blast reached outside radius'
    if net:
        c=clients['CR_Destruction_Blast_Table'];assert c.explosion_hits==blast.explosion_hits and c.received_break_effects>0
    dt_test['results'].append(dict(case='grenade_fracture_and_range',hits=blast.explosion_hits,breaks=blast.local_break_events-before))
    # Aim from clear ground; airborne wreckage can legitimately obstruct a
    # throw from the edge of the blast bay. Move the released smoke back to
    # that bay to test its non-destructive detonation beside the same objects.
    s.character_movement.stop_movement_immediately();s.set_actor_location(u.Vector(5000,2500,94),False,True)
    s.force_net_update();p.get_controller().set_control_rotation(u.Rotator());yield .7
    dt_key(p,'X',True);yield .08;dt_key(p,'X',False);yield .2
    assert p.throwable.selected_type==u.CRThrowableType.SMOKE
    assert p.throwable.can_begin_aim(),('Smoke aim unavailable',p.throwable.phase,p.physical_interaction.is_busy(),p.get_component_by_class(u.LyraHealthComponent).get_health())
    dt_key(p,'H',True);yield .4
    assert p.throwable.phase==u.CRThrowPhase.AIMING and not p.throwable.launch_blocked,('Smoke aim obstructed',p.throwable.phase,p.throwable.launch_blocked)
    dt_key(p,'H',False);yield .35
    smoke=next((a for a in u.GameplayStatics.get_all_actors_of_class(sw,u.CRThrownObject) if a.type==u.CRThrowableType.SMOKE and not a.detonated),None)
    assert smoke,('Smoke did not release',p.throwable.phase,s.throwable.phase,s.throwable.throws_released)
    smoke.movement.stop_movement_immediately();smoke.movement.deactivate();smoke.set_actor_location(origin,False,True)
    counts=[a.explosion_hits for a in targets.values()];yield 1.6
    assert smoke.detonated and counts==[a.explosion_hits for a in targets.values()]
    dt_test['results'].append(dict(case='smoke_does_not_destroy'))
    if not net:
        dt_capture(sw,'AfterDestruction',u.Vector(-2800,-2180,3600),u.Vector(-4300,-6600,140));yield .3

def dt_finish(error=None):
    u.unregister_slate_post_tick_callback(dt_test['handle']);dt_test.update(finished=True,error=error)
    try:
        p,_=dt_context()
        for key in ['LeftMouseButton','RightMouseButton','H','X']:dt_key(p,key,False)
        p.get_controller().set_ignore_look_input(False);p.get_controller().set_ignore_move_input(False)
    except Exception:pass
    (dt_root/'Artifacts/Destruction'/dt_test['report']).write_text(json.dumps(dict(passed=error is None,error=error,results=dt_test['results']),indent=2))
    print('DESTRUCTION_TEST_FINISHED',error)

dt_generator=dt_run()
def dt_tick(delta):
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    if not worlds or dt_test['busy']:return
    now=u.GameplayStatics.get_time_seconds(worlds[0])
    if dt_test.get('aim') is not None:
        p,_=dt_context()
        cam=u.GameplayStatics.get_player_camera_manager(p.get_world(),0).get_camera_location()
        p.get_controller().set_control_rotation(u.MathLibrary.find_look_at_rotation(cam,dt_test['aim']))
    if now<dt_test['next']:return
    dt_test['busy']=True
    try:
        assert time.monotonic()<dt_test['deadline'],'Destruction test timeout'
        dt_test['next']=now+next(dt_generator)
    except StopIteration:dt_finish()
    except Exception:dt_finish(traceback.format_exc())
    finally:dt_test['busy']=False
dt_test['handle']=u.register_slate_post_tick_callback(dt_tick)
