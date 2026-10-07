"""Blender: exercise all ten fingers and preserve an editable grip-check action."""
import bpy
import json
import math
from pathlib import Path
from mathutils import Vector, Quaternion

ROOT=Path(__file__).resolve().parents[1]
ASSET=ROOT/'Art/Characters/CrimsonSentinel'
bpy.ops.wm.open_mainfile(filepath=str(ASSET/'CrimsonSentinel.blend'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
for pb in rig.pose.bones:
    pb.rotation_mode='QUATERNION';pb.rotation_quaternion=Quaternion()
rig.animation_data_clear()
for action in list(bpy.data.actions):
    if action.name.startswith('CrimsonSentinel_GripCheck'):
        bpy.data.actions.remove(action)
bpy.context.view_layer.update()

def vertices():
    evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    temporary=evaluated.to_mesh()
    result=[v.co.copy() for v in temporary.vertices]
    evaluated.to_mesh_clear()
    return result

rest=vertices()
results=[]
for side,sign in [('l',1),('r',-1)]:
    for finger in ['thumb','index','middle','ring','pinky']:
        names=[finger+'_%02d_'%i+side for i in range(1,4)]
        groups={g.index for g in mesh.vertex_groups if g.name in names}
        influenced=[v.index for v in mesh.data.vertices if any(g.group in groups and g.weight>.25 for g in v.groups)]
        assert influenced, names
        for name,angle in zip(names,[35,50,25]):
            pb=rig.pose.bones[name]
            axis=pb.bone.matrix_local.to_3x3().inverted()@Vector((0,sign,0))
            pb.rotation_quaternion=Quaternion(axis,math.radians(angle))
        bpy.context.view_layer.update()
        posed=vertices()
        distances=[(posed[i]-rest[i]).length for i in influenced]
        result={'finger':finger+'_'+side,'weighted_vertices':len(influenced),'maximum_travel_cm':max(distances),'average_travel_cm':sum(distances)/len(distances)}
        assert result['maximum_travel_cm']>1.0,result
        assert result['maximum_travel_cm']<25,result
        results.append(result)
        for name in names:rig.pose.bones[name].rotation_quaternion=Quaternion()
        bpy.context.view_layer.update()

# A reusable Blender inspection action: neutral -> closed grip -> neutral.
for frame,closed in [(1,False),(20,True),(40,False)]:
    for side,sign in [('l',1),('r',-1)]:
        for finger in ['thumb','index','middle','ring','pinky']:
            for i,angle in enumerate([35,50,25],1):
                pb=rig.pose.bones[f'{finger}_{i:02d}_{side}']
                axis=pb.bone.matrix_local.to_3x3().inverted()@Vector((0,sign,0))
                pb.rotation_quaternion=Quaternion(axis,math.radians(angle if closed else 0))
                pb.keyframe_insert('rotation_quaternion',frame=frame,group=pb.name)
action=rig.animation_data.action
action.name='CrimsonSentinel_GripCheck';action.use_fake_user=True
rig.animation_data.action=None
for pb in rig.pose.bones:pb.rotation_quaternion=Quaternion()
bpy.context.scene.frame_set(1)
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_as_mainfile(filepath=str(ASSET/'CrimsonSentinel.blend'))
(ROOT/'Artifacts/CrimsonSentinel/finger-deformation.json').write_text(json.dumps({'passed':True,'action':action.name,'fingers':results},indent=2))
print('FINGER_DEFORMATION_PASSED',json.dumps(results),flush=True)
# Also make the weapon source portable without altering its exported rig.
weapon=ROOT/'Art/Weapons/BlackIronRifle/BlackIronRifle.blend'
bpy.ops.wm.open_mainfile(filepath=str(weapon));bpy.ops.file.make_paths_relative();bpy.ops.wm.save_as_mainfile(filepath=str(weapon))
