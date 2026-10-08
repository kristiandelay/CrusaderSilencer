"""Bake real left-hand throws, preserving standing pelvis and mirrored object grip."""
import json
from pathlib import Path
import unreal as u
ts_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
ts_folder='/Game/Crusader/Equipment/Throw';ts_lib=u.EditorAssetLibrary;ts_tools=u.AssetToolsHelpers.get_asset_tools()
ts_inputs=u.IKRetargetBatchOperationInputs()
ts_inputs.set_editor_properties(dict(assets_to_retarget=[ts_lib.find_asset_data('/Game/ThrowSystem/Animations/AS_'+n) for n in ['Aim','Throw']],
    source_mesh=u.load_asset('/Game/ThrowSystem/Demo/Characters/Mannequins/Meshes/SKM_Manny'),target_mesh=u.load_asset('/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin'),
    ik_retarget_asset=u.load_asset(ts_folder+'/RTG_ThrowPack_to_GASP'),target_path=ts_folder+'/Animations',prefix='GASP_Left_',include_referenced_assets=False,overwrite_existing_files=True))
assert len(u.IKRetargetBatchOperation.run_batch_retarget(ts_inputs))==2
ts_opts=u.AnimPoseEvaluationOptions();ts_opts.set_editor_property('extract_root_motion',False);ts_opts.set_editor_property('incorporate_root_motion_into_pose',True)
ts_modifier=u.new_object(u.MirrorModifier);ts_modifier.set_editor_property('mirror_data_table',u.load_asset('/Game/Characters/UEFN_Mannequin/Rigs/MDT_UEFN_Mannequin'))
ts_rows=[]
for name in ['Aim','Throw']:
    right=u.load_asset(ts_folder+'/Animations/GASP_AS_'+name);left=u.load_asset(ts_folder+'/Animations/GASP_Left_AS_'+name)
    ts_modifier.on_apply(left);left.set_editor_property('enable_root_motion',False)
    assert ts_lib.save_loaded_asset(left,only_if_is_dirty=False)
    path=ts_folder+'/AM_Left_'+name
    if ts_lib.does_asset_exist(path):montage=u.load_asset(path)
    else:
        f=u.AnimMontageFactory();f.set_editor_property('source_animation',left);f.set_editor_property('target_skeleton',left.get_editor_property('skeleton'))
        montage=ts_tools.create_asset('AM_Left_'+name,ts_folder,u.AnimMontage,f)
    assert ts_lib.save_loaded_asset(montage,only_if_is_dirty=False)
    errors=[];heights=[]
    for frame in range(u.AnimationLibrary.get_num_frames(left)+1):
        time_value=u.AnimationLibrary.get_time_at_frame(left,frame)
        rp=u.AnimPoseExtensions.get_anim_pose_at_time(right,time_value,ts_opts);lp=u.AnimPoseExtensions.get_anim_pose_at_time(left,time_value,ts_opts)
        for side,other in [('l','r'),('r','l')]:
            a=u.AnimPoseExtensions.get_bone_pose(rp,'hand_'+side,u.AnimPoseSpaces.WORLD).translation
            b=u.AnimPoseExtensions.get_bone_pose(lp,'hand_'+other,u.AnimPoseSpaces.WORLD).translation
            errors.append((u.Vector(-a.x,a.y,a.z)-b).length())
        heights.append(u.AnimPoseExtensions.get_bone_pose(lp,'pelvis',u.AnimPoseSpaces.WORLD).translation.z)
    assert max(errors)<.2,(name,errors)
    assert min(heights)>75,(name,heights)
    ts_rows.append(dict(name=name,left_animation=left.get_path_name(),left_montage=montage.get_path_name(),maximum_hand_mirror_error_cm=max(errors),minimum_pelvis_height_cm=min(heights)))
rp=u.AnimPoseExtensions.get_anim_pose_at_time(u.load_asset(ts_folder+'/Animations/GASP_AS_Aim'),0,ts_opts)
lp=u.AnimPoseExtensions.get_anim_pose_at_time(u.load_asset(ts_folder+'/Animations/GASP_Left_AS_Aim'),0,ts_opts)
rh=u.AnimPoseExtensions.get_bone_pose(rp,'hand_r',u.AnimPoseSpaces.WORLD);lh=u.AnimPoseExtensions.get_bone_pose(lp,'hand_l',u.AnimPoseSpaces.WORLD)
position=u.MathLibrary.transform_location(rh,u.Vector(4,0,0));q=rh.rotation
mirrored=u.Transform(location=u.Vector(-position.x,position.y,position.z),rotation=u.MathLibrary.quat_rotator(u.Quat(q.x,-q.y,-q.z,q.w)))
grip=u.MathLibrary.make_relative_transform(mirrored,lh)
ts_result=dict(animations=ts_rows,left_grip=grip.export_text())
(ts_root/'resources/ThrowShoulderAnimations.json').write_text(json.dumps(ts_result,indent=2)+'\n')
print('THROW_SHOULDER_ANIMATIONS',ts_result)
