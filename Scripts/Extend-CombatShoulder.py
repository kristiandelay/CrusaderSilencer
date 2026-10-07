"""Author fatal combat and mirrored weapon handling on the existing baseline."""
import unreal as u

lib = u.EditorAssetLibrary
asset_tools = u.AssetToolsHelpers.get_asset_tools()
assert not u.EditorLevelLibrary.get_pie_worlds(False), 'Stop PIE before authoring assets'


def combat_save(asset):
    if isinstance(asset, u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(asset)
        assert not u.CRBlueprintTools.has_blueprint_errors(asset), asset.get_path_name()
    assert lib.save_loaded_asset(asset, only_if_is_dirty=False)


mirror_path = '/Game/Baseline/Animations/MDT_WeaponHands'
table = u.load_asset(mirror_path) if lib.does_asset_exist(mirror_path) else asset_tools.duplicate_asset(
    'MDT_WeaponHands', '/Game/Baseline/Animations', u.load_asset('/Game/Characters/UEFN_Mannequin/Rigs/MDT_UEFN_Mannequin'))
assert u.CRBlueprintTools.configure_weapon_mirror_table(table, u.load_asset('/Game/Characters/UE5_Mannequins/Meshes/SK_Mannequin'))
combat_save(table)
animation = u.load_asset('/Game/Baseline/Animations/ABP_BaselineManny')
defaults = u.get_default_object(animation.generated_class())
assert u.CRBlueprintTools.build_weapon_overlay(animation, defaults.weapon_pose, defaults.weapon_aim_offset)
combat_save(animation)

path = '/Game/Baseline/Input/IA_Shoulder'
action = u.load_asset(path) if lib.does_asset_exist(path) else asset_tools.create_asset(
    'IA_Shoulder', '/Game/Baseline/Input', u.InputAction, u.InputAction_Factory())
action.set_editor_property('value_type', u.InputActionValueType.BOOLEAN)
action.set_editor_property('triggers', [])
combat_save(action)
mapping = u.load_asset('/Game/Baseline/Input/IMC_Baseline')
mapping.unmap_all_keys_from_action(action)
for name in ['Q', 'Gamepad_FaceButton_Top']:
    key = u.Key()
    assert key.import_text(name)
    for entry in list(mapping.get_editor_property('default_key_mappings').get_editor_property('mappings')):
        if entry.key.export_text() == key.export_text():
            mapping.unmap_key(entry.action, key)
    mapping.map_key(action, key)
combat_save(mapping)

ability_set = u.load_asset('/Game/Crusader/System/AbilitySet_CRTraversal')
grants = [g for g in ability_set.get_editor_property('granted_gameplay_abilities')
          if 'Death' not in g.get_editor_property('ability').get_name()]
death = u.LyraAbilitySet_GameplayAbility()
assert death.import_text('(Ability="/Script/LyraGame.BaselineDeathAbility",AbilityLevel=1)')
grants.append(death)
ability_set.set_editor_property('granted_gameplay_abilities', grants)
combat_save(ability_set)

for kind in ['Rifle', 'Pistol', 'Shotgun']:
    weapons = u.load_asset('/Game/Baseline/Weapons/' + kind + '/AbilitySet_' + kind)
    for grant in weapons.get_editor_property('granted_gameplay_abilities'):
        ability_class = grant.get_editor_property('ability')
        blueprint = u.load_asset(ability_class.get_path_name().split('.')[0])
        default = u.get_default_object(ability_class)
        if 'Fire' in blueprint.get_name() and kind in ['Rifle', 'Shotgun']:
            # Keep the baseline's damage effect inside project content, matching
            # the other copied weapon assets and the project's reference rules.
            original = default.get_editor_property('GE_Damage')
            damage_path = '/Game/Baseline/Weapons/' + kind + '/' + original.get_name().removesuffix('_C')
            damage = u.load_asset(damage_path) if lib.does_asset_exist(damage_path) else asset_tools.duplicate_asset(
                damage_path.rsplit('/',1)[1], damage_path.rsplit('/',1)[0], u.load_asset(original.get_path_name().split('.')[0]))
            combat_save(damage)
            default.set_editor_property('GE_Damage', damage.generated_class())
        tags = default.get_editor_property('activation_blocked_tags')
        value = tags.export_text()
        for tag in ['Status.Death', 'Baseline.State.ChangingShoulder']:
            if 'TagName="' + tag + '"' not in value:
                value = ('(GameplayTags=((TagName="' + tag + '")))' if value == '(GameplayTags=)' else
                         value.replace('GameplayTags=(', 'GameplayTags=((TagName="' + tag + '"),', 1))
        assert tags.import_text(value)
        default.set_editor_property('activation_blocked_tags', tags)
        combat_save(blueprint)

for path in ['/Game/Blueprints/SandboxCharacter_CMC', '/Game/Crusader/Characters/B_CRTraversalPawn',
             '/Game/Baseline/Characters/B_TrainingPartner']:
    combat_save(u.load_asset(path))
print('Combat death, shoulder controls and mirrored weapon animations saved')
