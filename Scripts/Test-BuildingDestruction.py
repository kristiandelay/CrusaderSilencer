"""Exercise real furniture placements, weapons, grenade, navigation and replication."""
import json,time,traceback
from pathlib import Path
import unreal as u

bt_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
# Reuse input/owner helpers; don't start the separate destruction-range test.
exec(compile((bt_root/'Scripts/Test-Destruction.py').read_text().split('def dt_run():')[0],
             'DestructionHelpers','exec'),globals())
bt_test=dict(next=0,busy=False,results=[],deadline=time.monotonic()+650,report='standalone.json')
bt_manifest=json.loads((bt_root/'resources/BuildingDestruction.json').read_text())

def bt_nav(a):
    row=next(r for r in bt_manifest['targets'] if r['actor']==a.get_actor_label())
    point=u.Vector(row['center'][0],row['center'][1],40)
    # The freight crate overlaps the checkpoint crate's padded navigation box.
    # Probe its north half so the surviving neighbor cannot mask its removal.
    if a.get_actor_label()=='CR_Breakable_Facility_FreightSupplies_0':point.y+=55
    projected=u.NavigationSystemV1.project_point_to_navigation(a.get_world(),point,None,None,u.Vector(3,3,40))
    return projected is None

def bt_capture(w,name):
    a=u.CRBlueprintTools.spawn_pie_test_actor(w,u.SceneCapture2D,u.Transform(location=u.Vector(13300,8680,265)))
    a.set_actor_rotation(u.MathLibrary.find_look_at_rotation(a.get_actor_location(),u.Vector(13830,9220,115)),False)
    c=a.get_component_by_class(u.SceneCaptureComponent2D)
    c.set_editor_property('capture_every_frame',False);c.set_editor_property('capture_on_movement',False)
    c.set_editor_property('fov_angle',90.);c.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    tex=u.RenderingLibrary.create_render_target2d(w,1400,900,u.TextureRenderTargetFormat.RTF_RGBA8)
    c.set_editor_property('texture_target',tex);c.capture_scene()
    u.RenderingLibrary.export_render_target(w,tex,str(bt_root/'Artifacts/BuildingDestruction'),name+'.png');a.destroy_actor()

def bt_run():
    while True:
        try:p,s=dt_context();break
        except StopIteration:yield .2
    while not p.physical_interaction.controls_created or not s.physical_interaction.controls_created:yield .2
    sw=s.get_world();cw=p.get_world();net=p!=s
    bt_test['player']=p
    # Keep the firing fixture alive while nearby guards react normally to shots.
    u.SystemLibrary.execute_console_command(sw,'God',s.get_controller())
    if net:bt_test['report']='network.json'
    p.get_controller().set_ignore_look_input(True);p.get_controller().set_ignore_move_input(True)
    targets={a.get_actor_label():a for a in u.GameplayStatics.get_all_actors_of_class(sw,u.CRDestructibleActor) if a.actor_has_tag('CrusaderBuildingDestruction')}
    clients={a.get_actor_label():a for a in u.GameplayStatics.get_all_actors_of_class(cw,u.CRDestructibleActor) if a.actor_has_tag('CrusaderBuildingDestruction')}
    assert len(targets)==len(bt_manifest['targets'])==27
    # The first solver update converts rest-bone transforms into simulation
    # transforms. Measure subsequent settling in that consistent space.
    yield 1.5
    initial={k:[u.Vector(t.translation.x,t.translation.y,t.translation.z) for t in a.get_destructible_geometry().get_current_transforms()] for k,a in targets.items()}
    npcs=[a for a in u.GameplayStatics.get_all_actors_of_class(sw,u.CRTraversalCharacter)
          if a.get_actor_label().startswith(('CR_FacilityCrowd_','CR_ControlCrowd_'))]
    tracks={a.get_actor_label():a.get_actor_location() for a in npcs}
    # Cross the debris cleanup window as well: an untouched sleeping object
    # must remain present instead of being treated as disposable debris.
    yield 22.
    assert all(a.local_break_events==0 for a in targets.values()),[(k,a.local_break_events) for k,a in targets.items() if a.local_break_events]
    assert all(bt_nav(a) for a in targets.values()),'Intact furniture missing navigation exclusion'
    drift=max((t.translation-b).length() for k,a in targets.items() for t,b in zip(a.get_destructible_geometry().get_current_transforms(),initial[k]))
    assert drift<12,('Furniture moved before damage',drift)
    for row in bt_manifest['targets']:
        center,_=targets[row['actor']].get_actor_bounds(False)
        assert (center-u.Vector(*row['center'])).length()<15,('Furniture shifted from placement',row['actor'],str(center))
    bt_test['results'].append(dict(case='27_intact_stable_navigation_obstacles',count=len(targets),maximum_settling_cm=drift))
    areas=[a for a in u.GameplayStatics.get_all_actors_of_class(sw,u.CRCrowdArea)
           if a.get_actor_label().startswith(('CR_FacilityCrowd_','CR_ControlCrowd_'))]
    routes=0
    for area in areas:
        for neighbour in area.neighbours:
            path=u.NavigationSystemV1.find_path_to_location_synchronously(sw,area.get_actor_location(),neighbour.get_actor_location())
            assert path and path.is_valid() and not path.is_partial(),('Blocked crowd route',area.get_actor_label(),neighbour.get_actor_label())
            routes+=1
    assert routes>0 and npcs
    bt_test['results'].append(dict(case='building_crowd_routes',complete_routes=routes,npcs=len(npcs)))
    if not net:bt_capture(sw,'OfficeBefore');yield .1

    def equip(kind):
        current=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
        if current and current.effects_profile.get_name()=='FX_'+kind:return
        pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(sw,u.BaselineWeaponPickup) if a.get_actor_label()=='CR_Destruction_Pickup_'+kind)
        loc=pickup.get_actor_location();s.set_actor_location(loc+u.Vector(-100,0,45),False,True);s.force_net_update();yield .5
        s.baseline_equipment.server_pickup(pickup);yield 1.
        assert p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).effects_profile.get_name()=='FX_'+kind

    # Clear firing positions inside the existing buildings, not isolated mesh copies.
    cases=[('Facility_OfficeDesk',(13770,8500,124),'Rifle'),
        ('Facility_OfficeChair',(13500,9300,124),'Rifle'),
        ('Facility_OfficeDrawer',(14150,9100,124),'Rifle'),
        ('Facility_LabSupplyA',(11150,8850,124),'Rifle'),
        ('Facility_ContainmentCrate',(12950,9250,124),'Rifle'),
        ('Facility_OfficeCrate',(13800,8620,124),'Rifle'),
        ('ControlRoom_CommandTerminal_0',(19970,9330,124),'Rifle'),
        ('ControlRoom_OperationsCrate_0',(19400,8050,124),'Pistol'),
        ('ControlRoom_ServiceLocker_0',(17910,7810,124),'Pistol'),
        ('ControlRoom_StorageBarrel_2',(23000,8200,124),'Shotgun'),
        ('ControlRoom_StorageCrate_2',(23000,7770,124),'Shotgun')]
    if net:cases=[cases[i] for i in [0,1,7,9]]
    for name,standing,kind in cases:
        yield from equip(kind)
        # Use normal reload input so a long furniture sweep does not run out
        # halfway through a test and mistake an empty magazine for a bad hit.
        dt_key(p,'R',True);yield .06;dt_key(p,'R',False);yield 2.
        a=targets['CR_Breakable_'+name];client=clients[a.get_actor_label()]
        s.character_movement.stop_movement_immediately();s.set_actor_location(u.Vector(*standing),False,True);s.force_net_update()
        center,extent=a.get_actor_bounds(False)
        aim=center
        if name=='Facility_OfficeDesk':aim=u.Vector(13730,9020,136)
        if name=='Facility_OfficeChair':aim.z=center.z+extent.z*.65
        if name=='Facility_OfficeDrawer':aim.z=95
        bt_test['aim']=aim
        bt_test['tracking_actor']=client
        bt_test['aim_fraction']=u.Vector((aim.x-center.x)/max(extent.x,1.),(aim.y-center.y)/max(extent.y,1.),(aim.z-center.z)/max(extent.z,1.))
        p.get_controller().set_control_rotation(u.MathLibrary.find_look_at_rotation(p.get_actor_location(),aim));yield .6
        dt_key(p,'RightMouseButton',True);yield 1.
        before=a.weapon_hits;breaks=a.local_break_events
        client_before=[u.Vector(t.translation.x,t.translation.y,t.translation.z) for t in client.get_destructible_geometry().get_current_transforms()]
        for attempt in range(10):
            dt_key(p,'LeftMouseButton',True);yield .04;dt_key(p,'LeftMouseButton',False);yield .6
            if a.local_break_events>breaks:break
        record=dict(case='placed_furniture_shot',actor=name,weapon=kind,hits=a.weapon_hits-before,breaks=a.local_break_events-breaks)
        bt_test['results'].append(record)
        assert record['hits']>0 and record['breaks']>0,(record,[(str(h.position),str(h.surface)) for h in p.weapon_effects.last_impacts])
        yield .8
        nav_deadline=u.GameplayStatics.get_time_seconds(sw)+6.
        while bt_nav(a) and u.GameplayStatics.get_time_seconds(sw)<nav_deadline:yield .25
        assert not bt_nav(a),('Broken object still excludes navigation',name,
            str(a.intact_navigation),[c.get_path_name() for c in a.get_components_by_class(u.CRDestructibleNavigation)])
        if not net and name=='Facility_OfficeDesk':bt_capture(sw,'OfficeBreaking')
        if net:
            record['client_motion_cm']=max((t.translation-b).length() for t,b in zip(client.get_destructible_geometry().get_current_transforms(),client_before))
            assert record['client_motion_cm']>3 and client.weapon_hits==a.weapon_hits and client.received_break_effects>0,record
        bt_test.pop('aim',None);bt_test.pop('tracking_actor',None);dt_key(p,'RightMouseButton',False);yield .2
    if not net:bt_capture(sw,'OfficeAfter');yield .1

    # Detonate a real thrown grenade by the still-intact freight crate.
    blast=targets['CR_Breakable_Facility_FreightSupplies_0']
    remote=targets['CR_Breakable_ControlRoom_CommandTerminal_1']
    s.set_actor_location(u.Vector(5000,2500,94),False,True);s.force_net_update();yield .7
    p.get_controller().set_control_rotation(u.Rotator(pitch=-15,yaw=0))
    dt_key(p,'H',True);yield .4;dt_key(p,'H',False);yield .35
    g=next(a for a in u.GameplayStatics.get_all_actors_of_class(sw,u.CRThrownObject) if a.type==u.CRThrowableType.GRENADE and not a.detonated)
    center,extent=blast.get_actor_bounds(False)
    g.movement.stop_movement_immediately();g.movement.deactivate()
    g.set_actor_location(center+u.Vector(0,extent.y+90,0),False,True);g.force_net_update()
    before=blast.local_break_events;outside=remote.explosion_hits;yield 3.
    # The fuse, Chaos notification and asynchronous nav tile rebuild finish on
    # separate frames. Wait for the same completed state as the weapon cases.
    blast_deadline=u.GameplayStatics.get_time_seconds(sw)+6.
    while (blast.local_break_events<=before or bt_nav(blast)) and u.GameplayStatics.get_time_seconds(sw)<blast_deadline:yield .25
    assert blast.explosion_hits>0 and blast.local_break_events>before and not blast.intact_navigation and not bt_nav(blast),dict(
        hits=blast.explosion_hits,breaks=blast.local_break_events-before,nav_blocked=bt_nav(blast))
    assert remote.explosion_hits==outside
    if net:assert clients[blast.get_actor_label()].received_break_effects>0
    bt_test['results'].append(dict(case='building_grenade',hits=blast.explosion_hits,breaks=blast.local_break_events-before))
    moving=[a.get_actor_label() for a in npcs if (a.get_actor_location()-tracks[a.get_actor_label()]).length()>150]
    assert len(moving)>=len(npcs)//2,('Crowd stopped moving',moving)
    bt_test['results'].append(dict(case='crowd_continues_moving',moving=len(moving),total=len(npcs)))
    bt_test['completed']=True

def bt_finish(error=None):
    u.unregister_slate_post_tick_callback(bt_test['handle']);bt_test.update(finished=True,error=error)
    try:
        p,_=dt_context()
        for key in ['LeftMouseButton','RightMouseButton','H','R']:dt_key(p,key,False)
        p.get_controller().set_ignore_look_input(False);p.get_controller().set_ignore_move_input(False)
    except Exception:pass
    (bt_root/'Artifacts/BuildingDestruction'/bt_test['report']).write_text(json.dumps(dict(passed=error is None,error=error,results=bt_test['results']),indent=2))
    print('BUILDING_DESTRUCTION_TEST_FINISHED',error)

bt_generator=bt_run()
def bt_tick(delta):
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    if not worlds or bt_test['busy']:return
    now=u.GameplayStatics.get_time_seconds(worlds[0])
    bt_test['busy']=True
    try:
        if bt_test.get('aim') is not None:
            p=bt_test['player'];assert p.get_controller(),'Test shooter died or lost possession'
            cam=u.GameplayStatics.get_player_camera_manager(p.get_world(),0).get_camera_location()
            target=bt_test.get('tracking_actor')
            if target:
                # Debris can move or tip other furniture. Follow a visible
                # solid part of its current collision, as a player would, instead
                # of continuing to fire at its pre-impact position or empty seat.
                center,extent=target.get_actor_bounds(False)
                fraction=bt_test['aim_fraction']
                points=[center+u.Vector(extent.x*fraction.x,extent.y*fraction.y,extent.z*fraction.z),center]
                points += [center+u.Vector(extent.x*x,extent.y*y,extent.z*z)
                           for z in [.4,-.4,.7] for x in [0.,-.5,.5] for y in [0.,-.5,.5]]
                bt_test['aim']=points[0]
                for point in points:
                    hit=u.SystemLibrary.line_trace_single(p,cam,cam+(point-cam)*1.1,
                        u.TraceTypeQuery.TRACE_TYPE_QUERY1,False,[p]+list(p.get_attached_actors()),u.DrawDebugTrace.NONE)
                    if hit and hit.to_tuple()[9]==target:
                        bt_test['aim']=point;break
            p.get_controller().set_control_rotation(u.MathLibrary.find_look_at_rotation(cam,bt_test['aim']))
        if now<bt_test['next']:return
        assert time.monotonic()<bt_test['deadline'],'Furniture test timeout'
        bt_test['next']=now+next(bt_generator)
    except StopIteration:bt_finish(None if bt_test.get('completed') else 'Test ended before all furniture cases completed')
    except Exception:bt_finish(traceback.format_exc())
    finally:bt_test['busy']=False
bt_test['handle']=u.register_slate_post_tick_callback(bt_tick)
