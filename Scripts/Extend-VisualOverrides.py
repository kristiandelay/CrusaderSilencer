"""Connect the sample widget to Lyra while retaining the shared weapon pose."""
import unreal as u

assert not u.EditorLevelLibrary.get_pie_worlds(False), 'Stop PIE before authoring'
lib = u.EditorAssetLibrary
data = u.SubobjectDataBlueprintFunctionLibrary
sub = u.get_engine_subsystem(u.SubobjectDataSubsystem)


def visual_save(asset):
    if isinstance(asset, u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(asset)
        assert not u.CRBlueprintTools.has_blueprint_errors(asset), asset.get_path_name()
    assert lib.save_loaded_asset(asset, only_if_is_dirty=False)


def visual_duplicate(source, target):
    return u.load_asset(target) if lib.does_asset_exist(target) else lib.duplicate_asset(source, target)


manager = u.load_asset('/Game/Blueprints/AC_VisualOverrideManager')
catalog = u.load_class(None, '/Game/Blueprints/GM_Sandbox.GM_Sandbox_C')
assert u.CRBlueprintTools.configure_visual_override_fallback(manager, catalog)
visual_save(manager)

# Selected skins retarget the complete Manny pose, including the weapon layer.
# Keep source locomotion/physics and montage ownership on their existing meshes.
retargets = [
    ('UE4_Mannequin', '/Game/Characters/UE4_Mannequin/Rigs'),
    ('UE5_Mannequin', '/Game/Characters/UE5_Mannequins/Rigs'),
    ('Echo', '/Game/Characters/Echo/Rigs'),
    ('TwinBlast', '/Game/Characters/Paragon/Heroes/TwinBlast/Rigs'),
    ('Metahuman_nrw', '/Game/MetaHumans/Common/Common/Rigs'),
    ('Metahuman_ovw', '/Game/MetaHumans/Common/Common/Rigs'),
]
rig = u.load_asset('/Game/Characters/UE5_Mannequins/Rigs/IK_UE5_Mannequin_Retarget')
manny = u.load_asset('/Game/Characters/UE5_Mannequins/Meshes/SKM_Manny')
mapping = []
for target, folder in retargets:
    source_name = 'RTG_UEFN_to_' + target
    destination = '/Game/Baseline/Animations/VisualOverrides/RTG_Manny_to_' + target
    retarget = visual_duplicate(folder + '/' + source_name, destination)
    controller = u.IKRetargeterController.get_controller(retarget)
    controller.set_ik_rig(u.RetargetSourceOrTarget.SOURCE, rig)
    controller.set_preview_mesh(u.RetargetSourceOrTarget.SOURCE, manny)
    controller.auto_map_chains(u.AutoMapChainType.EXACT, True)
    for pose in controller.get_retarget_poses(u.RetargetSourceOrTarget.SOURCE):
        controller.reset_retarget_pose(pose, [], u.RetargetSourceOrTarget.SOURCE)
    # Keep the two hands the same distance apart for a shared weapon mesh,
    # while the target rig solves its own arm lengths and elbow positions.
    blend = controller.get_op_controller(controller.get_index_of_op_by_name('Blend to Source'))
    if blend:
        settings = blend.get_settings()
        chains = list(settings.chains)
        for chain in chains:
            if str(chain.target_chain_name) in ['LeftArm', 'RightArm']:
                chain.set_editor_property('blend_to_source', 1.0)
                chain.set_editor_property('apply_pelvis_offset', 1.0)
        settings.set_editor_property('chains', chains)
        blend.set_settings(settings)
    visual_save(retarget)
    mapping.append('("' + source_name + '","' + retarget.get_path_name() + '")')

animation = visual_duplicate('/Game/Blueprints/RetargetedCharacters/ABP_GenericRetarget',
                             '/Game/Baseline/Animations/ABP_BaselineVisualRetarget')
assert u.CRBlueprintTools.set_property_text(u.get_default_object(animation.generated_class()),
                                          'IKRetargeter_Map', '(' + ','.join(mapping) + ')')
visual_save(animation)

character = u.load_asset('/Game/Blueprints/SandboxCharacter_CMC')
for handle in sub.k2_gather_subobject_data_for_blueprint(character):
    component = data.get_object(data.get_data(handle))
    if isinstance(component, u.ChildActorComponent) and component.get_name().startswith('VisualOverride'):
        tags = [str(t) for t in component.component_tags if str(t) not in ['VisualOverride', 'BaselineAnimationSource']]
        component.set_editor_property('component_tags', tags + ['BaselineAnimationSource'])
    if isinstance(component, u.BaselineEquipmentComponent):
        component.set_editor_property('visual_retarget_animation', animation.generated_class())
visual_save(character)
for path in ['/Game/Crusader/Characters/B_CRTraversalPawn', '/Game/Baseline/Characters/B_TrainingPartner']:
    visual_save(u.load_asset(path))
print('Visual widget fallback, persistent weapon animation source and skin retargets saved')
