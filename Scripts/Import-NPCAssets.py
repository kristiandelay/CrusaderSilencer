"""Import the prepared Blender exports and consistently named PBR textures."""
import unreal as u
import json
from pathlib import Path

ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
lib=u.EditorAssetLibrary
tools=u.AssetToolsHelpers.get_asset_tools()
assert not u.EditorLevelLibrary.get_pie_worlds(False)

def save(asset):
    assert lib.save_loaded_asset(asset,only_if_is_dirty=False)

def duplicate(source,target):
    return u.load_asset(target) if lib.does_asset_exist(target) else lib.duplicate_asset(source,target)

u.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
for category,name in [('Characters',n) for n in globals().get('NPC_IMPORT_NAMES',list(json.loads((ROOT/'resources/NPCCharacterRigs.json').read_text())))]:
    source=ROOT/'Art'/category/name
    destination='/Game/Crusader/'+category+'/'+name
    textures={}
    for kind in ['BaseColor','Normal','Metallic','Roughness']:
        asset_name=name+'_'+kind
        task=u.AssetImportTask();task.filename=str(source/'Source'/(asset_name+'.png'));task.destination_path=destination+'/Textures';task.destination_name=asset_name;task.automated=True;task.replace_existing=True;task.save=True
        tools.import_asset_tasks([task])
        tex=u.load_asset(destination+'/Textures/'+asset_name)
        assert tex,asset_name
        tex.set_editor_property('srgb',kind=='BaseColor')
        if kind=='Normal':
            tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_NORMALMAP)
            tex.set_editor_property('flip_green_channel',True)
        elif kind!='BaseColor':
            tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_MASKS)
        save(tex);textures[kind]=tex
    material_path=destination+'/M_'+name
    material=u.load_asset(material_path) if lib.does_asset_exist(material_path) else tools.create_asset('M_'+name,destination,u.Material,u.MaterialFactoryNew())
    u.MaterialEditingLibrary.delete_all_material_expressions(material)
    for i,(kind,prop) in enumerate([('BaseColor',u.MaterialProperty.MP_BASE_COLOR),('Normal',u.MaterialProperty.MP_NORMAL),('Metallic',u.MaterialProperty.MP_METALLIC),('Roughness',u.MaterialProperty.MP_ROUGHNESS)]):
        expression=u.MaterialEditingLibrary.create_material_expression(material,u.MaterialExpressionTextureSample,-400,i*220)
        expression.texture=textures[kind]
        if kind=='Normal':expression.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_NORMAL
        elif kind!='BaseColor':expression.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_MASKS
        assert u.MaterialEditingLibrary.connect_material_property(expression,'RGB' if kind in ['BaseColor','Normal'] else 'R',prop)
    u.MaterialEditingLibrary.recompile_material(material);save(material)
    options=u.FbxImportUI();options.set_editor_property('import_mesh',True);options.set_editor_property('import_as_skeletal',True);options.set_editor_property('mesh_type_to_import',u.FBXImportType.FBXIT_SKELETAL_MESH);options.set_editor_property('original_import_type',u.FBXImportType.FBXIT_SKELETAL_MESH);options.set_editor_property('automated_import_should_detect_type',False)
    options.set_editor_property('import_animations',False);options.set_editor_property('import_materials',False);options.set_editor_property('import_textures',False);options.set_editor_property('create_physics_asset',False)
    options.skeletal_mesh_import_data.set_editor_property('import_uniform_scale',1.0)
    options.skeletal_mesh_import_data.set_editor_property('normal_import_method',u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    options.skeletal_mesh_import_data.set_editor_property('update_skeleton_reference_pose',False)
    if lib.does_asset_exist(destination+'/'+name+'_Skeleton'):
        options.set_editor_property('skeleton',u.load_asset(destination+'/'+name+'_Skeleton'))
        options.skeletal_mesh_import_data.set_editor_property('update_skeleton_reference_pose',True)
    task=u.AssetImportTask();task.filename=str(source/'Export'/(name+'.fbx'));task.destination_path=destination;task.destination_name=name;task.automated=True;task.replace_existing=True;task.save=True;task.options=options
    tools.import_asset_tasks([task])
    mesh=u.load_asset(destination+'/'+name)
    assert isinstance(mesh,u.SkeletalMesh),str(task.imported_object_paths)
    mats=list(mesh.get_editor_property('materials'));mats[0].set_editor_property('material_interface',material);mesh.set_editor_property('materials',mats)
    editor=u.get_editor_subsystem(u.SkeletalMeshEditorSubsystem)
    assert editor.regenerate_lod(mesh,3,False,False),'Could not generate distance LODs'
    save(mesh)
    save(mesh.get_editor_property('skeleton'))
    print('IMPORTED',mesh.get_path_name(),mesh.get_editor_property('skeleton').get_path_name())
print('NPC_ASSET_IMPORT_COMPLETE')
