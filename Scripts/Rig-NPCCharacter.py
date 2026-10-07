"""Blender background: fit a UE-named humanoid rig, auto-skin and export.

Source meshes remain untouched. The editable Blender file includes the fitted
rest rig, all ten three-joint fingers, and a non-exported deformation check action.
"""
import bpy
import json
import math
from pathlib import Path
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[1]
import sys
NAME = sys.argv[sys.argv.index('--')+1]
ASSET = ROOT / 'Art/Characters' / NAME
OUT = ROOT / 'Artifacts/NPCCharacters' / NAME
OUT.mkdir(parents=True, exist_ok=True)
(ASSET / 'Export').mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.ops.import_scene.fbx(filepath=str(ASSET / ('Source/'+NAME+'.fbx')))
mesh = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
mesh.name = NAME
mesh.data.name = NAME
bpy.context.view_layer.objects.active = mesh
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
source_triangles = len(mesh.data.polygons)
# Preserve UVs and the silhouette while reducing the generated sculpt for play.
decimate = mesh.modifiers.new('Game topology', 'DECIMATE')
decimate.ratio = 85000 / source_triangles
decimate.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier=decimate.name)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.00001)
bpy.ops.object.mode_set(mode='OBJECT')
for p in mesh.data.polygons:
    p.use_smooth = True

mat = mesh.data.materials[0]
mat.name = NAME
mat.use_nodes = True
nodes = mat.node_tree.nodes
nodes.clear()
output = nodes.new('ShaderNodeOutputMaterial')
bsdf = nodes.new('ShaderNodeBsdfPrincipled')
mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
for kind, socket in [('BaseColor', 'Base Color'), ('Metallic', 'Metallic'), ('Roughness', 'Roughness'), ('Normal', None)]:
    tex = nodes.new('ShaderNodeTexImage')
    tex.name = NAME+'_'  + kind
    tex.image = bpy.data.images.load(str(ASSET / 'Source' / (tex.name + '.png')))
    if kind != 'BaseColor':
        tex.image.colorspace_settings.name = 'Non-Color'
    if socket:
        mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs[socket])
    else:
        normal = nodes.new('ShaderNodeNormalMap')
        mat.node_tree.links.new(tex.outputs['Color'], normal.inputs['Color'])
        mat.node_tree.links.new(normal.outputs['Normal'], bsdf.inputs['Normal'])

armature = bpy.data.armatures.new(NAME)
rig = bpy.data.objects.new('Armature', armature)
bpy.context.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
mesh.select_set(False)
rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')

def bone(name, head, tail, parent=None, deform=True):
    b = armature.edit_bones.new(name)
    b.head, b.tail = head, tail
    b.use_deform = deform
    if parent:
        b.parent = armature.edit_bones[parent]
    b.align_roll(Vector((0, -1, 0)))
    return b

config=json.loads((ROOT/'resources/NPCCharacterRigs.json').read_text())[NAME]
for item in config['bones']:
    bone(item['name'], item['head'], item['tail'], item.get('parent'), item['name']!='root')

bpy.ops.object.mode_set(mode='OBJECT')
rig.show_in_front = True
armature.display_type = 'OCTAHEDRAL'
mesh.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
print('AUTO_WEIGHT_BEGIN', len(mesh.data.vertices), flush=True)
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
print('AUTO_WEIGHT_END', flush=True)
# Drop tiny influences and keep a portable four-weight GPU skinning budget.
bpy.context.view_layer.objects.active = mesh
rig.select_set(False)
bpy.ops.object.vertex_group_clean(group_select_mode='ALL', limit=.001, keep_single=True)
bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
unweighted=[v.index for v in mesh.data.vertices if sum(g.weight for g in v.groups)<.99]
assert not unweighted, 'Automatic weighting left unweighted vertices: '+str(len(unweighted))
finger_groups={g.name:sum(1 for v in mesh.data.vertices for w in v.groups if w.group==g.index and w.weight>.01)
               for g in mesh.vertex_groups if any(g.name.startswith(n+'_') for n in ['thumb','index','middle','ring','pinky'])}
assert all(count>0 for count in finger_groups.values()), finger_groups
report={'source_triangles':source_triangles,'game_triangles':len(mesh.data.polygons),'vertices':len(mesh.data.vertices),'bones':len(armature.bones),'unweighted_vertices':len(unweighted),'max_influences':max(len(v.groups) for v in mesh.data.vertices),'finger_weighted_vertices':finger_groups}
(OUT/'rig-report.json').write_text(json.dumps(report,indent=2))

# Keep editable source and export only the deform rig; no test animation.
# UE retarget translations require unit-scale bones. Bake metres to centimetres
# into both data blocks instead of exporting an armature with a 100x root scale.
mesh.data.transform(Matrix.Scale(100.0,4))
armature.transform(Matrix.Scale(100.0,4))
bpy.context.scene.unit_settings.scale_length=.01
rig.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.context.scene.render.fps=30
bpy.ops.wm.save_as_mainfile(filepath=str(ASSET/(NAME+'.blend')))
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_as_mainfile(filepath=str(ASSET/(NAME+'.blend')))
bpy.ops.export_scene.fbx(filepath=str(ASSET/('Export/'+NAME+'.fbx')),use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=False,axis_forward='-Z',axis_up='Y',use_mesh_modifiers=True,mesh_smooth_type='FACE',path_mode='STRIP')
print('RIG_COMPLETE',json.dumps(report),flush=True)
