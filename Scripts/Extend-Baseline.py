"""Author reusable slide, weapon presentation, inventory and gym fixtures after the Lyra/GASP merge."""
from pathlib import Path
import json
import unreal as u

root = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
out = root / 'Artifacts/BaselineAuthoring'
out.mkdir(parents=True, exist_ok=True)
lib = u.EditorAssetLibrary
asset_tools = u.AssetToolsHelpers.get_asset_tools()

def save(asset):
    if isinstance(asset, u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(asset)
        assert not u.CRBlueprintTools.has_blueprint_errors(asset), asset.get_path_name()
    assert lib.save_loaded_asset(asset, only_if_is_dirty=False), asset.get_path_name()

def duplicate(source, target):
    return u.load_asset(target) if lib.does_asset_exist(target) else lib.duplicate_asset(source, target)

def asset(name, cls, factory, folder='/Game/Baseline/Input'):
    return u.load_asset(folder+'/'+name) if lib.does_asset_exist(folder+'/'+name) else asset_tools.create_asset(name,folder,cls,factory)

def cdo(bp):
    return u.get_default_object(bp.generated_class())

def key(name):
    value=u.Key()
    assert value.import_text(name)
    return value

def components(bp):
    subsystem=u.get_engine_subsystem(u.SubobjectDataSubsystem)
    data=u.SubobjectDataBlueprintFunctionLibrary
    return [data.get_object(data.get_data(handle)) for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp)]

def make_carry_animation(kind, hold):
    """Bake a looping arm carry; the runtime mask leaves GASP's torso/head free."""
    carry=duplicate(hold.get_path_name().split('.')[0],'/Game/Baseline/Animations/A_'+kind+'_Carry')
    carry.set_editor_property('enable_root_motion',False)
    options=u.AnimPoseEvaluationOptions()
    options.set_editor_property('retrieve_additive_as_full_pose',True)
    reference=u.AnimPoseExtensions.get_anim_pose_at_time(hold,0,options)
    offset_name='Pistol_Idle_ADS' if kind=='Pistol' else 'Rifle_Idle_Hipfire'
    lowered=u.load_asset('/Game/Characters/Heroes/Mannequin/Animations/AimOffsets/MM_'+offset_name+'_AO_CD')
    lowered_pose=u.AnimPoseExtensions.get_anim_pose_at_time(lowered,0,options)
    arm_bones=[]
    for bone in u.AnimationLibrary.get_animation_track_names(hold):
        chain={str(b) for b in u.AnimationLibrary.find_bone_path_to_root(hold,bone)}
        if str(bone) in ['clavicle_l','clavicle_r'] or chain.intersection({'clavicle_l','clavicle_r'}):
            arm_bones.append(bone)
    assert arm_bones,kind
    # Remove the downward pose's spine/head rotation entirely: only its local
    # arm articulation is retained. Preserve the source loop's breathing motion.
    offsets={}
    for bone in arm_bones:
        base=u.AnimPoseExtensions.get_bone_pose(reference,bone).rotation
        target=u.AnimPoseExtensions.get_bone_pose(lowered_pose,bone).rotation
        offsets[bone]=target.multiply(base.inversed())
    keys={bone:([],[],[]) for bone in arm_bones}
    for frame in range(u.AnimationLibrary.get_num_frames(hold)+1):
        pose=u.AnimPoseExtensions.get_anim_pose_at_time(hold,u.AnimationLibrary.get_time_at_frame(hold,frame),options)
        for bone in arm_bones:
            local=u.AnimPoseExtensions.get_bone_pose(pose,bone)
            positions,rotations,scales=keys[bone]
            positions.append(local.translation)
            rotations.append(offsets[bone].multiply(local.rotation))
            scales.append(local.scale3d)
    controller=carry.controller
    controller.open_bracket('Author relaxed weapon carry',False)
    try:
        for bone,(positions,rotations,scales) in keys.items():
            assert controller.set_bone_track_keys(bone,positions,rotations,scales,False),str(bone)
    finally:controller.close_bracket(False)
    save(carry)
    return carry

character=u.load_asset('/Game/Blueprints/SandboxCharacter_CMC')
source_anim=u.load_asset('/Game/Blueprints/SandboxCharacter_CMC_ABP')
aim_action=u.load_asset('/Game/Input/IA_Aim')
# Native input tracks hold/release; the replicated combat stance drives GASP's
# existing turn-in-place and aiming locomotion on every machine.
aim_action.set_editor_property('triggers',[])
save(aim_action)
assert u.CRBlueprintTools.configure_weapon_stance(character,u.CRTraversalCharacter.static_class(),aim_action,source_anim)
save(source_anim)
ability_set=u.load_asset('/Game/Crusader/System/AbilitySet_CRTraversal')
ability_set.set_editor_property('granted_attributes',[])
save(ability_set)
u.CRBlueprintTools.remove_input_action_binding(character,u.load_asset('/Game/Input/IA_Crouch'))
slide=duplicate('/Game/Characters/UEFN_Mannequin/Animations/Slide/M_Neutral_Slide_FootOut_Loop',
                '/Game/Baseline/Animations/A_SlideLoop')
slide.set_editor_property('enable_root_motion',False)
save(slide)
cdo(character).set_editor_property('slide_animation',slide)
save(character)
save(u.load_asset('/Game/Crusader/Characters/B_CRTraversalPawn'))

# One mapping context owns GASP movement and baseline equipment inputs.
mapping=duplicate('/Game/Input/IMC_Sandbox','/Game/Baseline/Input/IMC_Baseline')
mapping.unmap_all_keys_from_action(u.load_asset('/Game/Input/IA_Interact'))
# Preserve the selected mouse pitch direction when authoring future baselines.
for entry in mapping.get_editor_property('default_key_mappings').get_editor_property('mappings'):
    if entry.get_editor_property('key').export_text()=='Mouse2D':
        for modifier in entry.get_editor_property('modifiers'):
            if isinstance(modifier,u.InputModifierScalar):
                scalar=modifier.get_editor_property('scalar')
                modifier.set_editor_property('scalar',u.Vector(scalar.x,abs(scalar.y),scalar.z))
actions={}
for name, keyboard, gamepad in [('Interact','E','Gamepad_FaceButton_Left'),('Drop','G','Gamepad_Special_Left'),('Cycle','Tab','Gamepad_DPad_Up')]:
    action=asset('IA_'+name,u.InputAction,u.InputAction_Factory())
    action.set_editor_property('value_type',u.InputActionValueType.BOOLEAN)
    action.set_editor_property('triggers',[])
    save(action)
    mapping.unmap_all_keys_from_action(action)
    mapping.map_key(action,key(keyboard))
    mapping.map_key(action,key(gamepad))
    actions[name]=action
input_config=u.load_asset('/Game/Crusader/System/InputConfig_CRTraversal')
ability_inputs=[]
for action_name,tag,keyboard,gamepad in [
    ('IA_Weapon_Fire','InputTag.Weapon.Fire','LeftMouseButton','Gamepad_RightTrigger'),
    ('IA_Weapon_Fire_Auto','InputTag.Weapon.FireAuto','LeftMouseButton','Gamepad_RightTrigger'),
    ('IA_Weapon_Reload','InputTag.Weapon.Reload','R','Gamepad_DPad_Down')]:
    action=u.load_asset('/Game/Input/Actions/'+action_name)
    mapping.unmap_all_keys_from_action(action)
    mapping.map_key(action,key(keyboard))
    mapping.map_key(action,key(gamepad))
    entry=u.LyraInputAction()
    assert entry.import_text('(InputAction="'+action.get_path_name()+'",InputTag=(TagName="'+tag+'"))')
    ability_inputs.append(entry)
input_config.set_editor_property('ability_input_actions',ability_inputs)
save(input_config)
save(mapping)

# Manny retains the complete GASP lower body, with Lyra weapon poses/montages above the spine.
visual_anim=duplicate('/Game/Blueprints/RetargetedCharacters/ABP_GenericRetarget','/Game/Baseline/Animations/ABP_BaselineManny')
u.BlueprintEditorLibrary.reparent_blueprint(visual_anim,u.BaselineAnimInstance)
fallback=u.load_asset('/Game/Characters/Heroes/Mannequin/Animations/Locomotion/Rifle/MM_Rifle_Idle_Hipfire')
fallback_aim=u.load_asset('/Game/Characters/Heroes/Mannequin/Animations/AimOffsets/AO_MM_Rifle_Idle_Hipfire')
carry_animations={}
for kind in ['Rifle','Pistol','Shotgun']:
    hold=u.load_asset('/Game/Characters/Heroes/Mannequin/Animations/Locomotion/'+kind+'/MM_'+kind+'_Idle_'+('ADS' if kind=='Pistol' else 'Hipfire'))
    carry_animations[kind]=make_carry_animation(kind,hold)
cdo(visual_anim).set_editor_property('weapon_pose',fallback)
cdo(visual_anim).set_editor_property('weapon_carry_pose',carry_animations['Rifle'])
cdo(visual_anim).set_editor_property('weapon_aim_offset',fallback_aim)
assert u.CRBlueprintTools.build_weapon_overlay(visual_anim,fallback,fallback_aim), u.CRBlueprintTools.describe_blueprint(visual_anim)
save(visual_anim)
visual=u.load_asset('/Game/Crusader/Characters/B_CRMannequin')
for component in components(visual):
    if isinstance(component,u.SkeletalMeshComponent):
        component.set_anim_instance_class(visual_anim.generated_class())
save(visual)

weapon_items={}
# Lyra notifies must resolve the parent gameplay pawn from the visible ChildActor.
for path in ['/Game/Characters/Heroes/Mannequin/Animations/AnimNotifies/AN_PlayWeaponMontage',
             '/Game/Characters/Heroes/Abilities/AN_Reload']:
    notify=u.load_asset(path)
    u.CRBlueprintTools.route_notify_gameplay_owner(notify,u.BaselineAnimationLibrary.static_class())
    save(notify)

for kind in ['Rifle','Pistol','Shotgun']:
    folder='/Game/Baseline/Weapons/'+kind
    source='/ShooterCore/Weapons/'+kind
    instance=duplicate(source+'/B_WeaponInstance_'+kind,folder+'/B_WeaponInstance_'+kind)
    u.BlueprintEditorLibrary.reparent_blueprint(instance,u.BaselineWeaponInstance)
    pose=u.load_asset('/Game/Characters/Heroes/Mannequin/Animations/Locomotion/'+kind+'/MM_'+kind+'_Idle_'+('ADS' if kind=='Pistol' else 'Hipfire'))
    assert pose, kind
    cdo(instance).set_editor_property('hold_animation',pose)
    cdo(instance).set_editor_property('carry_animation',carry_animations[kind])
    aim=u.load_asset('/Game/Characters/Heroes/Mannequin/Animations/AimOffsets/AO_MM_'+('Pistol_Idle_ADS' if kind=='Pistol' else 'Rifle_Idle_Hipfire'))
    assert aim,kind
    cdo(instance).set_editor_property('aim_offset',aim)
    save(instance)
    ability_set=duplicate(source+'/AbilitySet_Shooter'+kind,folder+'/AbilitySet_'+kind)
    grants=[]
    for original in ability_set.get_editor_property('granted_gameplay_abilities'):
        ability_class=original.get_editor_property('ability')
        ability_path=ability_class.get_path_name().split('.')[0]
        ability=duplicate(ability_path,folder+'/'+ability_path.rsplit('/',1)[1])
        blocked=cdo(ability).get_editor_property('activation_blocked_tags')
        text=blocked.export_text()
        # Preserve stock restrictions while adding the traversal gate. Slides can fire.
        if 'Baseline.State.HandsBusy' not in text:
            text='(GameplayTags=((TagName="Baseline.State.HandsBusy")))' if text=='(GameplayTags=)' else text.replace('GameplayTags=(', 'GameplayTags=((TagName="Baseline.State.HandsBusy"),',1)
            assert blocked.import_text(text)
        cdo(ability).set_editor_property('activation_blocked_tags',blocked)
        save(ability)
        entry=u.LyraAbilitySet_GameplayAbility()
        assert entry.import_text(original.export_text().replace(ability_class.get_path_name(),ability.generated_class().get_path_name()))
        grants.append(entry)
    ability_set.set_editor_property('granted_gameplay_abilities',grants)
    save(ability_set)
    equipment=duplicate(source+'/WID_'+kind,folder+'/WID_'+kind)
    cdo(equipment).set_editor_property('instance_type',instance.generated_class())
    cdo(equipment).set_editor_property('ability_sets_to_grant',[ability_set])
    save(equipment)
    item=duplicate(source+'/ID_'+kind,folder+'/ID_'+kind)
    for fragment in cdo(item).get_editor_property('fragments'):
        if fragment.get_class().get_name()=='InventoryFragment_EquippableItem':
            fragment.set_editor_property('EquipmentDefinition',equipment.generated_class())
    save(item)
    weapon_items[kind]=item.generated_class()

experience=u.load_asset('/Game/System/Experiences/B_CRTraversal')
# ShooterCore content is mounted by Lyra's plugin policy. Its full activation adds
# another equipment manager and shooter input mappings, so this experience uses
# the weapon assets directly and discovers cues through feature registration.
cdo(experience).set_editor_property('game_features_to_enable',[])
save(experience)

level=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert level.load_level('/Game/Maps/L_TraversalGym')
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
existing={actor.get_actor_label():actor for actor in actors.get_all_level_actors()}

def fixture(cls,label,location,rotation=u.Rotator()):
    actor=existing.get(label)
    if actor is None:
        actor=actors.spawn_actor_from_class(cls,u.Vector(*location),rotation)
    actor.set_actor_label(label)
    actor.set_actor_location(u.Vector(*location),False,True)
    actor.set_actor_rotation(rotation,False)
    return actor

for kind,y in [('Rifle',-1100),('Pistol',-900),('Shotgun',-1300)]:
    pickup=fixture(u.BaselineWeaponPickup,'Baseline_Pickup_'+kind,[2250,y,55])
    pickup.set_editor_property('item_definition',weapon_items[kind])
    # Editing a native property from Python doesn't automatically rerun construction.
    icon=next(f for f in u.get_default_object(weapon_items[kind]).get_editor_property('fragments') if isinstance(f,u.InventoryFragment_PickupIcon))
    pickup.display_mesh.set_skinned_asset_and_update(icon.get_editor_property('skeletal_mesh'))

cube=u.load_asset('/Engine/BasicShapes/Cube')
for label,location,scale,pitch in [
    ('Baseline_SlideRamp',[-700,-4600,270],[18,5,.4],-15),
    ('Baseline_SlideTop',[-1775,-4600,500],[4,5,.4],0),
    ('Baseline_SlideRunout',[700,-4600,5],[10,5,.1],0),
]:
    actor=fixture(u.StaticMeshActor,label,location,u.Rotator(pitch=pitch,yaw=0,roll=0))
    actor.static_mesh_component.set_static_mesh(cube)
    actor.set_actor_scale3d(u.Vector(*scale))

label=fixture(u.TextRenderActor,'Baseline_SlideSign',[-1850,-4350,550],u.Rotator(pitch=0,yaw=90,roll=0))
label.text_render.set_text('MOMENTUM SLIDE\nSprint + C\nDownhill gains speed')
label.text_render.set_world_size(30)
assert level.save_current_level()
(out/'result.json').write_text(json.dumps({'map':'/Game/Maps/L_TraversalGym','weapons':{k:v.get_path_name() for k,v in weapon_items.items()},'slide_animation':slide.get_path_name(),'visual_animation':visual_anim.get_path_name()},indent=2))
u.log('BASELINE_AUTHORING_COMPLETE')
