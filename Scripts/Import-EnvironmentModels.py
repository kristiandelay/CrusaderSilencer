"""Import normalized environment props, PBR materials, Nanite and exact collision."""
import json
from pathlib import Path
import unreal as u

ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
records=json.loads((ROOT/'resources/EnvironmentModels.json').read_text())
lib=u.EditorAssetLibrary;tools=u.AssetToolsHelpers.get_asset_tools()
editor=u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
assert not u.EditorLevelLibrary.get_pie_worlds(False)
u.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
results=[]
for entry in records:
    name=entry['name'];source=ROOT/'Art/Environment'/entry['category']/name
    dest='/Game/Crusader/Environment/'+entry['category']+'/'+name
    textures={}
    tasks=[]
    for kind in ['BaseColor','Normal','Metallic','Roughness']:
        task=u.AssetImportTask();task.filename=str(source/'Source'/(name+'_'+kind+'.png'));task.destination_path=dest+'/Textures';task.destination_name=name+'_'+kind
        task.automated=True;task.replace_existing=True;task.save=True;tasks.append(task)
    tools.import_asset_tasks(tasks)
    for kind in ['BaseColor','Normal','Metallic','Roughness']:
        tex=u.load_asset(dest+'/Textures/'+name+'_'+kind);assert tex
        tex.set_editor_property('srgb',kind=='BaseColor')
        if kind=='Normal':
            tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_NORMALMAP);tex.set_editor_property('flip_green_channel',True)
        elif kind!='BaseColor':tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_MASKS)
        lib.save_loaded_asset(tex);textures[kind]=tex
    mat=u.load_asset(dest+'/M_'+name) if lib.does_asset_exist(dest+'/M_'+name) else tools.create_asset('M_'+name,dest,u.Material,u.MaterialFactoryNew())
    u.MaterialEditingLibrary.delete_all_material_expressions(mat)
    for i,(kind,prop) in enumerate([('BaseColor',u.MaterialProperty.MP_BASE_COLOR),('Normal',u.MaterialProperty.MP_NORMAL),('Metallic',u.MaterialProperty.MP_METALLIC),('Roughness',u.MaterialProperty.MP_ROUGHNESS)]):
        expr=u.MaterialEditingLibrary.create_material_expression(mat,u.MaterialExpressionTextureSample,-400,i*210);expr.texture=textures[kind]
        expr.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_COLOR if kind=='BaseColor' else u.MaterialSamplerType.SAMPLERTYPE_NORMAL if kind=='Normal' else u.MaterialSamplerType.SAMPLERTYPE_MASKS
        assert u.MaterialEditingLibrary.connect_material_property(expr,'RGB' if kind in ['BaseColor','Normal'] else 'R',prop)
    physical=u.load_asset('/Game/Crusader/Effects/Surfaces/PM_'+entry['surface']);assert physical
    mat.set_editor_property('phys_material',physical)
    u.MaterialEditingLibrary.recompile_material(mat);lib.save_loaded_asset(mat)
    options=u.FbxImportUI();options.import_mesh=True;options.import_as_skeletal=False;options.import_materials=False;options.import_textures=False
    options.mesh_type_to_import=u.FBXImportType.FBXIT_STATIC_MESH;options.automated_import_should_detect_type=False
    options.static_mesh_import_data.combine_meshes=True;options.static_mesh_import_data.auto_generate_collision=False
    options.static_mesh_import_data.normal_import_method=u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    task=u.AssetImportTask();task.filename=str(source/'Export'/(name+'.fbx'));task.destination_path=dest;task.destination_name=name
    task.options=options;task.automated=True;task.replace_existing=True;task.save=True
    tools.import_asset_tasks([task])
    mesh=u.load_asset(dest+'/'+name);assert isinstance(mesh,u.StaticMesh),task.imported_object_paths
    mesh.set_material(0,mat)
    body=mesh.get_editor_property('body_setup')
    body.set_editor_property('collision_trace_flag',u.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    body.set_editor_property('phys_material',physical)
    settings=editor.get_nanite_settings(mesh);settings.set_editor_property('enabled',True);editor.set_nanite_settings(mesh,settings,True)
    lib.save_loaded_asset(mesh,only_if_is_dirty=False)
    entry['imported']=True;entry['asset']=mesh.get_path_name()
    results.append(dict(name=name,asset=mesh.get_path_name(),nanite=True,collision='ComplexAsSimple',surface=entry['surface'],bounds=str(mesh.get_bounds())))
    (ROOT/'Artifacts/Environment/import.json').write_text(json.dumps(results,indent=2))
    print('IMPORTED_ENVIRONMENT',name)
(ROOT/'resources/EnvironmentModels.json').write_text(json.dumps(records,indent=2))
existing=json.loads((ROOT/'mockups/AssetSources.json').read_text());names={r['name'] for r in records}
(ROOT/'mockups/AssetSources.json').write_text(json.dumps([r for r in existing if r['name'] not in names]+records,indent=2))
print('ENVIRONMENT_IMPORT_COMPLETE',len(results))
