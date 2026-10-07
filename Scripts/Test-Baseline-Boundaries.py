"""Run after Test-Baseline.py: transaction rejection, slide collision and crouch clearance."""
boundary={'phase':'full','next':0,'results':[],'busy':False,'deadline':time.monotonic()+120}
boundary_out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/BaselineTests/boundaries.json'

def boundary_actor(world,name):
    return next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.Actor) if a.get_name()==boundary[name])

def boundary_spawn(world,cls,location,scale=(1,1,1)):
    transform=u.Transform()
    transform.translation=u.Vector(*location)
    transform.scale3d=u.Vector(*scale)
    return u.CRBlueprintTools.spawn_pie_test_actor(world,cls,transform)

def boundary_finish(error=None):
    u.unregister_slate_post_tick_callback(boundary['handle'])
    boundary['finished']=True
    try:
        world,pawn,_,_=baseline_context()
        pawn.character_movement.set_slide_requested(False)
        for key in ['wall','fixture']:
            if key in boundary:
                try:boundary_actor(world,key).destroy_actor()
                except StopIteration:pass
    except Exception:pass
    boundary_out.write_text(json.dumps({'passed':error is None,'error':error,'results':boundary['results']},indent=2))

def boundary_tick(dt):
    if boundary['busy']:return
    boundary['busy']=True
    try:
        assert time.monotonic()<boundary['deadline'],'Boundary checks timed out'
        world,pawn,controller,_=baseline_context()
        now=u.GameplayStatics.get_time_seconds(world)
        if now<boundary['next']:return
        equipment=pawn.get_component_by_class(u.BaselineEquipmentComponent)
        movement=pawn.character_movement
        phase=boundary['phase']
        if phase=='full':
            assert len(controller.inventory.get_all_items())==3
            pawn.un_crouch();movement.stop_movement_immediately()
            pawn.set_actor_location(u.Vector(0,-6500,94),False,True)
            controller.set_control_rotation(u.Rotator(pitch=0,yaw=0,roll=0))
            fixture=boundary_spawn(world,u.BaselineWeaponPickup,(160,-6500,55))
            fixture.set_editor_property('item_definition',u.load_class(None,'/Game/Baseline/Weapons/Rifle/ID_Rifle.ID_Rifle_C'))
            boundary['fixture']=fixture.get_name()
            equipment.server_pickup(fixture)
            assert len(controller.inventory.get_all_items())==3 and not fixture.is_actor_being_destroyed()
            assert 'full' in equipment.last_interaction_result.lower()
            boundary['results'].append('full_inventory_rejected_without_consuming_pickup')
            equipment.drop_active_weapon()
            boundary.update(phase='range',next=now+1)
        elif phase=='range':
            assert len(controller.inventory.get_all_items())==2
            fixture=boundary_actor(world,'fixture')
            fixture.set_actor_location(u.Vector(1200,-6500,55),False,True)
            equipment.server_pickup(fixture)
            assert len(controller.inventory.get_all_items())==2 and not fixture.is_actor_being_destroyed()
            boundary['results'].append('out_of_range_server_request_rejected')
            fixture.set_actor_location(u.Vector(180,-6500,55),False,True)
            wall=boundary_spawn(world,u.StaticMeshActor,(120,-6500,150),(.2,4,3))
            wall.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE)
            wall.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
            wall.static_mesh_component.set_collision_profile_name('BlockAll')
            boundary['wall']=wall.get_name()
            boundary.update(phase='occluded',next=now+.3)
        elif phase=='occluded':
            fixture=boundary_actor(world,'fixture')
            equipment.server_pickup(fixture)
            assert len(controller.inventory.get_all_items())==2 and not fixture.is_actor_being_destroyed()
            boundary['results'].append('pickup_through_wall_rejected')
            boundary_actor(world,'wall').set_actor_location(u.Vector(350,-6500,150),False,True)
            equipment.server_pickup(fixture)
            assert len(controller.inventory.get_all_items())==3
            boundary['results'].append('visible_in_range_pickup_accepted')
            boundary.pop('fixture')
            movement.velocity=u.Vector(800,0,0)
            movement.set_slide_requested(True)
            pawn.crouch()
            boundary.update(phase='wall_slide',next=now+1.5)
        elif phase=='wall_slide':
            assert pawn.get_actor_location().x<315 and pawn.get_velocity().length()<180
            assert not movement.is_sliding()
            boundary['results'].append('slide_stopped_by_wall')
            wall=boundary_actor(world,'wall')
            wall.set_actor_scale3d(u.Vector(4,4,.4))
            wall.set_actor_location(u.Vector(0,-6500,150),False,True)
            pawn.set_actor_location(u.Vector(0,-6500,62),False,True)
            pawn.un_crouch()
            boundary.update(phase='clearance',next=now+.5)
        elif phase=='clearance':
            assert pawn.capsule_component.get_scaled_capsule_half_height()==60
            boundary['results'].append('low_ceiling_prevents_uncrouch')
            boundary_actor(world,'wall').destroy_actor();boundary.pop('wall')
            pawn.un_crouch()
            boundary.update(phase='stand',next=now+.5)
        elif phase=='stand':
            assert pawn.capsule_component.get_scaled_capsule_half_height()>80
            boundary['results'].append('standing_recovers_when_clear')
            boundary_finish()
    except Exception:boundary_finish(traceback.format_exc())
    finally:boundary['busy']=False

boundary['handle']=u.register_slate_post_tick_callback(boundary_tick)
print('Started boundary checks')
