"""Validate the delivered Unreal meshes, LOD weights, materials and baked motion.

Run in the editor after Import-RobotAssets.py. Blender validates every vertex and
edge; this independently samples the actual imported mesh at every Unreal LOD.
"""
import hashlib
import json
import random
from pathlib import Path
import unreal as u

ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
names=list(json.loads((ROOT/'resources/RobotRigs.json').read_text()))
query=u.GeometryScript_MeshQueries
weights=u.GeometryScript_BoneWeights
editor=u.get_editor_subsystem(u.SkeletalMeshEditorSubsystem)
results=[]

for name in names:
    source=ROOT/'Art/Robots'/name
    manifest=json.loads((source/'RigManifest.json').read_text())
    blender=json.loads((ROOT/'Artifacts/Robots'/name/'validation.json').read_text())
    imported=json.loads((ROOT/'Artifacts/Robots'/name/'unreal-import.json').read_text())
    assert blender['passed'] and len(imported['modules'])==len(manifest['parts']),name
    mesh=u.load_asset(imported['mesh']);animation=u.load_asset(imported['animation'])
    assert mesh and animation and editor.get_lod_count(mesh)==3,name
    for slot in mesh.materials:
        material=slot.get_editor_property('material_interface')
        assert material and material.get_path_name().startswith('/Game/Crusader/Robots/'+name),name
    for asset in imported['modules']:assert isinstance(u.load_asset(asset),u.StaticMesh),asset
    for kind in ['BaseColor','Normal','Roughness','Metallic']:
        texture=u.load_asset('/Game/Crusader/Robots/'+name+'/Textures/'+name+'_'+kind)
        assert isinstance(texture,u.Texture2D),kind
        assert texture.get_editor_property('srgb')==(kind=='BaseColor'),kind
    bp=u.load_asset(imported['preview'])
    assert bp and not u.CRBlueprintTools.has_blueprint_errors(bp),name
    component=u.get_default_object(bp.generated_class()).skeletal_mesh_component
    assert component.get_editor_property('animation_data').get_editor_property('anim_to_play')==animation
    lod_reports=[]
    for lod in range(3):
        dynamic=u.DynamicMesh()
        read=u.GeometryScriptMeshReadLOD(lod_type=u.GeometryScriptLODType.RENDER_DATA,lod_index=lod)
        dynamic,outcome=u.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(mesh,dynamic,u.GeometryScriptCopyMeshFromAssetOptions(),read)
        assert outcome==u.GeometryScriptOutcomePins.SUCCESS,(name,lod,outcome)
        count=query.get_num_triangle_i_ds(dynamic)
        assert count>1000,(name,lod,count)
        bounds=query.get_mesh_bounding_box(dynamic)
        height=bounds.max.z-bounds.min.z
        assert 175<height<185,(name,lod,'Incorrect centimeter scale',height)
        rng=random.Random(714+lod)
        samples=sorted(set([0,count-1]+rng.sample(range(count),min(2048,count))))
        tested=0;vertices=set();bones=set()
        for triangle in samples:
            indices,valid=query.get_triangle_indices(dynamic,triangle)
            if not valid:continue
            triangle_bones=[]
            for vertex in [indices.x,indices.y,indices.z]:
                _,influences,has_weights=weights.get_vertex_bone_weights(dynamic,vertex)
                positive=[w for w in influences if w.weight>1e-6]
                assert has_weights and len(positive)==1,(name,lod,triangle,vertex,'blended weights')
                assert abs(positive[0].weight-1)<1e-5,(name,lod,vertex,positive[0].weight)
                triangle_bones.append(positive[0].bone_index);vertices.add(vertex);bones.add(positive[0].bone_index)
            assert len(set(triangle_bones))==1,(name,lod,triangle,'triangle bridges moving parts')
            tested+=1
        assert tested>=2000 and len(bones)>=8,(name,lod,tested,bones)
        lod_reports.append(dict(lod=lod,triangles=count,height_cm=height,sampled_triangles=tested,sampled_vertices=len(vertices),sampled_bones=len(bones),maximum_influences=1))
    assert lod_reports[2]['triangles']<lod_reports[1]['triangles']<lod_reports[0]['triangles'],name
    animation_bones=['root']+manifest['bones']
    for bone in animation_bones:
        assert u.AnimationLibrary.does_bone_name_exist(animation,bone),(name,bone)
        for sample_time in [0,.5,1,1.5,2,2.5,3,3.5,4]:
            pose=u.AnimationLibrary.get_bone_pose_for_time(animation,bone,sample_time,False)
            assert all(abs(v-1)<.001 for v in [pose.scale3d.x,pose.scale3d.y,pose.scale3d.z]),(name,bone,sample_time,pose)
    moving=[]
    for bone in manifest['bones']:
        a=u.AnimationLibrary.get_bone_pose_for_time(animation,bone,0,False).rotation
        b=u.AnimationLibrary.get_bone_pose_for_time(animation,bone,1,False).rotation
        delta=max(abs(getattr(a,c)-getattr(b,c)) for c in ['x','y','z','w'])
        if delta>.001:moving.append(bone)
    assert all(bone in moving for bone in manifest['bones'] if bone!='chassis'),(name,moving)
    digest=hashlib.sha256((source/'Export'/(name+'.fbx')).read_bytes()).hexdigest()
    result=dict(name=name,passed=True,fbx_sha256=digest,blender=blender,unreal=dict(**imported,lod_validation=lod_reports,animated_bones=moving,bone_scales_unit=True))
    results.append(result)
    print('ROBOT_IMPORT_VALIDATED',name,[(r['lod'],r['triangles']) for r in lod_reports])

report=dict(passed=True,robots=results)
preview_path=ROOT/'Artifacts/Robots/unreal-preview-validation.json'
if preview_path.exists() and preview_path.stat().st_mtime>=max((ROOT/'Artifacts/Robots'/name/'unreal-import.json').stat().st_mtime for name in names):
    preview=json.loads(preview_path.read_text())
    assert preview['passed'] and {r['name'] for r in preview['robots']}==set(names)
    report['unreal_playback']=preview
(ROOT/'resources/RobotRigValidation.json').write_text(json.dumps(report,indent=2)+'\n')
print('ROBOT_IMPORT_VALIDATION_COMPLETE',len(results))
