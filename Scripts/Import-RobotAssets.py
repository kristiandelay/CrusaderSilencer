"""Import custom mechanical skeletons, rigid modules and joint-check previews."""
import json
from pathlib import Path
import unreal as u

ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
profiles=json.loads((ROOT/'resources/RobotRigs.json').read_text())
names=globals().get('ROBOT_IMPORT_NAMES',list(profiles))
assert not u.EditorLevelLibrary.get_pie_worlds(False)
lib=u.EditorAssetLibrary;tools=u.AssetToolsHelpers.get_asset_tools()
u.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
reports=[]

def save(obj):assert lib.save_loaded_asset(obj,only_if_is_dirty=False),obj.get_path_name()
def create(name,folder,cls,factory):
    return u.load_asset(folder+'/'+name) if lib.does_asset_exist(folder+'/'+name) else tools.create_asset(name,folder,cls,factory)
def task(filename,destination,name,options=None):
    t=u.AssetImportTask();t.filename=str(filename);t.destination_path=destination;t.destination_name=name;t.automated=True;t.replace_existing=True;t.save=True
    if options:t.options=options
    tools.import_asset_tasks([t]);assert t.imported_object_paths,filename
    return [u.load_asset(p) for p in t.imported_object_paths]

for name in names:
    source=ROOT/'Art/Robots'/name;destination='/Game/Crusader/Robots/'+name
    validation_path=ROOT/'Artifacts/Robots'/name/'validation.json'
    validation=json.loads(validation_path.read_text());assert validation['passed'],name
    assert validation_path.stat().st_mtime>=(source/'RigManifest.json').stat().st_mtime,(name,'Revalidate the latest rig before import')
    manifest=json.loads((source/'RigManifest.json').read_text())
    textures={}
    for kind in ['BaseColor','Normal','Metallic','Roughness']:
        asset_name=name+'_'+kind
        task(source/'Source'/(asset_name+'.png'),destination+'/Textures',asset_name)
        tex=u.load_asset(destination+'/Textures/'+asset_name);tex.set_editor_property('srgb',kind=='BaseColor')
        if kind=='Normal':tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_NORMALMAP);tex.set_editor_property('flip_green_channel',True)
        elif kind!='BaseColor':tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_MASKS)
        save(tex);textures[kind]=tex
    materials={}
    for suffix,color,roughness in [('',None,0),('_JointMetal',(.075,.085,.095),.33),('_PistonMetal',(.32,.36,.40),.22)]:
        mat_name='M_'+name+suffix;mat=create(mat_name,destination,u.Material,u.MaterialFactoryNew());u.MaterialEditingLibrary.delete_all_material_expressions(mat)
        if color:
            expr=u.MaterialEditingLibrary.create_material_expression(mat,u.MaterialExpressionConstant3Vector,-300,0);expr.constant=u.LinearColor(*color,1)
            u.MaterialEditingLibrary.connect_material_property(expr,'',u.MaterialProperty.MP_BASE_COLOR)
            for i,(value,prop) in enumerate([(.85,u.MaterialProperty.MP_METALLIC),(roughness,u.MaterialProperty.MP_ROUGHNESS)]):
                expr=u.MaterialEditingLibrary.create_material_expression(mat,u.MaterialExpressionConstant,-300,200+i*100);expr.r=value;u.MaterialEditingLibrary.connect_material_property(expr,'',prop)
        else:
            for i,(kind,prop) in enumerate([('BaseColor',u.MaterialProperty.MP_BASE_COLOR),('Normal',u.MaterialProperty.MP_NORMAL),('Metallic',u.MaterialProperty.MP_METALLIC),('Roughness',u.MaterialProperty.MP_ROUGHNESS)]):
                expr=u.MaterialEditingLibrary.create_material_expression(mat,u.MaterialExpressionTextureSample,-400,i*220);expr.texture=textures[kind]
                if kind=='Normal':expr.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_NORMAL
                elif kind!='BaseColor':expr.sampler_type=u.MaterialSamplerType.SAMPLERTYPE_MASKS
                assert u.MaterialEditingLibrary.connect_material_property(expr,'RGB' if kind in ['BaseColor','Normal'] else 'R',prop)
        mat.set_editor_property('phys_material',u.load_asset('/Game/Crusader/Effects/Surfaces/PM_Metal'))
        u.MaterialEditingLibrary.recompile_material(mat);save(mat);materials[suffix]=mat
    def material_for(slot):
        label=str(slot)
        return materials['_PistonMetal' if 'PistonMetal' in label else '_JointMetal' if 'JointMetal' in label else '']
    options=u.FbxImportUI();options.import_mesh=True;options.import_as_skeletal=True;options.mesh_type_to_import=u.FBXImportType.FBXIT_SKELETAL_MESH;options.original_import_type=u.FBXImportType.FBXIT_SKELETAL_MESH;options.automated_import_should_detect_type=False
    options.import_animations=False;options.import_materials=False;options.import_textures=False;options.create_physics_asset=False
    options.skeletal_mesh_import_data.normal_import_method=u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    if lib.does_asset_exist(destination+'/'+name+'_Skeleton'):
        options.skeleton=u.load_asset(destination+'/'+name+'_Skeleton');options.skeletal_mesh_import_data.set_editor_property('update_skeleton_reference_pose',True)
    task(source/'Export'/(name+'.fbx'),destination,name,options)
    mesh=u.load_asset(destination+'/'+name);assert isinstance(mesh,u.SkeletalMesh),name
    slots=list(mesh.materials)
    for slot in slots:slot.set_editor_property('material_interface',material_for(slot.get_editor_property('imported_material_slot_name')))
    mesh.materials=slots
    # Prevent reduction from averaging weights across separate mechanical parts.
    factory=u.DataAssetFactory();factory.set_editor_property('data_asset_class',u.SkeletalMeshLODSettings)
    lod_asset=create('DA_RobotLODSettings','/Game/Crusader/Robots',u.SkeletalMeshLODSettings,factory)
    lods=[]
    for fraction,screen in [(1.,1.),(.50,.50),(.25,.25)]:
        lod=u.SkeletalMeshLODGroupSettings();settings=lod.get_editor_property('reduction_settings')
        for key,value in [('num_of_triangles_percentage',fraction),('max_bones_per_vertex',1),('enforce_bone_boundaries',True),('merge_coincident_vert_bones',False),('lock_edges',True)]:settings.set_editor_property(key,value)
        lod.set_editor_property('reduction_settings',settings);lod.set_editor_property('screen_size',u.PerPlatformFloat(default=screen));lods.append(lod)
    lod_asset.set_editor_property('lod_groups',lods);save(lod_asset);mesh.set_editor_property('lod_settings',lod_asset)
    editor=u.get_editor_subsystem(u.SkeletalMeshEditorSubsystem);assert editor.regenerate_lod(mesh,3,False,False),name
    save(mesh);skeleton=mesh.get_editor_property('skeleton');save(skeleton)
    animation_options=u.FbxImportUI();animation_options.import_mesh=False;animation_options.import_animations=True;animation_options.import_materials=False;animation_options.import_textures=False;animation_options.skeleton=skeleton
    animation_options.mesh_type_to_import=u.FBXImportType.FBXIT_ANIMATION;animation_options.original_import_type=u.FBXImportType.FBXIT_ANIMATION;animation_options.automated_import_should_detect_type=False
    animation_options.anim_sequence_import_data.set_editor_property('custom_sample_rate',30)
    animations=task(source/'Export'/(name+'_JointCheck.fbx'),destination,name+'_JointCheck',animation_options)
    animation=next(a for a in animations if isinstance(a,u.AnimSequence));save(animation)
    modules=[]
    for part in manifest['parts']:
        options=u.FbxImportUI();options.import_mesh=True;options.import_as_skeletal=False;options.mesh_type_to_import=u.FBXImportType.FBXIT_STATIC_MESH;options.original_import_type=u.FBXImportType.FBXIT_STATIC_MESH;options.automated_import_should_detect_type=False
        options.import_materials=False;options.import_textures=False;options.static_mesh_import_data.combine_meshes=True;options.static_mesh_import_data.normal_import_method=u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
        objects=task(source/'Export/Parts'/(part['name']+'.fbx'),destination+'/Parts',part['name'],options)
        module=next(a for a in objects if isinstance(a,u.StaticMesh));slots=list(module.static_materials)
        for slot in slots:slot.set_editor_property('material_interface',material_for(slot.get_editor_property('imported_material_slot_name')))
        module.static_materials=slots;save(module);modules.append(module.get_path_name())
    factory=u.BlueprintFactory();factory.set_editor_property('parent_class',u.SkeletalMeshActor)
    bp=create('BP_'+name+'_Preview',destination,u.Blueprint,factory)
    cdo=u.get_default_object(bp.generated_class());component=cdo.skeletal_mesh_component
    component.set_skeletal_mesh_asset(mesh);component.set_animation_mode(u.AnimationMode.ANIMATION_SINGLE_NODE)
    play=u.SingleAnimationPlayData(anim_to_play=animation,saved_looping=True,saved_playing=True,saved_play_rate=1.0)
    component.set_editor_property('animation_data',play);component.set_collision_profile_name('NoCollision')
    u.BlueprintEditorLibrary.compile_blueprint(bp);assert not u.CRBlueprintTools.has_blueprint_errors(bp);save(bp)
    row=dict(name=name,mesh=mesh.get_path_name(),skeleton=skeleton.get_path_name(),animation=animation.get_path_name(),preview=bp.get_path_name(),lods=editor.get_lod_count(mesh),modules=modules)
    reports.append(row)
    (ROOT/'Artifacts/Robots'/name/'unreal-import.json').write_text(json.dumps(row,indent=2)+'\n')
    catalog_path=ROOT/'mockups/AssetSources.json';catalog=json.loads(catalog_path.read_text())
    for entry in catalog:
        if entry['name']==name:entry.update(imported=True,asset=row['mesh'])
    catalog_path.write_text(json.dumps(catalog,indent=2)+'\n')
    print('ROBOT_IMPORTED',name,len(modules),'modules',row['animation'])
print('ROBOT_IMPORT_COMPLETE',len(reports))
