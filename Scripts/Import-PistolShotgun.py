"""Import the prepared weapons and replace the baseline pistol/shotgun models."""
import json
from pathlib import Path
import unreal as u

ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
OUT=ROOT/'Artifacts/WeaponReplacements'
assert not u.EditorLevelLibrary.get_pie_worlds(False)
lib=u.EditorAssetLibrary
tools=u.AssetToolsHelpers.get_asset_tools()

def save(asset):
    if isinstance(asset,u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(asset)
        assert not u.CRBlueprintTools.has_blueprint_errors(asset),asset.get_path_name()
    assert lib.save_loaded_asset(asset,only_if_is_dirty=False)

def duplicate(source,target):
    return u.load_asset(target) if lib.does_asset_exist(target) else lib.duplicate_asset(source,target)

def cdo(asset):return u.get_default_object(asset.generated_class())

u.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
for name,kind,title in [('FuturisticPistol','Pistol','Futuristic Pistol'),('TitanBreaker','Shotgun','Titan Breaker')]:
    source=ROOT/'Art/Weapons'/name
    folder='/Game/Crusader/Weapons/'+name
    textures={}
    for tex_kind in ['BaseColor','Normal','Metallic','Roughness']:
        asset_name=name+'_'+tex_kind
        task=u.AssetImportTask();task.filename=str(source/'Source'/(asset_name+'.png'))
        task.destination_path=folder+'/Textures';task.destination_name=asset_name
        task.automated=True;task.replace_existing=True;task.save=True
        tools.import_asset_tasks([task])
        tex=u.load_asset(folder+'/Textures/'+asset_name)
        assert tex,asset_name
        tex.set_editor_property('srgb',tex_kind=='BaseColor')
        if tex_kind=='Normal':
            tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_NORMALMAP)
            tex.set_editor_property('flip_green_channel',True)
        elif tex_kind!='BaseColor':tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_MASKS)
        save(tex);textures[tex_kind]=tex
    material_path=folder+'/M_'+name
    material=u.load_asset(material_path) if lib.does_asset_exist(material_path) else tools.create_asset('M_'+name,folder,u.Material,u.MaterialFactoryNew())
    u.MaterialEditingLibrary.delete_all_material_expressions(material)
    for i,(tex_kind,prop) in enumerate([('BaseColor',u.MaterialProperty.MP_BASE_COLOR),('Normal',u.MaterialProperty.MP_NORMAL),('Metallic',u.MaterialProperty.MP_METALLIC),('Roughness',u.MaterialProperty.MP_ROUGHNESS)]):
        expression=u.MaterialEditingLibrary.create_material_expression(material,u.MaterialExpressionTextureSample,-400,i*220)
        expression.texture=textures[tex_kind]
        if tex_kind=='Normal':expression.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_NORMAL
        elif tex_kind!='BaseColor':expression.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_MASKS
        assert u.MaterialEditingLibrary.connect_material_property(expression,'RGB' if tex_kind in ['BaseColor','Normal'] else 'R',prop)
    u.MaterialEditingLibrary.recompile_material(material);save(material)
    original_skeleton=u.load_asset('/Game/Weapons/'+kind+'/Mesh/SK_'+kind+'_Skeleton')
    skeleton=duplicate(original_skeleton.get_path_name(),folder+'/'+name+'_Skeleton')
    skeleton.add_compatible_skeleton(original_skeleton);save(skeleton)
    options=u.FbxImportUI()
    for key,value in [('import_mesh',True),('import_as_skeletal',True),('mesh_type_to_import',u.FBXImportType.FBXIT_SKELETAL_MESH),('original_import_type',u.FBXImportType.FBXIT_SKELETAL_MESH),('automated_import_should_detect_type',False),('import_animations',False),('import_materials',False),('import_textures',False),('create_physics_asset',False),('skeleton',skeleton)]:
        options.set_editor_property(key,value)
    options.skeletal_mesh_import_data.set_editor_property('import_uniform_scale',1.0)
    options.skeletal_mesh_import_data.set_editor_property('normal_import_method',u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    options.skeletal_mesh_import_data.set_editor_property('update_skeleton_reference_pose',False)
    task=u.AssetImportTask();task.filename=str(source/'Export'/(name+'.fbx'))
    task.destination_path=folder;task.destination_name=name
    task.automated=True;task.replace_existing=True;task.save=True;task.options=options
    tools.import_asset_tasks([task])
    mesh=u.load_asset(folder+'/'+name)
    assert isinstance(mesh,u.SkeletalMesh),str(task.imported_object_paths)
    mats=list(mesh.get_editor_property('materials'));mats[0].set_editor_property('material_interface',material)
    mesh.set_editor_property('materials',mats)
    assert u.get_editor_subsystem(u.SkeletalMeshEditorSubsystem).regenerate_lod(mesh,3,False,False)
    save(mesh)
    report=json.loads((OUT/(name+'-rig.json')).read_text())
    for socket in [s for s in u.ObjectIterator(u.SkeletalMeshSocket) if s.get_outer()==skeleton]:
        socket_name=str(socket.get_editor_property('socket_name'))
        if socket_name=='Muzzle' or socket_name.startswith('ShellEject'):
            key='muzzle_grip_cm' if socket_name=='Muzzle' else 'eject_grip_cm'
            assert u.CRBlueprintTools.set_property_text(socket,'BoneName','Grip')
            assert u.CRBlueprintTools.set_property_text(socket,'RelativeLocation',u.Vector(*report[key]).export_text())
            assert u.CRBlueprintTools.set_property_text(socket,'RelativeRotation',u.Rotator().export_text())
    save(skeleton)
    weapon=duplicate('/ShooterCore/Weapons/'+kind+'/B_'+kind,folder+'/B_'+name)
    sub=u.get_engine_subsystem(u.SubobjectDataSubsystem);data=u.SubobjectDataBlueprintFunctionLibrary
    changed=set()
    for handle in sub.k2_gather_subobject_data_for_blueprint(weapon):
        component=data.get_object_for_blueprint(data.get_data(handle),weapon)
        if isinstance(component,u.SkeletalMeshComponent) and component.get_path_name() not in changed:
            component.set_editor_property('skeletal_mesh_asset',mesh)
            component.set_editor_property('override_materials',[material])
            component.set_editor_property('physics_asset_override',None)
            changed.add(component.get_path_name())
    assert len(changed)==1,changed
    save(weapon)
    # Preserve each existing weapon's ID, abilities, statistics and HUD behavior. Updating
    # its actor definition replaces the model anywhere that weapon is equipped.
    equipment=u.load_asset('/Game/Baseline/Weapons/'+kind+'/WID_'+kind)
    spawn=list(cdo(equipment).get_editor_property('actors_to_spawn'))
    spawn[0].set_editor_property('actor_to_spawn',weapon.generated_class())
    cdo(equipment).set_editor_property('actors_to_spawn',spawn);save(equipment)
    item=u.load_asset('/Game/Baseline/Weapons/'+kind+'/ID_'+kind)
    cdo(item).set_editor_property('display_name',u.Text(title))
    reticles=[]
    for prefix in ['W_Reticle_','W_AmmoCounter_']:
        widget=duplicate('/ShooterCore/Weapons/'+kind+'/'+prefix+kind,folder+'/UI/'+prefix+name)
        save(widget);reticles.append(widget.generated_class())
    for fragment in cdo(item).get_editor_property('fragments'):
        if fragment.get_class().get_name()=='InventoryFragment_PickupIcon':
            fragment.set_editor_property('SkeletalMesh',mesh)
            fragment.set_editor_property('DisplayName',u.Text(title))
        if fragment.get_class().get_name()=='InventoryFragment_QuickBarIcon':
            fragment.set_editor_property('DisplayNameWhenEquipped',u.Text(title))
        if fragment.get_class().get_name()=='InventoryFragment_ReticleConfig':
            fragment.set_editor_property('ReticleWidgets',reticles)
    save(item)
    for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        if isinstance(actor,u.BaselineWeaponPickup) and actor.item_definition==item.generated_class():
            actor.set_actor_label(title+' Pickup')
            actor.display_mesh.set_skeletal_mesh_asset(mesh)
            actor.display_mesh.set_material(0,material)
    print('REPLACED',kind,'with',name)
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
print('PISTOL_SHOTGUN_IMPORT_COMPLETE')
