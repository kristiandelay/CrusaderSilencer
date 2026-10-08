"""Actual Q/H/X input: both hands, both objects, swaps while aiming and release locking."""
import json,time,traceback
from pathlib import Path
import unreal as u
tsh_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
tsh_test=dict(next=0,busy=False,results=[],deadline=time.monotonic()+200,report='shoulders.json')
def tsh_key(p,name,down):
    key=u.Key();assert key.import_text(name);u.CRBlueprintTools.inject_pie_key(p,key,down)
def tsh_context():
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    pawns=[p for w in worlds for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if isinstance(p.get_controller(),u.PlayerController) and not p.crowd_agent.enabled]
    p=next(p for p in pawns if p.is_locally_controlled() and (not p.has_authority() if len(worlds)>1 else True))
    server=next(a for a in pawns if a.has_authority() and not a.is_locally_controlled()) if len(worlds)>1 else p
    return p,server
def tsh_hand(p,left):
    held=next(a for a in p.get_components_by_class(u.StaticMeshComponent) if a.static_mesh and a.static_mesh.get_name() in ['SM_Grenade','SM_Smoke'])
    hand='hand_l' if left else 'hand_r';other='hand_r' if left else 'hand_l'
    assert str(held.get_attach_socket_name())==hand,(held.get_attach_socket_name(),hand)
    assert held.get_attach_parent()==p.baseline_equipment.get_presentation_mesh()
    assert held.is_visible()
    for mesh in [p.mesh,p.baseline_equipment.get_presentation_mesh()]:
        assert mesh.get_socket_location(hand).z>mesh.get_socket_location(other).z+20,('Wrong arm pose',left,mesh.get_name())
        floor=p.get_actor_location().z-p.capsule_component.get_scaled_capsule_half_height()
        assert mesh.get_socket_location('pelvis').z-floor>70,'Pose below floor'
    assert (held.get_world_location()-held.get_attach_parent().get_socket_location(hand)).length()<12
    assert min(held.get_world_scale().x,held.get_world_scale().y,held.get_world_scale().z)>0,'Negative scale mirrored object'
    return held
def tsh_run():
    while True:
        try:p,server=tsh_context();break
        except StopIteration:yield .2
    while not p.physical_interaction.controls_created or not server.physical_interaction.controls_created:yield .2
    if p!=server:tsh_test['report']='shoulders-network.json'
    pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(server.get_world(),u.BaselineWeaponPickup) if 'Rifle' in a.item_definition.get_name())
    pos=pickup.get_actor_location();server.set_actor_location(pos+u.Vector(-110,0,94-pos.z),False,True);server.baseline_equipment.server_pickup(pickup)
    yield 1
    for kind in [u.CRThrowableType.GRENADE,u.CRThrowableType.SMOKE]:
        for swap in [False,True]:
            for left in [False,True]:
                # Isolate each trajectory from previous grenades and roaming NPCs.
                for w in u.EditorLevelLibrary.get_pie_worlds(False):
                    for a in u.GameplayStatics.get_all_actors_of_class(w,u.CRThrownObject):
                        if a.has_authority():a.destroy_actor()
                server.set_actor_location(u.Vector(5000,2500,94),False,True);server.set_actor_rotation(u.Rotator(yaw=35),False);server.force_net_update()
                p.get_controller().set_control_rotation(u.Rotator(yaw=35))
                yield .65
                initial=not left if swap else left
                if p.baseline_equipment.is_left_shoulder()!=initial:
                    tsh_key(p,'Q',True);yield .1;tsh_key(p,'Q',False);yield .5
                if p.throwable.selected_type!=kind:
                    tsh_key(p,'X',True);yield .1;tsh_key(p,'X',False);yield .2
                assert p.baseline_equipment.is_left_shoulder()==server.baseline_equipment.is_left_shoulder()==initial
                before=server.throwable.throws_released;count=server.throwable.get_remaining()
                tsh_key(p,'H',True);yield .45
                assert p.throwable.phase==server.throwable.phase==u.CRThrowPhase.AIMING
                tsh_hand(p,initial);tsh_hand(server,initial)
                if swap:
                    tsh_key(p,'Q',True);yield .1;tsh_key(p,'Q',False);yield .45
                assert p.throwable.is_left_throw_hand()==server.throwable.is_left_throw_hand()==left
                held=tsh_hand(p,left);tsh_hand(server,left)
                assert p.throwable.preview_visible
                start=p.throwable.preview_points[0]
                lateral=(start-p.get_actor_location()).dot(p.get_actor_right_vector())
                assert abs(lateral-(-24 if left else 24))<1,('Wrong trajectory side',left,lateral)
                impact=p.throwable.predicted_impact
                tsh_key(p,'H',False);yield .09
                assert p.throwable.phase==u.CRThrowPhase.THROWING
                montage=p.mesh.get_anim_instance().get_current_active_montage()
                expected=p.throwable.get_editor_property('left_throw_montage' if left else 'throw_montage')
                assert montage==expected,('Wrong release animation',left,montage)
                tsh_key(p,'Q',True);yield .1;tsh_key(p,'Q',False);yield .4
                assert p.baseline_equipment.is_left_shoulder()==server.baseline_equipment.is_left_shoulder()==left,'Hand changed during release'
                assert p.throwable.release_left_hand==server.throwable.release_left_hand==left
                assert server.throwable.throws_released==before+1 and server.throwable.get_remaining()==count-1
                yield 1.2
                obj=next(a for a in u.GameplayStatics.get_all_actors_of_class(server.get_world(),u.CRThrownObject))
                error=(obj.first_impact-impact).length()
                assert obj.bounce_count>0 and error<40,('Release missed preview',left,error)
                assert not p.throwable.is_busy() and not server.throwable.is_busy()
                weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
                assert all(not a.get_editor_property('bHidden') and str(a.root_component.get_attach_socket_name()) in [('hand_l' if left else 'hand_r'),('weapon_l' if left else 'weapon_r')] for a in weapon.get_spawned_actors())
                tsh_test['results'].append(dict(type=str(kind),left=left,swap_while_aiming=swap,trajectory_side_cm=lateral,impact_error_cm=error,release_locked=True,weapon_hand_restored=True))
    tsh_key(p,'H',True);yield .4
    tsh_key(p,'Q',True);yield .1;tsh_key(p,'Q',False);yield .5
    tsh_key(p,'Z',True);yield .1;tsh_key(p,'Z',False);tsh_key(p,'H',False);yield .4
    assert not p.throwable.is_busy() and not server.throwable.is_busy()
    assert server.throwable.throws_released==8
    tsh_test['results'].append(dict(case='cancel_after_hand_swap',no_extra_throw=True))
def tsh_finish(error=None):
    u.unregister_slate_post_tick_callback(tsh_test['handle']);tsh_test.update(finished=True,error=error)
    (tsh_root/'Artifacts/Throw'/tsh_test['report']).write_text(json.dumps(dict(passed=error is None,error=error,results=tsh_test['results']),indent=2)+'\n')
    print('THROW_SHOULDERS',error)
tsh_generator=tsh_run()
def tsh_tick(dt):
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    if not worlds:return
    now=u.GameplayStatics.get_time_seconds(worlds[0])
    if tsh_test['busy'] or now<tsh_test['next']:return
    tsh_test['busy']=True
    try:
        assert time.monotonic()<tsh_test['deadline']
        tsh_test['next']=now+next(tsh_generator)
    except StopIteration:tsh_finish()
    except Exception:tsh_finish(traceback.format_exc())
    finally:tsh_test['busy']=False
tsh_test['handle']=u.register_slate_post_tick_callback(tsh_tick)
print('THROW_SHOULDERS_STARTED')
