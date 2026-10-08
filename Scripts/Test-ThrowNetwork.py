"""Owning client hold/release, replicated montage/projectile/fuse/inventory and smoke."""
import json,time,traceback
from pathlib import Path
import unreal as u
tn_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
tn_test=dict(next=0,busy=False,results=[],deadline=time.monotonic()+140)
def tn_key(p,name,down):
    key=u.Key();assert key.import_text(name);u.CRBlueprintTools.inject_pie_key(p,key,down)
def tn_context():
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    pawns=[p for w in worlds for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if isinstance(p.get_controller(),u.PlayerController) and not p.crowd_agent.enabled]
    client=next(p for p in pawns if p.is_locally_controlled() and not p.has_authority())
    server=next(p for p in pawns if p.has_authority() and not p.is_locally_controlled())
    return client,server
def tn_run():
    while True:
        try:p,server=tn_context();break
        except StopIteration:yield .2
    while not p.physical_interaction.controls_created or not server.physical_interaction.controls_created:yield .2
    server.set_actor_location(u.Vector(5000,2500,94),False,True);server.set_actor_rotation(u.Rotator(),False);server.force_net_update()
    p.get_controller().set_control_rotation(u.Rotator())
    yield 1
    for kind in [u.CRThrowableType.GRENADE,u.CRThrowableType.SMOKE]:
        if p.throwable.selected_type!=kind:
            tn_key(p,'X',True);yield .15;tn_key(p,'X',False);yield .2
        tn_key(p,'H',True);yield .6
        assert p.throwable.phase==server.throwable.phase==u.CRThrowPhase.AIMING
        assert p.throwable.preview_visible and not server.throwable.preview_visible,'Preview leaked to another connection'
        assert p.mesh.get_anim_instance().get_current_active_montage() and server.mesh.get_anim_instance().get_current_active_montage()
        for pawn in [p,server]:
            floor=pawn.get_actor_location().z-pawn.capsule_component.get_scaled_capsule_half_height()
            assert pawn.mesh.get_socket_location('pelvis').z-floor>70,'Replicated throw pose below ground'
        tn_key(p,'H',False);yield .45
        local_objects=u.GameplayStatics.get_all_actors_of_class(p.get_world(),u.CRThrownObject)
        server_objects=u.GameplayStatics.get_all_actors_of_class(server.get_world(),u.CRThrownObject)
        assert len(local_objects)==len(server_objects)==1,('Projectile duplication/replication',len(local_objects),len(server_objects))
        local,auth=local_objects[0],server_objects[0]
        assert local.type==auth.type==kind
        error=(local.get_actor_location()-auth.get_actor_location()).length()
        assert error<160,('Projectile replication',error)
        assert p.throwable.get_remaining()==server.throwable.get_remaining()==5
        assert p.throwable.phase==server.throwable.phase==u.CRThrowPhase.THROWING
        assert not p.throwable.preview_visible
        yield 3.1
        assert local.detonated and auth.detonated
        assert not p.throwable.is_busy() and not server.throwable.is_busy()
        assert p.throwable.throws_released==server.throwable.throws_released
        if kind==u.CRThrowableType.SMOKE:
            center=auth.detonation_location+u.Vector(0,0,100)
            for world in [p.get_world(),server.get_world()]:
                assert u.CRThrownObject.is_sight_obscured(world,center-u.Vector(700,0,0),center+u.Vector(700,0,0))
                effects=[a for a in u.ObjectIterator(u.ParticleSystemComponent) if a.get_world()==world and a.get_num_active_particles()>0]
                assert effects,'Smoke missing on network view'
        tn_test['results'].append(dict(case=str(kind),replication_error_cm=error,remaining=5,projectile_copies=1,detonated_both=True))
        yield 3 if kind==u.CRThrowableType.GRENADE else .5
    tn_key(p,'H',True);yield .3;tn_key(p,'Z',True);yield .2;tn_key(p,'Z',False);tn_key(p,'H',False);yield .3
    assert not p.throwable.is_busy() and not server.throwable.is_busy()
    assert p.throwable.smoke_grenades==server.throwable.smoke_grenades==5
    tn_test['results'].append(dict(case='network_cancel',inventory_unchanged=True))
def tn_finish(error=None):
    u.unregister_slate_post_tick_callback(tn_test['handle']);tn_test.update(finished=True,error=error)
    (tn_root/'Artifacts/Throw/network.json').write_text(json.dumps(dict(passed=error is None,error=error,results=tn_test['results']),indent=2)+'\n')
    print('THROW_NETWORK',error)
tn_generator=tn_run()
def tn_tick(dt):
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    if not worlds:return
    now=u.GameplayStatics.get_time_seconds(worlds[0])
    if tn_test['busy'] or now<tn_test['next']:return
    tn_test['busy']=True
    try:
        assert time.monotonic()<tn_test['deadline']
        tn_test['next']=now+next(tn_generator)
    except StopIteration:tn_finish()
    except Exception:tn_finish(traceback.format_exc())
    finally:tn_test['busy']=False
tn_test['handle']=u.register_slate_post_tick_callback(tn_tick)
print('THROW_NETWORK_STARTED')
