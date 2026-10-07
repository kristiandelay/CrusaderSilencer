"""Add Crimson Sentinel to the visual catalog and Black Iron Rifle to the gym."""
import json
from pathlib import Path
import unreal as u

assert not u.EditorLevelLibrary.get_pie_worlds(False)
lib=u.EditorAssetLibrary
tools=u.AssetToolsHelpers.get_asset_tools()
sub=u.get_engine_subsystem(u.SubobjectDataSubsystem)
data=u.SubobjectDataBlueprintFunctionLibrary
character_folder='/Game/Crusader/Characters/CrimsonSentinel'
weapon_folder='/Game/Crusader/Weapons/BlackIronRifle'

def save(asset):
    if isinstance(asset,u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(asset)
        assert not u.CRBlueprintTools.has_blueprint_errors(asset),asset.get_path_name()
    assert lib.save_loaded_asset(asset,only_if_is_dirty=False)

def duplicate(source,target):
    return u.load_asset(target) if lib.does_asset_exist(target) else lib.duplicate_asset(source,target)

def cdo(asset):return u.get_default_object(asset.generated_class())

mesh=u.load_asset(character_folder+'/CrimsonSentinel')
rig_path=character_folder+'/IK_CrimsonSentinel'
rig=u.load_asset(rig_path) if lib.does_asset_exist(rig_path) else tools.create_asset('IK_CrimsonSentinel',character_folder,u.IKRigDefinition,u.IKRigDefinitionFactory())
controller=u.IKRigController.get_controller(rig)
assert controller.set_skeletal_mesh(mesh)
assert controller.apply_auto_generated_retarget_definition(),'UE humanoid chain recognition failed'
assert controller.apply_auto_fbik(),'UE humanoid full-body IK generation failed'
save(rig)
print('IK_RIG_CHAINS',len(controller.get_retarget_chains()))
retarget=duplicate('/Game/Baseline/Animations/VisualOverrides/RTG_Manny_to_UE5_Mannequin',character_folder+'/RTG_Manny_to_CrimsonSentinel')
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
mapping['RTG_Manny_to_CrimsonSentinel']=retarget
cdo(animation).set_editor_property('IKRetargeter_Map',mapping)
save(animation)
visual=duplicate('/Game/Blueprints/RetargetedCharacters/BP_Manny',character_folder+'/BP_CrimsonSentinel')
seen=set()
for handle in sub.k2_gather_subobject_data_for_blueprint(visual):
    component=data.get_object_for_blueprint(data.get_data(handle),visual)
    if isinstance(component,u.SkeletalMeshComponent) and component.get_path_name() not in seen:
        component.set_editor_property('skeletal_mesh_asset',mesh)
        component.set_editor_property('anim_class',animation.generated_class())
        component.set_editor_property('component_tags',['RTG_Manny_to_CrimsonSentinel'])
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

rifle_mesh=u.load_asset(weapon_folder+'/BlackIronRifle')
skeleton=rifle_mesh.get_editor_property('skeleton')
skeleton.add_compatible_skeleton(u.load_asset('/Game/Weapons/Rifle/Mesh/SK_Rifle_Skeleton'))
# Socket positions are local to Grip, whose X axis follows the barrel.
report=json.loads((Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/CrimsonSentinel/rifle-report.json').read_text())
for socket in [s for s in u.ObjectIterator(u.SkeletalMeshSocket) if s.get_outer()==skeleton]:
    if str(socket.get_editor_property('socket_name'))=='Muzzle':
        assert u.CRBlueprintTools.set_property_text(socket,'BoneName','Grip')
        assert u.CRBlueprintTools.set_property_text(socket,'RelativeLocation',u.Vector(report['muzzle_ue_cm'][1],0,report['muzzle_ue_cm'][2]).export_text())
        assert u.CRBlueprintTools.set_property_text(socket,'RelativeRotation',u.Rotator().export_text())
save(skeleton)
weapon=duplicate('/ShooterCore/Weapons/Rifle/B_Rifle',weapon_folder+'/B_BlackIronRifle')
count=0
for handle in sub.k2_gather_subobject_data_for_blueprint(weapon):
    component=data.get_object_for_blueprint(data.get_data(handle),weapon)
    if isinstance(component,u.SkeletalMeshComponent):
        component.set_editor_property('skeletal_mesh_asset',rifle_mesh)
        component.set_editor_property('override_materials',[u.load_asset(weapon_folder+'/M_BlackIronRifle')])
        count+=1
assert count==1,count
save(weapon)
equipment=duplicate('/Game/Baseline/Weapons/Rifle/WID_Rifle',weapon_folder+'/WID_BlackIronRifle')
spawn=list(cdo(equipment).get_editor_property('actors_to_spawn'))
spawn[0].set_editor_property('actor_to_spawn',weapon.generated_class())
cdo(equipment).set_editor_property('actors_to_spawn',spawn)
save(equipment)
item=duplicate('/Game/Baseline/Weapons/Rifle/ID_Rifle',weapon_folder+'/ID_BlackIronRifle')
cdo(item).set_editor_property('display_name',u.Text('Black Iron Rifle'))
reticles=[]
for old,new in [('W_Reticle_Rifle','W_Reticle_BlackIronRifle'),('W_AmmoCounter_Rifle','W_AmmoCounter_BlackIronRifle')]:
    widget=duplicate('/ShooterCore/Weapons/Rifle/'+old,weapon_folder+'/UI/'+new)
    save(widget);reticles.append(widget.generated_class())
for fragment in cdo(item).get_editor_property('fragments'):
    if fragment.get_class().get_name()=='InventoryFragment_EquippableItem':fragment.set_editor_property('EquipmentDefinition',equipment.generated_class())
    if fragment.get_class().get_name()=='InventoryFragment_PickupIcon':fragment.set_editor_property('SkeletalMesh',rifle_mesh)
    if fragment.get_class().get_name()=='InventoryFragment_PickupIcon':fragment.set_editor_property('DisplayName',u.Text('Black Iron Rifle'))
    if fragment.get_class().get_name()=='InventoryFragment_QuickBarIcon':fragment.set_editor_property('DisplayNameWhenEquipped',u.Text('Black Iron Rifle'))
    if fragment.get_class().get_name()=='InventoryFragment_ReticleConfig':fragment.set_editor_property('ReticleWidgets',reticles)
save(item)
level=u.get_editor_subsystem(u.LevelEditorSubsystem)
if u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world().get_name()!='L_TraversalGym':
    assert level.load_level('/Game/Maps/L_TraversalGym')
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
for actor in actors.get_all_level_actors():
    if isinstance(actor,u.BaselineWeaponPickup) and actor.item_definition:
        if actor.item_definition.get_name() in ['ID_Rifle_C','ID_BlackIronRifle_C']:
            actor.set_editor_property('item_definition',item.generated_class())
            actor.set_actor_label('Black Iron Rifle Pickup')
            actor.display_mesh.set_skeletal_mesh_asset(rifle_mesh)
assert level.save_current_level()
print('CRIMSON_INTEGRATION_COMPLETE')
