"""Grant the roll GAS ability and bind one-press Enhanced Input on the GASP pawn."""
import json
from pathlib import Path
import unreal as u

rr_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
rr_lib=u.EditorAssetLibrary

def rr_save(a):
    if isinstance(a,u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(a)
        assert not u.CRBlueprintTools.has_blueprint_errors(a),a.get_path_name()
    assert rr_lib.save_loaded_asset(a,only_if_is_dirty=False)

rr_montages=[u.load_asset(r['montage']) for r in json.loads((rr_root/'resources/RollAnimations.json').read_text())]
assert len(rr_montages)==8 and all(rr_montages)
rr_source=u.load_asset('/Game/Blueprints/SandboxCharacter_CMC_ABP')
assert u.CRBlueprintTools.configure_physical_animation(u.load_asset('/Game/Blueprints/SandboxCharacter_CMC'),rr_source)
rr_save(rr_source)
for path in ['/Game/Blueprints/SandboxCharacter_CMC','/Game/Crusader/Characters/B_CRTraversalPawn']:
    bp=u.load_asset(path);roll=u.get_default_object(bp.generated_class()).roll
    roll.set_editor_property('montages',rr_montages)
    roll.set_editor_property('play_rate',1.15);roll.set_editor_property('recovery_time',.55)
    rr_save(bp)
for role in ['GuardRifle','GuardPistol','GuardShotgun','Civilian']:
    bp=u.load_asset('/Game/Crusader/AI/B_'+role);rr_save(bp)
    assert len(u.get_default_object(bp.generated_class()).roll.get_editor_property('montages'))==8,role

ability_set=u.load_asset('/Game/Crusader/System/AbilitySet_CRTraversal')
entries=list(ability_set.get_editor_property('granted_gameplay_abilities'))
entries=[e for e in entries if e.get_editor_property('ability')!=u.CRRollAbility.static_class()]
entry=u.LyraAbilitySet_GameplayAbility()
assert entry.import_text('(Ability="/Script/CoreUObject.Class\'/Script/LyraGame.CRRollAbility\'",AbilityLevel=1,InputTag=(TagName="InputTag.Movement.Roll"))')
entries.append(entry);ability_set.set_editor_property('granted_gameplay_abilities',entries);rr_save(ability_set)

path='/Game/Baseline/Input/IA_Roll'
action=u.load_asset(path) if rr_lib.does_asset_exist(path) else u.AssetToolsHelpers.get_asset_tools().create_asset('IA_Roll','/Game/Baseline/Input',u.InputAction,u.InputAction_Factory())
action.set_editor_property('value_type',u.InputActionValueType.BOOLEAN)
action.set_editor_property('triggers',[u.new_object(u.InputTriggerPressed,outer=action)])
rr_save(action)
mapping=u.load_asset('/Game/Baseline/Input/IMC_Baseline')
def rr_key(name):
    result=u.Key();assert result.import_text(name);return result
mapping.unmap_all_keys_from_action(action)
# Keep the ragdoll debug action on T; reserve this controller button for gameplay.
mapping.unmap_key(u.load_asset('/Game/Baseline/Input/IA_Ragdoll'),rr_key('Gamepad_DPad_Right'))
mapping.map_key(action,rr_key('LeftAlt'));mapping.map_key(action,rr_key('Gamepad_DPad_Right'));rr_save(mapping)
config=u.load_asset('/Game/Crusader/System/InputConfig_CRTraversal')
inputs=[e for e in config.get_editor_property('ability_input_actions') if e.get_editor_property('input_action')!=action]
entry=u.LyraInputAction();assert entry.import_text('(InputAction="'+action.get_path_name()+'",InputTag=(TagName="InputTag.Movement.Roll"))')
inputs.append(entry);config.set_editor_property('ability_input_actions',inputs);rr_save(config)
print('ROLL_CONFIGURED','LeftAlt / Gamepad D-pad Right',len(rr_montages),'directions, predicted GAS, .55s recovery')
