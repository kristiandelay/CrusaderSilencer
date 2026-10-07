"""Blender background: scale, skin and export Black Iron Rifle on Lyra's rig."""
import bpy
import bmesh
import json
from pathlib import Path
from mathutils import Vector, Matrix

ROOT=Path(__file__).resolve().parents[1]
ASSET=ROOT/'Art/Weapons/BlackIronRifle'
OUT=ROOT/'Artifacts/CrimsonSentinel'
(ASSET/'Export').mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(OUT/'Rifle.fbx'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
for ob in list(bpy.context.scene.objects):
    if ob!=rig:bpy.data.objects.remove(ob,do_unlink=True)
bpy.ops.import_scene.fbx(filepath=str(ASSET/'Source/BlackIronRifle.fbx'))
mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
mesh.name='BlackIronRifle';mesh.data.name='BlackIronRifle'
bpy.context.view_layer.objects.active=mesh
bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True)
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
scale=.94/mesh.dimensions.x
for vertex in mesh.data.vertices:
    x,y,z=vertex.co
    vertex.co=Vector((-y*scale,(x-2.53)*scale,(z-.58)*scale))
source_triangles=len(mesh.data.polygons)
decimate=mesh.modifiers.new('Game topology','DECIMATE');decimate.ratio=22000/source_triangles;decimate.use_collapse_triangulate=True
bpy.ops.object.modifier_apply(modifier=decimate.name)
for poly in mesh.data.polygons:poly.use_smooth=True
mat=mesh.data.materials[0];mat.name='BlackIronRifle';mat.use_nodes=True
nodes=mat.node_tree.nodes;nodes.clear()
bsdf=nodes.new('ShaderNodeBsdfPrincipled');output=nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(bsdf.outputs['BSDF'],output.inputs['Surface'])
for kind,socket in [('BaseColor','Base Color'),('Metallic','Metallic'),('Roughness','Roughness'),('Normal',None)]:
    tex=nodes.new('ShaderNodeTexImage');tex.name='BlackIronRifle_'+kind;tex.image=bpy.data.images.load(str(ASSET/'Source'/(tex.name+'.png')))
    if kind!='BaseColor':tex.image.colorspace_settings.name='Non-Color'
    if socket:mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs[socket])
    else:
        normal=nodes.new('ShaderNodeNormalMap');mat.node_tree.links.new(tex.outputs['Color'],normal.inputs['Color']);mat.node_tree.links.new(normal.outputs['Normal'],bsdf.inputs['Normal'])
# Rigid receiver plus a magazine region driven by the existing reload animation.
# Split shared boundary vertices so the moving magazine cannot stretch triangles
# back to the receiver while the reload animation withdraws it.
bm=bmesh.new();bm.from_mesh(mesh.data)
mag_layer=bm.faces.layers.int.new('MagazineSection')
for face in bm.faces:
    center=face.calc_center_median()
    original_x=center.y/scale+2.53;original_z=center.z/scale+.58
    face[mag_layer]=int(.75<original_x<1.53 and original_z<.94)
boundary=[edge for edge in bm.edges if len({face[mag_layer] for face in edge.link_faces})>1]
bmesh.ops.split_edges(bm,edges=boundary)
bm.verts.index_update()
magazine_indices={v.index for face in bm.faces if face[mag_layer] for v in face.verts}
body_indices={v.index for face in bm.faces if not face[mag_layer] for v in face.verts}
assert not magazine_indices.intersection(body_indices),'Magazine is still attached to receiver'
bm.to_mesh(mesh.data);bm.free()
grip=mesh.vertex_groups.new(name='Grip');magazine=mesh.vertex_groups.new(name='Magazine')
for v in mesh.data.vertices:
    group=magazine if v.index in magazine_indices else grip
    group.add([v.index],1.0,'REPLACE')
mesh.parent=rig;mesh.matrix_parent_inverse=rig.matrix_world.inverted()
modifier=mesh.modifiers.new('Rifle rig','ARMATURE');modifier.object=rig
# Keep the original rifle bone axes but bake centimetres into the mesh. This
# avoids a 100x animated root and keeps muzzle sockets and reload travel correct.
mesh.parent=None;mesh.matrix_world=Matrix.Identity(4)
mesh.data.transform(Matrix.Scale(100.0,4))
rig.scale=(1,1,1)
bpy.context.scene.unit_settings.system='METRIC'
bpy.context.scene.unit_settings.scale_length=.01
bpy.context.view_layer.update()
mesh.parent=rig;mesh.matrix_parent_inverse=rig.matrix_world.inverted()
rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.wm.save_as_mainfile(filepath=str(ASSET/'BlackIronRifle.blend'))
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_as_mainfile(filepath=str(ASSET/'BlackIronRifle.blend'))
bpy.ops.export_scene.fbx(filepath=str(ASSET/'Export/BlackIronRifle.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=False,axis_forward='-Z',axis_up='Y',use_mesh_modifiers=True,mesh_smooth_type='FACE',path_mode='STRIP')
assert all(len({g.group for i in p.vertices for g in mesh.data.vertices[i].groups})==1 for p in mesh.data.polygons),'Reload would stretch receiver triangles'
report={'source_triangles':source_triangles,'game_triangles':len(mesh.data.polygons),'vertices':len(mesh.data.vertices),'length_m':.94,'grip_source':[2.53,0,.58],'source_scale':scale,'muzzle_ue_cm':[0,(-(-3.52072-2.53)*scale)*100,(1.32-.58)*scale*100],'skeleton':'Lyra rifle Root/Grip hierarchy','magazine_vertices':sum(1 for v in mesh.data.vertices if any(g.group==magazine.index for g in v.groups)),'detached_magazine':True,'cross_bone_triangles':0}
(OUT/'rifle-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
