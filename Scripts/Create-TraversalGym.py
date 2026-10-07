"""Author the Lyra-owned GASP CMC gym using Unreal's asset APIs."""
import json
from pathlib import Path
import unreal as u

root = Path(__file__).resolve().parents[1]
out = root / 'Artifacts/GymAuthoring'
out.mkdir(parents=True, exist_ok=True)
tools = u.AssetToolsHelpers.get_asset_tools()
lib = u.EditorAssetLibrary
sub = u.get_engine_subsystem(u.SubobjectDataSubsystem)
data_lib = u.SubobjectDataBlueprintFunctionLibrary

def components(bp):
    return [data_lib.get_object(data_lib.get_data(h)) for h in sub.k2_gather_subobject_data_for_blueprint(bp)]

def save(obj):
    assert lib.save_loaded_asset(obj, only_if_is_dirty=False), obj.get_path_name()

def data_asset(name, cls, folder='/Game/Crusader/System'):
    path = folder + '/' + name
    if lib.does_asset_exist(path):
        return u.load_asset(path)
    factory = u.DataAssetFactory()
    factory.set_editor_property('data_asset_class', cls)
    return tools.create_asset(name, folder, cls, factory)

def duplicate(source, target):
    return u.load_asset(target) if lib.does_asset_exist(target) else lib.duplicate_asset(source, target)

character = u.load_asset('/Game/Blueprints/SandboxCharacter_CMC')
u.BlueprintEditorLibrary.reparent_blueprint(character, u.CRTraversalCharacter)
assert u.CRBlueprintTools.disconnect_function_entry(character, 'SetupInput')
assert u.CRBlueprintTools.disconnect_function_entry(character, 'SetupCamera')
u.BlueprintEditorLibrary.compile_blueprint(character)

# Apply only to packages that came from GASP, never to Lyra's own trace nodes.
remapped = {}
manifest = json.loads((root / 'Artifacts/source-manifest.json').read_text())
registry = u.AssetRegistryHelpers.get_asset_registry()
registry.search_all_assets(True)
for row in manifest['files']:
    if row['source'] != 'GASP' or not row['path'].endswith('.uasset'):
        continue
    path = '/Game/' + row['path'][len('Content/'):-len('.uasset')]
    asset_data = registry.get_asset_by_object_path(path + '.' + path.rsplit('/', 1)[1])
    if str(asset_data.asset_class_path.asset_name) not in ['Blueprint', 'AnimBlueprint']:
        continue
    bp = asset_data.get_asset()
    count = u.CRBlueprintTools.remap_gasp_trace_channels(bp)
    if count:
        u.BlueprintEditorLibrary.compile_blueprint(bp)
        save(bp)
        remapped[path] = count

# Use the sample's explicit UEFN-to-Manny IK retargeter with the actual Lyra mesh.
visual = duplicate('/Game/Blueprints/RetargetedCharacters/BP_Manny', '/Game/Crusader/Characters/B_CRMannequin')
lyra_mesh = u.load_asset('/Game/Characters/Heroes/Mannequin/Meshes/SKM_Manny')
for component in components(visual):
    if isinstance(component, u.SkeletalMeshComponent):
        component.set_skinned_asset_and_update(lyra_mesh)
u.BlueprintEditorLibrary.compile_blueprint(visual)
save(visual)

for component in components(character):
    name = component.get_name()
    if isinstance(component, u.ChildActorComponent) and name.startswith('VisualOverride'):
        component.set_editor_property('child_actor_class', visual.generated_class())
    if isinstance(component, u.CameraComponent) and name != 'CameraComponent':
        component.set_editor_property('auto_activate', False)
    if 'GameplayCamera' in name:
        component.set_editor_property('auto_activate', False)
        component.set_editor_property('run_standalone_camera_system', False)
        component.set_editor_property('run_in_editor', False)
        component.set_editor_property('default_player', u.AutoReceiveInput.DISABLED)
# Remove unused sample camera subobjects: an inactive GameplayCamera still creates
# a CineCamera output in UE 5.8, so deactivation alone leaves a second active camera.
u.CRBlueprintTools.remove_sample_camera_components(character)
cdo = u.get_default_object(character.generated_class())
cdo.mesh.set_visibility(False, False)
cdo.mesh.set_editor_property('visibility_based_anim_tick_option', u.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
u.BlueprintEditorLibrary.compile_blueprint(character)
save(character)

# Keep the source class in the ancestry: the source animation graph casts to it.
factory = u.BlueprintFactory()
factory.set_editor_property('parent_class', character.generated_class())
if not lib.does_asset_exist('/Game/Crusader/Characters/B_CRTraversalPawn'):
    hero = tools.create_asset('B_CRTraversalPawn', '/Game/Crusader/Characters', u.Blueprint, factory)
else:
    hero = u.load_asset('/Game/Crusader/Characters/B_CRTraversalPawn')
u.BlueprintEditorLibrary.compile_blueprint(hero)
save(hero)

ability_set = data_asset('AbilitySet_CRTraversal', u.LyraAbilitySet)
# LyraPlayerState already creates and registers health/combat sets.
ability_set.set_editor_property('granted_attributes', [])
save(ability_set)
input_config = data_asset('InputConfig_CRTraversal', u.LyraInputConfig)
save(input_config)
pawn_data = data_asset('PawnData_CRTraversal', u.LyraPawnData)
pawn_data.set_editor_property('pawn_class', hero.generated_class())
pawn_data.set_editor_property('ability_sets', [ability_set])
pawn_data.set_editor_property('input_config', input_config)
pawn_data.set_editor_property('default_camera_mode', u.CRTraversalCameraMode)
save(pawn_data)

experience = duplicate('/Game/System/Experiences/B_LyraDefaultExperience', '/Game/System/Experiences/B_CRTraversal')
experience_cdo = u.get_default_object(experience.generated_class())
experience_cdo.set_editor_property('default_pawn_data', pawn_data)
experience_cdo.set_editor_property('game_features_to_enable', [])
experience_cdo.set_editor_property('actions', [])
experience_cdo.set_editor_property('action_sets', [])
u.BlueprintEditorLibrary.compile_blueprint(experience)
save(experience)

level = duplicate('/Game/Levels/DefaultLevel', '/Game/Maps/L_TraversalGym')
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/L_TraversalGym')
world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
settings = world.get_world_settings()
settings.set_editor_property('default_game_mode', u.CRTraversalGameMode)
# CRTraversalGameMode selects the experience through Lyra's normal URL option.
actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
inventory = []
for actor in actors:
    if isinstance(actor, u.PlayerStart):
        actor.set_actor_location(u.Vector(2100, -1100, 94), False, True)
        actor.set_actor_rotation(u.Rotator(pitch=0, yaw=0, roll=0), True)
    loc = actor.get_actor_location()
    bounds = actor.get_actor_bounds(False)
    inventory.append({'name': actor.get_actor_label(), 'class': actor.get_class().get_path_name(), 'location': [loc.x, loc.y, loc.z], 'extent': [bounds[1].x, bounds[1].y, bounds[1].z]})
assert levels.save_current_level()
(out / 'actors.json').write_text(json.dumps(inventory, indent=2))
(out / 'result.json').write_text(json.dumps({'remapped_trace_nodes': remapped, 'pawn': hero.generated_class().get_path_name(), 'map': '/Game/Maps/L_TraversalGym', 'experience': experience.get_path_name(), 'lyra_mesh': lyra_mesh.get_path_name()}, indent=2))
u.log('CR_TRAVERSAL_GYM_AUTHORED')
