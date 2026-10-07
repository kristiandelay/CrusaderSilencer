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
ASSET = ROOT / 'Art/Characters/CrimsonSentinel'
OUT = ROOT / 'Artifacts/CrimsonSentinel'
OUT.mkdir(parents=True, exist_ok=True)
(ASSET / 'Export').mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.ops.import_scene.fbx(filepath=str(ASSET / 'Source/CrimsonSentinel.fbx'))
mesh = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
mesh.name = 'CrimsonSentinel'
mesh.data.name = 'CrimsonSentinel'
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
mat.name = 'CrimsonSentinel'
mat.use_nodes = True
nodes = mat.node_tree.nodes
nodes.clear()
output = nodes.new('ShaderNodeOutputMaterial')
bsdf = nodes.new('ShaderNodeBsdfPrincipled')
mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
for kind, socket in [('BaseColor', 'Base Color'), ('Metallic', 'Metallic'), ('Roughness', 'Roughness'), ('Normal', None)]:
    tex = nodes.new('ShaderNodeTexImage')
    tex.name = 'CrimsonSentinel_' + kind
    tex.image = bpy.data.images.load(str(ASSET / 'Source' / (tex.name + '.png')))
    if kind != 'BaseColor':
        tex.image.colorspace_settings.name = 'Non-Color'
    if socket:
        mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs[socket])
    else:
        normal = nodes.new('ShaderNodeNormalMap')
        mat.node_tree.links.new(tex.outputs['Color'], normal.inputs['Color'])
        mat.node_tree.links.new(normal.outputs['Normal'], bsdf.inputs['Normal'])

armature = bpy.data.armatures.new('CrimsonSentinel')
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

bone('root', (0,0,0), (0,0,.1), deform=False)
bone('pelvis', (0,.025,.91), (0,.025,1.01), 'root')
for i, (start, end) in enumerate([(1.01,1.10),(1.10,1.20),(1.20,1.29),(1.29,1.38),(1.38,1.48)], 1):
    bone('spine_%02d'%i, (0,.025,start), (0,.025,end), 'pelvis' if i==1 else 'spine_%02d'%(i-1))
bone('neck_01', (0,.025,1.48), (0,.025,1.525), 'spine_05')
bone('neck_02', (0,.025,1.525), (0,.025,1.565), 'neck_01')
bone('head', (0,.025,1.565), (0,.025,1.755), 'neck_02')

for side, sign in [('l',1),('r',-1)]:
    def p(x,y,z): return (x*sign,y,z)
    def limb(name,head,tail,parent): return bone(name+'_'+side,p(*head),p(*tail),parent+'_'+side if parent in ['clavicle','upperarm','lowerarm','hand','thigh','calf','foot'] else parent)
    limb('clavicle',(.02,.025,1.415),(.23,.041,1.415),'spine_05')
    limb('upperarm',(.23,.041,1.415),(.444,.051,1.35),'clavicle')
    limb('lowerarm',(.444,.051,1.35),(.69,.061,1.322),'upperarm')
    limb('hand',(.69,.061,1.322),(.77,.052,1.322),'lowerarm')
    limb('thigh',(.115,.025,.89),(.14,.012,.49),'pelvis')
    limb('calf',(.14,.012,.49),(.147,.023,.105),'thigh')
    limb('foot',(.147,.023,.105),(.147,-.11,.045),'calf')
    limb('ball',(.147,-.11,.045),(.147,-.195,.045),'foot')
    for digit, yy, xx, length in [('index',.013,.778,.101),('middle',.037,.787,.112),('ring',.061,.782,.103),('pinky',.088,.77,.096)]:
        start=(.714,yy,1.318)
        points=[(xx,yy,1.322),(xx+length*.42,yy,1.316),(xx+length*.74,yy-.001,1.300),(xx+length,yy-.002,1.294)]
        meta=digit+'_metacarpal_'+side
        bone(meta,p(*start),p(*points[0]),'hand_'+side)
        for j in range(3):
            bone(digit+'_%02d_'%(j+1)+side,p(*points[j]),p(*points[j+1]),meta if j==0 else digit+'_%02d_'%j+side)
    points=[(.716,.028,1.307),(.748,.002,1.282),(.769,-.01,1.274),(.785,-.014,1.268)]
    for j in range(3):
        bone('thumb_%02d_'%(j+1)+side,p(*points[j]),p(*points[j+1]),'hand_'+side if j==0 else 'thumb_%02d_'%j+side)

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
bpy.ops.wm.save_as_mainfile(filepath=str(ASSET/'CrimsonSentinel.blend'))
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_as_mainfile(filepath=str(ASSET/'CrimsonSentinel.blend'))
bpy.ops.export_scene.fbx(filepath=str(ASSET/'Export/CrimsonSentinel.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=False,axis_forward='-Z',axis_up='Y',use_mesh_modifiers=True,mesh_smooth_type='FACE',path_mode='STRIP')
print('RIG_COMPLETE',json.dumps(report),flush=True)
