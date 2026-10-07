"""Fit the two Meshy weapons to the existing Lyra rigs, retaining moving parts."""
import bpy
import bmesh
import json
from pathlib import Path
from mathutils import Vector, Matrix

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'Artifacts/WeaponReplacements'
SPECS=[
    dict(name='FuturisticPistol',kind='Pistol',length=.31,grip=(1.17,0,.43),
         muzzle=(-1.68,0,1.46),eject=(.6,-.16,1.40),triangles=14000),
    dict(name='TitanBreaker',kind='Shotgun',length=.68,grip=(1.97,0,.44),
         muzzle=(-2.58,0,1.35),eject=(.6,-.22,1.30),triangles=22000),
]

def section(name,center):
    x,y,z=center
    if name=='FuturisticPistol':
        if z<.18 and x>.80:return 'Magazine'
        if z>1.29 and x>-1.50:return 'Slide'
    else:
        if .54<x<1.09 and .60<z<1.03:return 'Magazine'
        if -1.03<x<.14 and .76<z<1.13:return 'Bolt'
    return 'Grip'

for spec in SPECS:
    name=spec['name'];folder=ROOT/'Art/Weapons'/name
    (folder/'Export').mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(OUT/(spec['kind']+'.fbx')))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    for ob in list(bpy.context.scene.objects):
        if ob!=rig:bpy.data.objects.remove(ob,do_unlink=True)
    bpy.ops.import_scene.fbx(filepath=str(folder/'Source'/(name+'.fbx')))
    mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
    mesh.name=name;mesh.data.name=name
    bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True)
    bpy.context.view_layer.objects.active=mesh
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    source_triangles=sum(len(p.vertices)-2 for p in mesh.data.polygons)
    scale=spec['length']/mesh.dimensions.x
    # Retain source coordinates until moving sections have been separated.
    decimate=mesh.modifiers.new('Game topology','DECIMATE')
    decimate.ratio=spec['triangles']/source_triangles;decimate.use_collapse_triangulate=True
    bpy.ops.object.modifier_apply(modifier=decimate.name)
    bm=bmesh.new();bm.from_mesh(mesh.data)
    layer=bm.faces.layers.int.new('RigidSection')
    group_names=['Grip','Magazine','Slide' if spec['kind']=='Pistol' else 'Bolt']
    for face in bm.faces:face[layer]=group_names.index(section(name,face.calc_center_median()))
    boundaries=[edge for edge in bm.edges if len({f[layer] for f in edge.link_faces})>1]
    bmesh.ops.split_edges(bm,edges=boundaries);bm.verts.index_update()
    indices={i:{v.index for f in bm.faces if f[layer]==i for v in f.verts} for i in range(len(group_names))}
    assert sum(map(len,indices.values()))==len(bm.verts),'Moving sections remain welded'
    bm.to_mesh(mesh.data);bm.free()
    for i,bone in enumerate(group_names):
        assert bone in rig.data.bones and indices[i],bone
        mesh.vertex_groups.new(name=bone).add(sorted(indices[i]),1,'REPLACE')
    def fit(point):
        p=Vector(point)-Vector(spec['grip'])
        return Vector((-p.y,p.x,p.z))*scale*100
    for vertex in mesh.data.vertices:vertex.co=fit(vertex.co)
    for poly in mesh.data.polygons:poly.use_smooth=True
    material=bpy.data.materials.new(name);material.use_nodes=True
    mesh.data.materials.clear();mesh.data.materials.append(material)
    bsdf=material.node_tree.nodes.get('Principled BSDF')
    for kind,socket in [('BaseColor','Base Color'),('Metallic','Metallic'),('Roughness','Roughness'),('Normal',None)]:
        tex=material.node_tree.nodes.new('ShaderNodeTexImage');tex.name=name+'_'+kind
        tex.image=bpy.data.images.load(str(folder/'Source'/(tex.name+'.png')))
        if kind!='BaseColor':tex.image.colorspace_settings.name='Non-Color'
        if socket:material.node_tree.links.new(tex.outputs['Color'],bsdf.inputs[socket])
        else:
            normal=material.node_tree.nodes.new('ShaderNodeNormalMap')
            material.node_tree.links.new(tex.outputs['Color'],normal.inputs['Color'])
            material.node_tree.links.new(normal.outputs['Normal'],bsdf.inputs['Normal'])
    # Reference FBX stores centimetres in the armature and .01 on its object.
    # Bake geometry into the same units without scaling animated bones.
    rig.scale=(1,1,1)
    bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.01
    bpy.context.view_layer.update()
    mesh.parent=rig;mesh.matrix_parent_inverse=rig.matrix_world.inverted()
    modifier=mesh.modifiers.new('Weapon rig','ARMATURE');modifier.object=rig
    rig.select_set(True);bpy.context.view_layer.objects.active=rig
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/(name+'.blend')))
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/(name+'.blend')))
    bpy.ops.export_scene.fbx(filepath=str(folder/'Export'/(name+'.fbx')),use_selection=True,
        object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=False,
        axis_forward='-Z',axis_up='Y',use_mesh_modifiers=True,mesh_smooth_type='FACE',path_mode='STRIP')
    assert all(len({g.group for i in p.vertices for g in mesh.data.vertices[i].groups})==1 for p in mesh.data.polygons)
    # Grip bone coordinates: X runs forward along the bore, Z points up.
    def grip_space(point):
        fitted=fit(point)
        return [-fitted.y,fitted.x,fitted.z]
    report=dict(spec,source_triangles=source_triangles,game_triangles=len(mesh.data.polygons),
        vertices=len(mesh.data.vertices),source_scale=scale,
        muzzle_grip_cm=grip_space(spec['muzzle']),eject_grip_cm=grip_space(spec['eject']),
        section_vertices={bone:len(indices[i]) for i,bone in enumerate(group_names)},
        unweighted_vertices=0,cross_bone_triangles=0)
    (OUT/(name+'-rig.json')).write_text(json.dumps(report,indent=2)+'\n')
    print('PREPARED',json.dumps(report),flush=True)
