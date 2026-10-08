"""Retarget the purchased eight-way standing rolls onto GASP's source skeleton."""
import json
from pathlib import Path
import unreal as u

ra_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
ra_folder='/Game/Crusader/Movement/Roll'
ra_lib=u.EditorAssetLibrary;ra_tools=u.AssetToolsHelpers.get_asset_tools()

def ra_save(a):assert ra_lib.save_loaded_asset(a,only_if_is_dirty=False)
def ra_create(name,cls,factory):
    return u.load_asset(ra_folder+'/'+name) if ra_lib.does_asset_exist(ra_folder+'/'+name) else ra_tools.create_asset(name,ra_folder,cls,factory)

ra_source=u.load_asset('/Game/RollDodgeDashSet/Demo/Mannequins/Meshes/SKM_Manny')
ra_target=u.load_asset('/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin')
ra_rig=ra_create('IK_RollPack',u.IKRigDefinition,u.IKRigDefinitionFactory())
ra_rc=u.IKRigController.get_controller(ra_rig);assert ra_rc.set_skeletal_mesh(ra_source)
assert ra_rc.apply_auto_generated_retarget_definition();assert ra_rc.apply_auto_fbik()
if not any(str(c.chain_name)=='Root' for c in ra_rc.get_retarget_chains()):ra_rc.add_retarget_chain('Root','root','root','None')
ra_save(ra_rig)
ra_retarget=ra_create('RTG_RollPack_to_GASP',u.IKRetargeter,u.IKRetargetFactory())
ra_controller=u.IKRetargeterController.get_controller(ra_retarget)
ra_controller.set_ik_rig(u.RetargetSourceOrTarget.SOURCE,ra_rig)
ra_controller.set_ik_rig(u.RetargetSourceOrTarget.TARGET,u.load_asset('/Game/Characters/UEFN_Mannequin/Rigs/IK_UEFN_Mannequin'))
ra_controller.set_preview_mesh(u.RetargetSourceOrTarget.SOURCE,ra_source)
ra_controller.set_preview_mesh(u.RetargetSourceOrTarget.TARGET,ra_target)
ra_controller.remove_all_ops();ra_controller.add_default_ops()
ra_controller.auto_map_chains(u.AutoMapChainType.FUZZY,True)
ra_controller.set_source_chain('Root','Root')
ra_root_op=ra_controller.get_op_controller(ra_controller.get_index_of_op_by_name('Root Motion'))
ra_root_op.set_source_root_bone('root')
ra_root_op.set_target_root_bone('root')
ra_root_op.set_target_pelvis_bone('pelvis')
# The humanoid retarget chains do not animate the auxiliary IK foot bones.
# Bake them onto the animated feet after all root/limb operations; leaving them
# at the reference pose makes GASP's leg solver stretch the knees during a roll.
ra_pin_index=ra_controller.add_retarget_op(u.IKRetargetPinBoneOp.static_struct().get_path_name())
assert ra_pin_index>=0
ra_pin=ra_controller.get_op_controller(ra_pin_index)
for side in ['l','r']:ra_pin.set_bone_pair('foot_'+side,'ik_foot_'+side)
for side in [u.RetargetSourceOrTarget.SOURCE,u.RetargetSourceOrTarget.TARGET]:
    for pose in ra_controller.get_retarget_poses(side):ra_controller.reset_retarget_pose(pose,[],side)
ra_controller.auto_align_all_bones(u.RetargetSourceOrTarget.TARGET)
ra_save(ra_retarget)
ra_names=['Fwd','FwdRt_45','FwdRt_90','BwdRt_135','Bwd','BwdLt_135','FwdLt_90','FwdLt_45']
ra_source_paths=['/Game/RollDodgeDashSet/Animations/RootMotion/Mannequin/Roll/A_Roll_Idle'+n for n in ra_names]
ra_input=u.IKRetargetBatchOperationInputs()
ra_input.set_editor_properties(dict(assets_to_retarget=[ra_lib.find_asset_data(p) for p in ra_source_paths],source_mesh=ra_source,target_mesh=ra_target,ik_retarget_asset=ra_retarget,target_path=ra_folder+'/Animations',prefix='GASP_',include_referenced_assets=False,overwrite_existing_files=True))
ra_outputs=u.IKRetargetBatchOperation.run_batch_retarget(ra_input)
assert len(ra_outputs)==8,len(ra_outputs)
ra_report=[]
for index,name in enumerate(ra_names):
    seq=u.load_asset(ra_folder+'/Animations/GASP_A_Roll_Idle'+name)
    assert seq and seq.get_editor_property('skeleton')==ra_target.get_editor_property('skeleton')
    seq.set_editor_property('enable_root_motion',True)
    seq.set_editor_property('root_motion_root_lock',u.RootMotionRootLock.ANIM_FIRST_FRAME)
    ra_save(seq)
    factory=u.AnimMontageFactory();factory.set_editor_property('source_animation',seq)
    factory.set_editor_property('target_skeleton',seq.get_editor_property('skeleton'))
    montage=ra_create('AM_Roll_'+name,u.AnimMontage,factory)
    # Dynamic factory defaults use DefaultSlot, shared by the existing GASP full-body actions.
    assert len(montage.get_editor_property('slot_anim_tracks'))==1
    ra_save(montage)
    opts=u.AnimPoseEvaluationOptions();opts.set_editor_property('extract_root_motion',False)
    opts.set_editor_property('incorporate_root_motion_into_pose',True)
    poses=[u.AnimPoseExtensions.get_anim_pose_at_time(seq,t,opts) for t in [0,seq.sequence_length]]
    roots=[u.AnimPoseExtensions.get_bone_pose(p,'root',u.AnimPoseSpaces.WORLD).translation for p in poses]
    delta=roots[1]-roots[0]
    assert 350<delta.length()<550,(name,delta)
    ik_errors=[]
    for frame in range(u.AnimationLibrary.get_num_frames(seq)+1):
        pose=u.AnimPoseExtensions.get_anim_pose_at_time(seq,u.AnimationLibrary.get_time_at_frame(seq,frame),opts)
        for side in ['l','r']:
            foot=u.AnimPoseExtensions.get_bone_pose(pose,'foot_'+side,u.AnimPoseSpaces.WORLD).translation
            goal=u.AnimPoseExtensions.get_bone_pose(pose,'ik_foot_'+side,u.AnimPoseSpaces.WORLD).translation
            ik_errors.append((foot-goal).length())
    assert max(ik_errors)<.01,(name,'IK feet detached at baked keys',max(ik_errors))
    ra_report.append(dict(index=index,direction=name,source=ra_source_paths[index],animation=seq.get_path_name(),montage=montage.get_path_name(),duration=seq.sequence_length,root_delta=[delta.x,delta.y,delta.z],maximum_baked_foot_ik_error_cm=max(ik_errors)))
(ra_root/'resources/RollAnimations.json').write_text(json.dumps(ra_report,indent=2)+'\n')
print('ROLL_ANIMATIONS_PREPARED',json.dumps(ra_report))
