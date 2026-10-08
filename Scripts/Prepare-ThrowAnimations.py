"""Retarget the installed ThrowSystem aim/throw onto the GASP source skeleton."""
import json
from pathlib import Path
import unreal as u

ta_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
ta_folder='/Game/Crusader/Equipment/Throw'
ta_lib=u.EditorAssetLibrary;ta_tools=u.AssetToolsHelpers.get_asset_tools()
def ta_create(name,cls,factory):
    return u.load_asset(ta_folder+'/'+name) if ta_lib.does_asset_exist(ta_folder+'/'+name) else ta_tools.create_asset(name,ta_folder,cls,factory)
def ta_save(a):assert ta_lib.save_loaded_asset(a,only_if_is_dirty=False)
ta_source=u.load_asset('/Game/ThrowSystem/Demo/Characters/Mannequins/Meshes/SKM_Manny')
ta_target=u.load_asset('/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin')
ta_rig=ta_create('IK_ThrowPack',u.IKRigDefinition,u.IKRigDefinitionFactory())
ta_rc=u.IKRigController.get_controller(ta_rig);assert ta_rc.set_skeletal_mesh(ta_source)
assert ta_rc.apply_auto_generated_retarget_definition();assert ta_rc.apply_auto_fbik()
if not any(str(c.chain_name)=='Root' for c in ta_rc.get_retarget_chains()):ta_rc.add_retarget_chain('Root','root','root','None')
ta_save(ta_rig)
ta_rt=ta_create('RTG_ThrowPack_to_GASP',u.IKRetargeter,u.IKRetargetFactory())
ta_c=u.IKRetargeterController.get_controller(ta_rt)
ta_c.set_ik_rig(u.RetargetSourceOrTarget.SOURCE,ta_rig)
ta_c.set_ik_rig(u.RetargetSourceOrTarget.TARGET,u.load_asset('/Game/Characters/UEFN_Mannequin/Rigs/IK_UEFN_Mannequin'))
ta_c.set_preview_mesh(u.RetargetSourceOrTarget.SOURCE,ta_source);ta_c.set_preview_mesh(u.RetargetSourceOrTarget.TARGET,ta_target)
ta_c.remove_all_ops();ta_c.add_default_ops();ta_c.auto_map_chains(u.AutoMapChainType.FUZZY,True)
ta_c.set_source_chain('Root','Root')
ta_root_op=ta_c.get_op_controller(ta_c.get_index_of_op_by_name('Root Motion'))
ta_root_op.set_source_root_bone('root');ta_root_op.set_target_root_bone('root');ta_root_op.set_target_pelvis_bone('pelvis')
ta_pin=ta_c.get_op_controller(ta_c.add_retarget_op(u.IKRetargetPinBoneOp.static_struct().get_path_name()))
for side in ['l','r']:ta_pin.set_bone_pair('foot_'+side,'ik_foot_'+side)
ta_c.auto_align_all_bones(u.RetargetSourceOrTarget.TARGET);ta_save(ta_rt)
ta_inputs=u.IKRetargetBatchOperationInputs()
ta_inputs.set_editor_properties(dict(assets_to_retarget=[ta_lib.find_asset_data('/Game/ThrowSystem/Animations/AS_'+n) for n in ['Aim','Throw']],source_mesh=ta_source,target_mesh=ta_target,ik_retarget_asset=ta_rt,target_path=ta_folder+'/Animations',prefix='GASP_',include_referenced_assets=False,overwrite_existing_files=True))
assert len(u.IKRetargetBatchOperation.run_batch_retarget(ta_inputs))==2
ta_results=[]
for n in ['Aim','Throw']:
    seq=u.load_asset(ta_folder+'/Animations/GASP_AS_'+n);seq.set_editor_property('enable_root_motion',False);ta_save(seq)
    f=u.AnimMontageFactory();f.set_editor_property('source_animation',seq);f.set_editor_property('target_skeleton',seq.get_editor_property('skeleton'))
    montage=ta_create('AM_'+n,u.AnimMontage,f);ta_save(montage)
    opts=u.AnimPoseEvaluationOptions();opts.set_editor_property('extract_root_motion',False);opts.set_editor_property('incorporate_root_motion_into_pose',True)
    pelvis_heights=[]
    for frame in range(u.AnimationLibrary.get_num_frames(seq)+1):
        pose=u.AnimPoseExtensions.get_anim_pose_at_time(seq,u.AnimationLibrary.get_time_at_frame(seq,frame),opts)
        pelvis=u.AnimPoseExtensions.get_bone_pose(pose,'pelvis',u.AnimPoseSpaces.WORLD).translation
        root=u.AnimPoseExtensions.get_bone_pose(pose,'root',u.AnimPoseSpaces.WORLD).translation
        pelvis_heights.append(pelvis.z-root.z)
    assert min(pelvis_heights)>75 and max(pelvis_heights)<120,(n,'Invalid standing pelvis height',pelvis_heights)
    ta_results.append(dict(animation=seq.get_path_name(),montage=montage.get_path_name(),duration=seq.sequence_length,pelvis_height_cm=[min(pelvis_heights),max(pelvis_heights)]))
(ta_root/'resources/ThrowAnimations.json').write_text(json.dumps(ta_results,indent=2)+'\n')
print('THROW_ANIMATIONS_PREPARED',ta_results)
