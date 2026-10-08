"""Real input integration: trajectory, fuse, GAS damage/cover, smoke and interruption."""
import json,time,traceback
from pathlib import Path
import unreal as u
tt_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
tt_test=dict(next=0,busy=False,results=[],deadline=time.monotonic()+160)
def tt_key(p,name,down):
    key=u.Key();assert key.import_text(name);u.CRBlueprintTools.inject_pie_key(p,key,down)
def tt_record(name,**values):tt_test['results'].append(dict(case=name,**values))
def tt_pose(p):
    floor=p.get_actor_location().z-p.capsule_component.get_scaled_capsule_half_height()
    meshes=[p.mesh,p.baseline_equipment.get_presentation_mesh()]
    heights=[m.get_socket_location('pelvis').z-floor for m in meshes]
    assert all(70<h<135 for h in heights),('Throw pose collapsed into ground',heights)
    return heights
def tt_capture(w,name,location,target):
    camera=u.CRBlueprintTools.spawn_pie_test_actor(w,u.SceneCapture2D,u.Transform(location=location))
    camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(location,target),False)
    c=camera.get_component_by_class(u.SceneCaptureComponent2D)
    c.set_editor_property('capture_every_frame',False);c.set_editor_property('capture_on_movement',False)
    c.set_editor_property('fov_angle',70);c.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    t=u.RenderingLibrary.create_render_target2d(w,1200,760,u.TextureRenderTargetFormat.RTF_RGBA8)
    c.set_editor_property('texture_target',t);c.capture_scene()
    u.RenderingLibrary.export_render_target(w,t,str(tt_root/'Artifacts/Throw'),name+'.png');camera.destroy_actor()
def tt_run():
    w=u.EditorLevelLibrary.get_pie_worlds(False)[0];p=u.GameplayStatics.get_player_pawn(w,0);t=p.throwable
    while not p.physical_interaction.controls_created:yield .2
    pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.BaselineWeaponPickup) if 'Rifle' in a.item_definition.get_name())
    pos=pickup.get_actor_location();p.set_actor_location(pos+u.Vector(-110,0,94-pos.z),False,True);p.baseline_equipment.server_pickup(pickup)
    yield 1
    weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance);assert weapon
    p.set_actor_location(u.Vector(5000,2500,94),False,True);p.set_actor_rotation(u.Rotator(),False);p.get_controller().set_control_rotation(u.Rotator())
    yield .6
    assert t.can_begin_aim()
    tt_key(p,'H',True);yield .5
    assert t.phase==u.CRThrowPhase.AIMING and t.preview_visible and len(t.preview_points)>10
    tt_record('standing_throw_aim_pose',pelvis_heights_cm=tt_pose(p))
    assert p.baseline_equipment.are_hands_busy() and all(a.get_editor_property('bHidden') for a in weapon.get_spawned_actors())
    tt_key(p,'X',True);yield .1;tt_key(p,'X',False)
    assert t.selected_type==u.CRThrowableType.GRENADE,'Changed type mid-throw'
    tt_key(p,'Z',True);yield .2;tt_key(p,'Z',False);tt_key(p,'H',False);yield .4
    assert not t.is_busy() and not t.preview_visible and t.grenades==6 and t.throws_released==0
    tt_record('cancel_and_type_lock',remaining=t.grenades)
    # A wall covering the hand path cannot be bypassed by spawning beyond it.
    block=u.CRBlueprintTools.spawn_pie_test_actor(w,u.StaticMeshActor,u.Transform(location=p.get_actor_location()+u.Vector(38,0,45)))
    block.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE);block.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
    block.set_actor_scale3d(u.Vector(.1,3,3));block.static_mesh_component.set_collision_profile_name('BlockAll')
    tt_key(p,'H',True);yield .35
    assert t.launch_blocked and not t.preview_visible,'Preview ignored close cover'
    tt_key(p,'H',False);yield .25
    assert t.grenades==6 and t.throws_released==0 and not t.is_busy()
    block.destroy_actor();tt_record('close_cover_cancels_release');yield .25
    tt_key(p,'H',True);yield .45
    predicted=t.predicted_impact;assert t.phase==u.CRThrowPhase.AIMING and t.preview_visible and t.preview_hit,(t.phase,t.preview_visible,t.launch_blocked)
    tt_capture(w,'GrenadeTrajectory',p.get_actor_location()+u.Vector(-260,-330,160),p.get_actor_location()+u.Vector(450,0,80))
    tt_capture(w,'ThrowAimPose',p.get_actor_location()+u.Vector(300,-320,100),p.get_actor_location()+u.Vector(0,0,10))
    # Scene capture can stall rendering; let that frame finish before timing input.
    yield .3
    tt_key(p,'H',False);yield .35
    objects=u.GameplayStatics.get_all_actors_of_class(w,u.CRThrownObject);assert len(objects)==1,(len(objects),t.phase,t.throws_released,t.grenades,t.launch_blocked)
    tt_record('standing_throw_release_pose',pelvis_heights_cm=tt_pose(p))
    grenade=objects[0];assert t.grenades==5 and t.throws_released==1
    yield 1.8
    assert grenade.bounce_count>0
    error=(grenade.first_impact-predicted).length();assert error<35,('Preview diverged',error,predicted,grenade.first_impact)
    guards=[a for a in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if a.crowd_agent.enabled and a.crowd_agent.guard and not isinstance(a,u.CRRobotCharacter)][:3]
    assert len(guards)==3
    center=grenade.get_actor_location()
    for g,offset in zip(guards,[u.Vector(200,0,88-center.z),u.Vector(0,230,88-center.z),u.Vector(850,0,88-center.z)]):
        g.get_controller().set_actor_tick_enabled(False);g.get_controller().stop_movement();g.character_movement.stop_movement_immediately();g.set_actor_location(center+offset,False,True)
    wall=u.CRBlueprintTools.spawn_pie_test_actor(w,u.StaticMeshActor,u.Transform(location=center+u.Vector(0,115,100)))
    wall.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE);wall.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
    wall.set_actor_scale3d(u.Vector(2,.3,3));wall.static_mesh_component.set_collision_profile_name('BlockAll')
    health=[g.get_component_by_class(u.LyraHealthComponent).get_health() for g in guards]
    yield 1.3
    assert grenade.detonated
    after=[g.get_component_by_class(u.LyraHealthComponent).get_health() for g in guards]
    assert after[0]<health[0] and after[1:]==health[1:],('Blast/cover/range',health,after)
    tt_record('grenade_arc_bounce_fuse_damage_cover',arc_error_cm=error,health_before=health,health_after=after,bounces=grenade.bounce_count)
    wall.destroy_actor()
    for g in guards:g.set_actor_location(u.Vector(13000,2500+guards.index(g)*400,94),False,True)
    assert not t.is_busy() and not t.preview_visible
    tt_key(p,'X',True);yield .15;tt_key(p,'X',False);yield .15
    assert t.selected_type==u.CRThrowableType.SMOKE
    tt_key(p,'H',True);yield .45
    assert t.preview_visible
    tt_key(p,'H',False);yield .4
    smoke=next(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.CRThrownObject) if a.type==u.CRThrowableType.SMOKE)
    assert t.smoke_grenades==5
    yield 1.6
    assert smoke.detonated
    assert any(a.get_num_active_particles()>0 for a in u.ObjectIterator(u.ParticleSystemComponent) if a.get_world()==w),'No visible smoke particles'
    center=smoke.detonation_location+u.Vector(0,0,100)
    assert u.CRThrownObject.is_sight_obscured(w,center-u.Vector(700,0,0),center+u.Vector(700,0,0))
    assert not u.CRThrownObject.is_sight_obscured(w,center+u.Vector(0,700,0),center+u.Vector(1000,700,0))
    tt_capture(w,'SmokeCloud',center+u.Vector(-720,-780,350),center)
    tt_record('smoke_fuse_and_sight_obstruction',duration=smoke.get_editor_property('smoke_duration'),remaining=t.smoke_grenades)
    tt_key(p,'LeftAlt',True);yield .25;tt_key(p,'LeftAlt',False)
    assert p.roll.is_rolling()
    assert all(not a.get_editor_property('bHidden') for a in weapon.get_spawned_actors()),'Roll hid weapon'
    tt_key(p,'H',True);yield .1;tt_key(p,'H',False)
    assert not t.is_busy();tt_record('roll_weapon_visible_throw_blocked')
    yield 1.4
    tt_key(p,'H',True);yield .25
    assert t.is_busy();p.physical_interaction.start_ragdoll(u.Vector())
    yield .3;tt_key(p,'H',False)
    assert not t.is_busy() and not t.preview_visible and t.throws_released==2
    assert p.baseline_equipment.should_hide_weapon()
    tt_record('knockdown_cancels_without_consuming')
    yield 1
    p.physical_interaction.request_recovery();yield 5
    assert not p.physical_interaction.is_busy()
    assert not u.GameplayStatics.get_all_actors_of_class(w,u.CRThrownObject) or all(a.type==u.CRThrowableType.SMOKE for a in u.GameplayStatics.get_all_actors_of_class(w,u.CRThrownObject))
    p.set_actor_location(u.Vector(5000,2500,94),False,True);yield .5
    p.launch_character(u.Vector(0,0,550),False,True);yield .12
    tt_key(p,'H',True);yield .15;tt_key(p,'H',False)
    assert not t.is_busy();tt_record('airborne_throw_blocked')
    yield 1.5
    assert u.CRBlueprintTools.set_property_text(t,'SmokeGrenades','0')
    tt_key(p,'H',True);yield .15;tt_key(p,'H',False)
    assert not t.is_busy() and t.throws_released==2;tt_record('empty_inventory_blocked')
    yield 3
    assert not u.GameplayStatics.get_all_actors_of_class(w,u.CRThrownObject),'Smoke/projectile did not expire'
    assert not u.CRThrownObject.is_sight_obscured(w,center-u.Vector(700,0,0),center+u.Vector(700,0,0))
    tt_record('smoke_expiry_restores_sight')
def tt_finish(error=None):
    u.unregister_slate_post_tick_callback(tt_test['handle']);tt_test.update(finished=True,error=error)
    (tt_root/'Artifacts/Throw/standalone.json').write_text(json.dumps(dict(passed=error is None,error=error,results=tt_test['results']),indent=2)+'\n')
    print('THROW_TEST',error)
tt_generator=tt_run()
def tt_tick(dt):
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    if not worlds:return
    now=u.GameplayStatics.get_time_seconds(worlds[0])
    if tt_test['busy'] or now<tt_test['next']:return
    tt_test['busy']=True
    try:
        assert time.monotonic()<tt_test['deadline']
        tt_test['next']=now+next(tt_generator)
    except StopIteration:tt_finish()
    except Exception:tt_finish(traceback.format_exc())
    finally:tt_test['busy']=False
tt_test['handle']=u.register_slate_post_tick_callback(tt_tick)
print('THROW_TEST_STARTED')
