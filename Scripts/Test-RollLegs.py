"""Compare evaluated roll knees with the authored pose and capture all eight rolls."""
import json,math,time,traceback
from pathlib import Path
import unreal as u

rlv_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
rlv_out=rlv_root/'Artifacts/Roll/Legs';rlv_out.mkdir(exist_ok=True)
rlv_rows=json.loads((rlv_root/'resources/RollAnimations.json').read_text())
rlv_opts=u.AnimPoseEvaluationOptions();rlv_opts.set_editor_property('incorporate_root_motion_into_pose',True)
rlv_bones=['thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r']

def rlv_knee(points,side):
    a=points['thigh_'+side]-points['calf_'+side];b=points['foot_'+side]-points['calf_'+side]
    return math.degrees(math.acos(max(-1,min(1,(a.x*b.x+a.y*b.y+a.z*b.z)/(a.length()*b.length())))))

def rlv_measure(p):
    anim=p.mesh.get_anim_instance();montage=anim.get_current_active_montage()
    assert montage and anim.locomotion_correction_bypass_weight>.99,'Standing correction applied to roll'
    position=anim.montage_get_position(montage)
    seq=u.load_asset(rlv_rows[p.roll.active_direction]['animation'])
    pose=u.AnimPoseExtensions.get_anim_pose_at_time(seq,position,rlv_opts)
    raw={b:u.AnimPoseExtensions.get_bone_pose(pose,b,u.AnimPoseSpaces.WORLD).translation for b in rlv_bones}
    record=dict(direction=p.roll.active_direction,position=position,authored_knees=[rlv_knee(raw,s) for s in ['l','r']])
    for name,mesh in [('source',p.mesh),('visible',p.baseline_equipment.get_presentation_mesh())]:
        points={b:mesh.get_socket_transform(b,u.RelativeTransformSpace.RTS_COMPONENT).translation for b in rlv_bones}
        knees=[rlv_knee(points,s) for s in ['l','r']]
        record[name+'_knees']=knees
        record[name+'_error']=max(abs(a-b) for a,b in zip(knees,record['authored_knees']))
    assert record['source_error']<5,record
    assert record['visible_error']<22,record
    return record

rlv_test=dict(phase='setup',index=0,sample=0,next=0,busy=False,results=[],deadline=time.monotonic()+180)
def rlv_finish(error=None):
    u.unregister_slate_post_tick_callback(rlv_test['handle']);rlv_test.update(finished=True,error=error)
    ws=u.EditorLevelLibrary.get_pie_worlds(False)
    if ws:u.GameplayStatics.set_global_time_dilation(ws[0],1)
    if rlv_test.get('camera'):rlv_test['camera'].destroy_actor()
    (rlv_out/'validation.json').write_text(json.dumps(dict(passed=error is None,error=error,results=rlv_test['results']),indent=2)+'\n')
    print('ROLL_LEGS',error)

def rlv_tick(dt):
    if rlv_test['busy']:return
    rlv_test['busy']=True
    try:
        assert time.monotonic()<rlv_test['deadline'],'Roll leg pose checks timed out'
        ws=u.EditorLevelLibrary.get_pie_worlds(False)
        if not ws:return
        w=ws[0];p=u.GameplayStatics.get_player_pawn(w,0)
        if not p or not p.physical_interaction.controls_created:return
        now=u.GameplayStatics.get_time_seconds(w);phase=rlv_test['phase'];anim=p.mesh.get_anim_instance()
        if rlv_test.get('camera'):
            at=p.get_actor_location();loc=at+u.Vector(90,-340,90);camera=rlv_test['camera']
            camera.set_actor_location(loc,False,True);camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(loc,at+u.Vector(0,0,-15)),False)
        if now<rlv_test['next']:return
        if phase=='setup':
            u.GameplayStatics.set_global_time_dilation(w,.3)
            camera=u.CRBlueprintTools.spawn_pie_test_actor(w,u.SceneCapture2D,u.Transform())
            capture=camera.get_component_by_class(u.SceneCaptureComponent2D)
            capture.set_editor_property('capture_every_frame',True);capture.set_editor_property('always_persist_rendering_state',True)
            capture.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR);capture.set_editor_property('fov_angle',48)
            texture=u.RenderingLibrary.create_render_target2d(w,1000,850,u.TextureRenderTargetFormat.RTF_RGBA8);capture.set_editor_property('texture_target',texture)
            rlv_test.update(camera=camera,texture=texture,phase='place',next=now+.1)
        elif phase=='place':
            p.character_movement.stop_movement_immediately();p.un_crouch()
            p.set_actor_location(u.Vector(5000,2500,94),False,True);p.set_actor_rotation(u.Rotator(),False);p.get_controller().set_control_rotation(u.Rotator())
            rlv_test.update(phase='roll',next=now+.3)
        elif phase=='roll':
            angle=math.radians(45*rlv_test['index'])
            assert p.roll.request_roll(u.Vector(math.cos(angle),math.sin(angle),0))
            rlv_test.update(phase='sample',sample=0)
        elif phase=='sample':
            montage=anim.get_current_active_montage();assert montage,'Roll stopped before pose sampling'
            position=anim.montage_get_position(montage)
            if position<[.34,.48,.62][rlv_test['sample']]:return
            result=rlv_measure(p);rlv_test['results'].append(result)
            name=rlv_rows[rlv_test['index']]['direction']+'_'+str(rlv_test['sample'])+'.png'
            u.RenderingLibrary.export_render_target(w,rlv_test['texture'],str(rlv_out),name)
            rlv_test['sample']+=1
            if rlv_test['sample']==3:rlv_test.update(phase='restore',next=now+1.3)
        elif phase=='restore':
            assert not p.roll.is_rolling() and anim.locomotion_correction_bypass_weight==0,'Standing foot IK did not return'
            assert p.can_use_movement_actions()
            rlv_test['index']+=1
            if rlv_test['index']==8:rlv_finish();return
            rlv_test.update(phase='place',next=now+.1)
    except Exception:rlv_finish(traceback.format_exc())
    finally:rlv_test['busy']=False
rlv_test['handle']=u.register_slate_post_tick_callback(rlv_tick)
print('ROLL_LEG_POSE_CHECKS_STARTED')
