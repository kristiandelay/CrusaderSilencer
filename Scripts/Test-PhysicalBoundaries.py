"""PIE interaction rejection and automatic fall-ragdoll checks."""
boundary_physical={'phase':'setup','next':0,'index':0,'results':[],'deadline':time.monotonic()+100,'busy':False}
boundary_physical_out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/PhysicalTests/physical-boundaries.json'

def pb_finish(error=None):
    u.unregister_slate_post_tick_callback(boundary_physical['handle'])
    boundary_physical['finished']=True
    boundary_physical_out.write_text(json.dumps({'passed':error is None,'error':error,'results':boundary_physical['results']},indent=2))
    print('PHYSICAL_BOUNDARIES_COMPLETE',error)

def pb_tick(dt):
    if boundary_physical['busy']:return
    boundary_physical['busy']=True
    try:
        assert time.monotonic()<boundary_physical['deadline'],'Boundary test timeout'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        w=worlds[0];p=u.GameplayStatics.get_player_pawn(w,0)
        if not p:return
        other=next(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if 'TrainingPartner' in a.get_name())
        now=u.GameplayStatics.get_time_seconds(w)
        if boundary_physical.pop('release',False):
            for action in ['Shove','Ragdoll']:physical_input(p,action,0)
        if now<boundary_physical['next']:return
        phase=boundary_physical['phase']
        if phase=='setup':
            p.character_movement.stop_movement_immediately();other.character_movement.stop_movement_immediately()
            p.set_actor_location(u.Vector(1800,-2700,94),False,True)
            p.set_actor_rotation(u.Rotator(yaw=0),False)
            p.get_controller().set_control_rotation(u.Rotator(yaw=0))
            other.set_actor_location(u.Vector(2200,-2700,94),False,True)
            boundary_physical.update(phase='range',next=now+1)
        elif phase=='range':
            assert not p.physical_interaction.find_interaction_target(),'Selected out-of-range target'
            physical_input(p,'Shove',1)
            boundary_physical.update(phase='check_range',next=now+.4,release=True)
        elif phase=='check_range':
            assert not p.physical_interaction.is_busy() and not other.physical_interaction.is_busy(),'Out-of-range request accepted'
            boundary_physical['results'].append({'case':'out_of_range_rejected','passed':True})
            other.set_actor_location(u.Vector(1650,-2700,94),False,True)
            boundary_physical.update(phase='behind',next=now+.6)
        elif phase=='behind':
            assert not p.physical_interaction.find_interaction_target(),'Selected target behind player'
            boundary_physical['results'].append({'case':'target_behind_rejected','passed':True})
            other.set_actor_location(u.Vector(1950,-2700,94),False,True)
            wall=u.CRBlueprintTools.spawn_pie_test_actor(w,u.StaticMeshActor,u.Transform(location=u.Vector(1875,-2700,100)))
            wall.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE)
            wall.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
            wall.set_actor_scale3d(u.Vector(.25,4,2))
            boundary_physical['wall_name']=wall.get_name()
            boundary_physical.update(phase='wall',next=now+.5)
        elif phase=='wall':
            assert not p.physical_interaction.find_interaction_target(),'Selected target through wall'
            boundary_physical['results'].append({'case':'wall_blocks_interaction','passed':True})
            next(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.StaticMeshActor) if a.get_name()==boundary_physical['wall_name']).destroy_actor()
            boundary_physical.update(phase='dying_target',next=now+.3)
        elif phase=='dying_target':
            assert p.physical_interaction.find_interaction_target()==other,'Ready target unavailable after removing wall'
            health=other.get_component_by_class(u.LyraHealthComponent)
            assert u.CRBlueprintTools.set_property_text(health,'DeathState','DeathStarted')
            assert not p.physical_interaction.find_interaction_target(),'Selected a dying target'
            assert u.CRBlueprintTools.set_property_text(health,'DeathState','NotDead')
            boundary_physical['results'].append({'case':'dying_target_rejected','passed':True})
            p.set_actor_location(u.Vector(1500,-2800,1600),False,True)
            p.character_movement.set_movement_mode(u.MovementMode.MOVE_FALLING)
            boundary_physical.update(phase='fall',next=now+.1,started=now,saw_ragdoll=False,saw_recovery=False,min_pelvis_z=1e8)
        elif phase=='fall':
            physical=p.physical_interaction
            state=str(physical.get_phase())
            if 'RAGDOLL' in state:
                boundary_physical['saw_ragdoll']=True
                boundary_physical['min_pelvis_z']=min(boundary_physical['min_pelvis_z'],p.mesh.get_socket_location('pelvis').z)
                assert p.mesh.get_socket_location('pelvis').z>-100,'High-speed ragdoll tunneled through floor'
                if now-boundary_physical['started']>5:physical_input(p,'Ragdoll',1);boundary_physical['release']=True
            if 'RECOVERY' in state:boundary_physical['saw_recovery']=True
            if now-boundary_physical['started']>7 and not physical.is_busy():
                assert boundary_physical['saw_ragdoll'] and boundary_physical['saw_recovery'],'Automatic fall/get-up failed'
                assert p.get_actor_location().z>50,'Recovered capsule below floor'
                boundary_physical['results'].append({'case':'fast_fall_passive_ragdoll_and_recovery','passed':True,'minimum_pelvis_z':boundary_physical['min_pelvis_z']})
                pb_finish()
            else:boundary_physical['next']=now+.1
    except Exception:pb_finish(traceback.format_exc())
    finally:boundary_physical['busy']=False

boundary_physical['handle']=u.register_slate_post_tick_callback(pb_tick)
print('Started physical boundary checks')
