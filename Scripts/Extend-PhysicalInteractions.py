"""Connect the UE 5.8 Physics Control and paired motion matching samples to CMC."""
from pathlib import Path
import json
import unreal as u

lib=u.EditorAssetLibrary
asset_tools=u.AssetToolsHelpers.get_asset_tools()
root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent

def save(obj):
    if isinstance(obj,u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(obj)
        assert not u.CRBlueprintTools.has_blueprint_errors(obj),obj.get_path_name()
    assert lib.save_loaded_asset(obj,only_if_is_dirty=False),obj.get_path_name()

def key(name):
    k=u.Key()
    assert k.import_text(name)
    return k

character=u.load_asset('/Game/Blueprints/SandboxCharacter_CMC')
animation=u.load_asset('/Game/Blueprints/SandboxCharacter_CMC_ABP')
u.BlueprintEditorLibrary.reparent_blueprint(animation,u.BaselineSourceAnimInstance)
assert u.CRBlueprintTools.configure_physical_animation(character,animation)
# The get-up schema samples hands as well as the locomotion bones. Without
# these entries Pose Search substitutes missing data when comparing landings.
history_nodes=[node for node in u.ObjectIterator(u.AnimGraphNode_PoseSearchHistoryCollector)
               if node.get_path_name().startswith(animation.get_path_name()+':')]
assert len(history_nodes)==1
history=history_nodes[0].get_editor_property('node')
bones=list(history.get_editor_property('collected_bones'))
for name in ['hand_l','hand_r']:
    if not any(str(bone.get_editor_property('bone_name'))==name for bone in bones):
        bone=u.BoneReference()
        bone.set_editor_property('bone_name',name)
        bones.append(bone)
history.set_editor_property('collected_bones',bones)
history_nodes[0].set_editor_property('node',history)
save(animation)
cdo=u.get_default_object(character.generated_class())
physical=cdo.get_editor_property('physical_interaction')
base='/Game/Characters/UEFN_Mannequin'
physical.set_editor_property('control_profile',u.load_asset(base+'/Rigs/PCA_SandboxCharacter'))
chooser=u.load_asset(base+'/Animations/Ragdoll/CHT_GetUpMontages')
getup=u.load_object(None,chooser.get_path_name()+':PSD_GetUp')
assert getup
getup_path='/Game/Baseline/Animations/PSD_PhysicalGetUp'
getup=u.load_asset(getup_path) if lib.does_asset_exist(getup_path) else asset_tools.duplicate_asset('PSD_PhysicalGetUp','/Game/Baseline/Animations',getup)
assert getup
getup_assets=[]
for direction in ['F','B','L','R']:
    montage=u.load_asset(base+'/Animations/Ragdoll/AM_M_ragdoll_getup_stand_'+direction)
    assert montage
    getup_assets.append('(AnimAsset="'+montage.get_path_name()+'")')
assert u.CRBlueprintTools.set_property_text(getup,'DatabaseAnimationAssets','('+','.join(getup_assets)+')')
save(getup)
physical.set_editor_property('get_up_database',getup)
physical.set_editor_property('shove_database',u.load_asset(base+'/Animations/Interactions/Shoves/PSD_Interaction_Shove'))
physical.set_editor_property('tackle_database',u.load_asset(base+'/Animations/Interactions/Tackle/PSD_Interaction_Tackle'))
physical.set_editor_property('takedown_databases',[u.load_asset(base+'/Animations/Interactions/Takedowns/PSD_Interaction_takedown_'+speed) for speed in ['stand','Walk','Run']])
save(character)
pawn=u.load_asset('/Game/Crusader/Characters/B_CRTraversalPawn')
save(pawn)

mapping=u.load_asset('/Game/Baseline/Input/IMC_Baseline')
controls={}
for name,keyboard,gamepad in [('Ragdoll','T','Gamepad_DPad_Right'),('Shove','F','Gamepad_RightThumbstick'),('Tackle','V','Gamepad_DPad_Left'),('Takedown','B','Gamepad_LeftThumbstick')]:
    path='/Game/Baseline/Input/IA_'+name
    action=u.load_asset(path) if lib.does_asset_exist(path) else asset_tools.create_asset('IA_'+name,'/Game/Baseline/Input',u.InputAction,u.InputAction_Factory())
    action.set_editor_property('value_type',u.InputActionValueType.BOOLEAN)
    action.set_editor_property('triggers',[])
    save(action)
    # Replace the sample's pawn/visual cycling and strafe shortcuts on these
    # buttons so a physical action cannot also swap the active character.
    for entry in list(mapping.get_editor_property('default_key_mappings').get_editor_property('mappings')):
        if entry.key.export_text() in [keyboard,gamepad] and entry.action!=action:
            mapping.unmap_key(entry.action,entry.key)
    mapping.unmap_all_keys_from_action(action)
    mapping.map_key(action,key(keyboard))
    mapping.map_key(action,key(gamepad))
    controls[keyboard]=name
save(mapping)

path='/Game/Baseline/Characters/B_TrainingPartner'
if lib.does_asset_exist(path):partner=u.load_asset(path)
else:
    factory=u.BlueprintFactory()
    factory.set_editor_property('parent_class',pawn.generated_class())
    partner=asset_tools.create_asset('B_TrainingPartner','/Game/Baseline/Characters',u.Blueprint,factory)
partner_defaults=u.get_default_object(partner.generated_class())
partner_defaults.set_editor_property('auto_possess_ai',u.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)
partner_defaults.set_editor_property('ai_controller_class',u.LyraPlayerBotController)
partner_defaults.get_editor_property('physical_interaction').set_editor_property('auto_recover',True)
# Placed partners use the same lifecycle data as player-spawned characters.
extension=partner_defaults.get_component_by_class(u.LyraPawnExtensionComponent)
assert u.CRBlueprintTools.set_property_text(extension,'PawnData','/Script/LyraGame.LyraPawnData\'/Game/Crusader/System/PawnData_CRTraversal.PawnData_CRTraversal\'')
save(partner)

level=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert level.load_level('/Game/Maps/L_TraversalGym')
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
existing={a.get_actor_label():a for a in actors.get_all_level_actors()}
for i,position in enumerate([(2550,-1100,94),(2550,-1650,94)]):
    label='Baseline_TrainingPartner_'+str(i+1)
    actor=existing.get(label)
    if actor is None:actor=actors.spawn_actor_from_class(partner.generated_class(),u.Vector(*position),u.Rotator(yaw=180))
    actor.set_actor_label(label)
    actor.set_actor_location(u.Vector(*position),False,True)
    actor.set_actor_rotation(u.Rotator(yaw=180),False)
sign=existing.get('Baseline_InteractionSign')
if sign is None:sign=actors.spawn_actor_from_class(u.TextRenderActor,u.Vector(2780,-1100,240),u.Rotator(yaw=180))
sign.set_actor_label('Baseline_InteractionSign')
sign.text_render.set_text('PHYSICAL INTERACTIONS\nF: Shove   V: Tackle   B: Takedown\nT: Ragdoll / Get up   Space: Get up\nApproach and face a training partner')
sign.text_render.set_world_size(24)
assert level.save_current_level()
(root/'Artifacts/PhysicalAuthoring.json').write_text(json.dumps({'controls':controls,'getup_database':getup.get_path_name(),'character':pawn.get_path_name(),'training_partner':partner.get_path_name()},indent=2))
u.log('PHYSICAL_INTERACTION_AUTHORING_COMPLETE')

