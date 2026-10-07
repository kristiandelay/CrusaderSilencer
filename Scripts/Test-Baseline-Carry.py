"""Compare relaxed body bones against a simultaneous, unmodified GASP retarget."""
import math
carry_out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/CarryTests'
carry_out.mkdir(parents=True,exist_ok=True)
carry_test={'phase':'setup','next':0,'index':0,'results':[],'busy':False,'deadline':time.monotonic()+150}

def carry_context():
    world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
    pawn=u.GameplayStatics.get_player_pawn(world,0)
    pc=pawn.get_controller()
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
             if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pc)
    equipment=pawn.get_component_by_class(u.BaselineEquipmentComponent)
    return world,pawn,pc,sub,equipment

def carry_input(sub,name,values):
    sub.inject_input_vector_for_action(u.load_asset('/Game/Input/IA_'+name),u.Vector(*values),[],[])

def carry_reference(world):
    return next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.SkeletalMeshActor)
                if a.actor_has_tag('CarryPoseReference'))

def carry_finish(error=None):
    u.unregister_slate_post_tick_callback(carry_test['handle'])
    carry_test['finished']=True
    try:
        world,pawn,pc,sub,_=carry_context()
        for name in ['Move','Aim','Walk']:carry_input(sub,name,(0,0,0))
        pawn.un_crouch();carry_reference(world).destroy_actor()
    except Exception:pass
    carry_test.pop('capture',None)
    (carry_out/'carry-body.json').write_text(json.dumps({'passed':error is None,'error':error,'results':carry_test['results']},indent=2))

def carry_tick(dt):
    if carry_test['busy']:return
    carry_test['busy']=True
    try:
        assert time.monotonic()<carry_test['deadline'],'Carry test timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds or not u.GameplayStatics.get_player_pawn(worlds[0],0):return
        world,pawn,pc,sub,equipment=carry_context()
        now=u.GameplayStatics.get_time_seconds(world)
        if carry_test['phase']=='sample' and carry_test['index'] in [2,3]:
            carry_input(sub,'Move',(0,1,0));carry_input(sub,'Walk',(1,0,0))
        if now<carry_test['next']:return
        mesh=equipment.get_presentation_mesh();anim=mesh.get_anim_instance()
        if carry_test['phase']=='setup':
            if not equipment.get_active_item():equipment.interact()
            pawn.set_actor_location(u.Vector(-1400,-3200,94),False,True)
            pc.set_control_rotation(u.Rotator(pitch=0,yaw=0,roll=0))
            reference=u.CRBlueprintTools.spawn_pie_test_actor(world,u.SkeletalMeshActor,mesh.get_world_transform())
            reference.set_editor_property('tags',['CarryPoseReference'])
            reference.attach_to_component(pawn.mesh,'None',u.AttachmentRule.KEEP_WORLD,u.AttachmentRule.KEEP_WORLD,u.AttachmentRule.KEEP_WORLD,False)
            ref_mesh=reference.skeletal_mesh_component
            # Physics Control makes the live retarget evaluate after physics.
            # Compare the same frame, rather than a default pre-physics reference.
            ref_mesh.set_tick_group(u.TickingGroup.TG_POST_PHYSICS)
            ref_mesh.add_tick_prerequisite_component(mesh)
            ref_mesh.set_skeletal_mesh_asset(mesh.get_skeletal_mesh_asset())
            ref_mesh.set_editor_property('component_tags',mesh.get_editor_property('component_tags'))
            ref_mesh.set_anim_instance_class(u.load_asset('/Game/Blueprints/RetargetedCharacters/ABP_GenericRetarget').generated_class())
            assert u.CRBlueprintTools.set_property_text(ref_mesh.get_anim_instance(),'IKRetargeter',anim.get_editor_property('IKRetargeter').get_path_name())
            ref_mesh.set_editor_property('visibility_based_anim_tick_option',u.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
            reference.set_actor_hidden_in_game(True)
            carry_test.update(phase='start',next=now+2)
        elif carry_test['phase']=='start':
            index=carry_test['index']
            pc.set_control_rotation(u.Rotator(pitch=30 if index==1 else 0,yaw=0,roll=0))
            if index==3:pawn.crouch()
            carry_test.update(phase='sample',next=now+.6,started=now+.6,samples=[])
        elif carry_test['phase']=='sample':
            assert anim.weapon_upper_body_weight<.02 and abs(anim.aim_pitch)<.1
            ref_mesh=carry_reference(world).skeletal_mesh_component
            errors=[]
            for bone in ['spine_01','spine_03','spine_05','neck_01','head']:
                actual=mesh.get_socket_transform(bone,u.RelativeTransformSpace.RTS_COMPONENT)
                expected=ref_mesh.get_socket_transform(bone,u.RelativeTransformSpace.RTS_COMPONENT)
                dot=abs(actual.rotation.x*expected.rotation.x+actual.rotation.y*expected.rotation.y+
                        actual.rotation.z*expected.rotation.z+actual.rotation.w*expected.rotation.w)
                errors.append(math.degrees(2*math.acos(min(1,dot))))
            head=mesh.get_socket_location('head')-pawn.get_actor_location()
            carry_test['samples'].append({'error':max(errors),'head_z':head.z})
            if now-carry_test['started']>1.2:
                max_error=max(s['error'] for s in carry_test['samples'])
                assert max_error<2,f'Relaxed overlay modified head/spine by {max_error} degrees'
                carry_test['results'].append({'case':['idle','look_up','walk','crouch_walk'][carry_test['index']],
                    'max_body_rotation_difference_degrees':max_error,
                    'head_motion_cm':max(s['head_z'] for s in carry_test['samples'])-min(s['head_z'] for s in carry_test['samples'])})
                if carry_test['index']==0:
                    carry_test['capture']=u.AutomationLibrary.take_high_res_screenshot(1440,900,str(carry_out/'relaxed-idle.png'),delay=0.0)
                carry_test['index']+=1
                if carry_test['index']==4:carry_finish()
                else:carry_test.update(phase='start',next=now+.1)
    except Exception:carry_finish(traceback.format_exc())
    finally:carry_test['busy']=False

carry_test['handle']=u.register_slate_post_tick_callback(carry_tick)
print('Started carry body comparison')
