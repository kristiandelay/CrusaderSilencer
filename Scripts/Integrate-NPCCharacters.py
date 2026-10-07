"""Register four fitted guards/NPCs in the existing visual override catalog."""
import json
from pathlib import Path
import unreal as u

assert not u.EditorLevelLibrary.get_pie_worlds(False)
lib=u.EditorAssetLibrary
tools=u.AssetToolsHelpers.get_asset_tools()
sub=u.get_engine_subsystem(u.SubobjectDataSubsystem)
data=u.SubobjectDataBlueprintFunctionLibrary

def save(asset):
    if isinstance(asset,u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(asset)
        assert not u.CRBlueprintTools.has_blueprint_errors(asset),asset.get_path_name()
    assert lib.save_loaded_asset(asset,only_if_is_dirty=False)

def duplicate(source,target):
    return u.load_asset(target) if lib.does_asset_exist(target) else lib.duplicate_asset(source,target)

def cdo(asset):return u.get_default_object(asset.generated_class())

for name in ['ObsidianSentinel','RegalCommander','TheSteadfastOfficer','UrbanTrailblazer']:
    character_folder='/Game/Crusader/Characters/'+name
    mesh=u.load_asset(character_folder+'/'+name)
    rig_path=character_folder+'/IK_'+name
    rig=u.load_asset(rig_path) if lib.does_asset_exist(rig_path) else tools.create_asset('IK_'+name,character_folder,u.IKRigDefinition,u.IKRigDefinitionFactory())
    controller=u.IKRigController.get_controller(rig)
    assert controller.set_skeletal_mesh(mesh)
    assert controller.apply_auto_generated_retarget_definition(),'UE humanoid chain recognition failed'
    assert controller.apply_auto_fbik(),'UE humanoid full-body IK generation failed'
    save(rig)
    print('IK_RIG_CHAINS',len(controller.get_retarget_chains()))
    retarget=duplicate('/Game/Baseline/Animations/VisualOverrides/RTG_Manny_to_UE5_Mannequin',character_folder+'/RTG_Manny_to_'+name)
    controller=u.IKRetargeterController.get_controller(retarget)
    controller.set_ik_rig(u.RetargetSourceOrTarget.TARGET,rig)
    controller.set_preview_mesh(u.RetargetSourceOrTarget.TARGET,mesh)
    controller.auto_map_chains(u.AutoMapChainType.FUZZY,True)
    for pose in controller.get_retarget_poses(u.RetargetSourceOrTarget.TARGET):
        controller.reset_retarget_pose(pose,[],u.RetargetSourceOrTarget.TARGET)
    controller.auto_align_all_bones(u.RetargetSourceOrTarget.TARGET)
    blend=controller.get_op_controller(controller.get_index_of_op_by_name('Blend to Source'))
    if blend:
        settings=blend.get_settings();chains=list(settings.chains)
        for chain in chains:
            if str(chain.target_chain_name) in ['LeftArm','RightArm']:
                chain.set_editor_property('blend_to_source',1.0);chain.set_editor_property('apply_pelvis_offset',1.0)
        settings.set_editor_property('chains',chains);blend.set_settings(settings)
    save(retarget)
    animation=u.load_asset('/Game/Baseline/Animations/ABP_BaselineVisualRetarget')
    mapping=cdo(animation).get_editor_property('IKRetargeter_Map')
    mapping['RTG_Manny_to_'+name]=retarget
    cdo(animation).set_editor_property('IKRetargeter_Map',mapping)
    save(animation)
    visual=duplicate('/Game/Blueprints/RetargetedCharacters/BP_Manny',character_folder+'/BP_'+name)
    seen=set()
    for handle in sub.k2_gather_subobject_data_for_blueprint(visual):
        component=data.get_object_for_blueprint(data.get_data(handle),visual)
        if isinstance(component,u.SkeletalMeshComponent) and component.get_path_name() not in seen:
            component.set_editor_property('skeletal_mesh_asset',mesh)
            component.set_editor_property('anim_class',animation.generated_class())
            component.set_editor_property('component_tags',['RTG_Manny_to_'+name])
            seen.add(component.get_path_name())
    assert len(seen)==1,seen
    save(visual)
    catalog=u.load_asset('/Game/Blueprints/GM_Sandbox')
    entries=list(cdo(catalog).get_editor_property('VisualOverrides_Soft'))
    class_path=visual.generated_class().get_path_name()
    if not any(entry and entry.get_path_name()==class_path for entry in entries):
        entries.append(visual.generated_class())
    cdo(catalog).set_editor_property('VisualOverrides_Soft',entries)
    save(catalog)
    print('CATALOG_COUNT',len(entries))
    
print('NPC_INTEGRATION_COMPLETE')
