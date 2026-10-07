"""Two-player listen-server PIE smoke test: owning-client pickup, fire, reload and drop."""
network={'phase':'place','next':0,'results':[],'busy':False,'deadline':time.monotonic()+180}
network_out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/BaselineTests/network.json'

def network_context():
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    assert len(worlds)==2
    pawns=[p for w in worlds for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if 'TrainingPartner' not in p.get_class().get_name()]
    client=next(p for p in pawns if p.is_locally_controlled() and not p.has_authority())
    server=next(p for p in pawns if p.has_authority() and not p.is_locally_controlled())
    host=next(p for p in pawns if p.has_authority() and p.is_locally_controlled())
    world=next(w for w in worlds if client in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter))
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
             if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==client.get_controller())
    return world,client,server,host,sub

def network_finish(error=None):
    u.unregister_slate_post_tick_callback(network['handle'])
    network['finished']=True
    try:
        _,_,_,_,sub=network_context()
        for name in ['Fire','Reload','Interact','Drop']:baseline_input(sub,name,(0,0,0))
    except Exception:pass
    network_out.parent.mkdir(parents=True,exist_ok=True)
    network_out.write_text(json.dumps({'passed':error is None,'error':error,'mode':'two-player listen-server PIE','results':network['results']},indent=2))

def network_tick(dt):
    if network['busy']:return
    network['busy']=True
    try:
        assert time.monotonic()<network['deadline'],'Network smoke timed out'
        world,client,server,host,sub=network_context()
        now=u.GameplayStatics.get_time_seconds(world)
        if now<network['next']:return
        equipment=client.get_component_by_class(u.BaselineEquipmentComponent)
        authority=server.get_component_by_class(u.BaselineEquipmentComponent)
        phase=network['phase']
        if phase=='place':
            host.set_actor_location(u.Vector(2500,-3200,94),False,True)
            server.set_actor_location(u.Vector(2100,-1100,94),False,True)
            client.get_controller().set_control_rotation(u.Rotator(pitch=-10,yaw=0,roll=0))
            network.update(phase='pick',next=now+1)
        elif phase=='pick':
            assert equipment.find_pickup()
            baseline_input(sub,'Interact',(1,0,0))
            network.update(phase='verify',next=now+2)
        elif phase=='verify':
            assert len(client.get_controller().inventory.get_all_items())==1
            assert len(server.get_controller().inventory.get_all_items())==1
            assert len(client.equipment_manager.get_equipment_instances_of_type(u.BaselineWeaponInstance))==1
            assert baseline_stats(equipment.get_active_item())==baseline_stats(authority.get_active_item())
            network['results'].append('client_pickup_inventory_equipment_and_ammo_replicated')
            network.update(phase='fire',started=now)
        elif phase=='fire':
            baseline_input(sub,'Fire',(1 if now-network['started']<1 else 0,0,0))
            if now-network['started']>=1:network.update(phase='verify_fire',next=now+1)
        elif phase=='verify_fire':
            stats=baseline_stats(equipment.get_active_item())
            assert 0<stats['MagazineAmmo']<30,stats
            assert stats==baseline_stats(authority.get_active_item())
            network['results'].append({'client_fire_and_server_ammo_agree':stats})
            baseline_input(sub,'Reload',(1,0,0))
            network.update(phase='verify_reload',next=now+4)
        elif phase=='verify_reload':
            stats=baseline_stats(equipment.get_active_item())
            assert stats['MagazineAmmo']==30 and stats['SpareAmmo']<60,stats
            assert stats==baseline_stats(authority.get_active_item())
            network['saved']=stats
            network['results'].append({'client_reload_and_server_ammo_agree':stats})
            baseline_input(sub,'Drop',(1,0,0))
            network.update(phase='verify_drop',next=now+2)
        elif phase=='verify_drop':
            assert not client.get_controller().inventory.get_all_items()
            assert not server.get_controller().inventory.get_all_items()
            assert not client.equipment_manager.get_equipment_instances_of_type(u.BaselineWeaponInstance)
            drops=[a for a in u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup) if a.get_editor_property('bHasSavedStats')]
            assert len(drops)==1
            location=drops[0].get_actor_location()
            assert location.z<70
            network['results'].append('client_drop_removes_equipment_and_replicates_world_pickup')
            server.set_actor_location(u.Vector(location.x-100,location.y,94),False,True)
            client.get_controller().set_control_rotation(u.Rotator(pitch=-10,yaw=0,roll=0))
            network.update(phase='repick',next=now+1)
        elif phase=='repick':
            assert equipment.find_pickup()
            baseline_input(sub,'Interact',(1,0,0))
            network.update(phase='verify_repick',next=now+1)
        elif phase=='verify_repick':
            assert baseline_stats(equipment.get_active_item())==network['saved']
            assert baseline_stats(authority.get_active_item())==network['saved']
            network['results'].append('client_recovery_preserves_server_ammo')
            network_finish()
    except Exception:network_finish(traceback.format_exc())
    finally:network['busy']=False

network['handle']=u.register_slate_post_tick_callback(network_tick)
print('Started owning-client equipment replication checks')
