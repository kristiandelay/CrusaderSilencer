"""Check rigid weights, panel edge lengths, piston alignment and FBX round trips."""
import bpy,json,sys,math
import numpy as np
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
NAME=sys.argv[sys.argv.index('--')+1]
ASSET=ROOT/'Art/Robots'/NAME;OUT=ROOT/'Artifacts/Robots'/NAME
bpy.ops.wm.open_mainfile(filepath=str(ASSET/(NAME+'.blend')))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
scene=bpy.context.scene
report=dict(name=NAME,passed=False,parts=len(meshes),poses=[],maximum_edge_length_change_cm=0.0)
for obj in meshes:
    assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in obj.data.vertices),obj.name
    assert len(obj.vertex_groups)==1,obj.name
    assert obj.vertex_groups[0].name==obj['RigidBone']
    assert all(abs(v-1)<1e-6 for v in obj.scale),obj.name
    assert obj.data.uv_layers or 'Axle' in obj.name or 'Piston' in obj.name,obj.name
assert all(abs(v-1)<1e-6 for v in rig.scale)
rest={}
scene.frame_set(1);bpy.context.view_layer.update()
def coordinates(obj):
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());data=evaluated.to_mesh()
    xyz=np.empty(len(data.vertices)*3,dtype=np.float32);data.vertices.foreach_get('co',xyz)
    evaluated.to_mesh_clear();return xyz.reshape((-1,3))
for obj in meshes:
    edges=np.empty(len(obj.data.edges)*2,dtype=np.int32);obj.data.edges.foreach_get('vertices',edges);edges=edges.reshape((-1,2))
    xyz=coordinates(obj);rest[obj.name]=(edges,np.linalg.norm(xyz[edges[:,0]]-xyz[edges[:,1]],axis=1),xyz)
for frame in [1,16,31,46,61,76,91,106,121]:
    scene.frame_set(frame);bpy.context.view_layer.update();max_delta=0.;travel=0.;alignment=[]
    for obj in meshes:
        edges,lengths,start=rest[obj.name];xyz=coordinates(obj)
        delta=float(np.max(np.abs(np.linalg.norm(xyz[edges[:,0]]-xyz[edges[:,1]],axis=1)-lengths)))
        max_delta=max(max_delta,delta);travel=max(travel,float(np.max(np.linalg.norm(xyz-start,axis=1))))
        assert delta<.002,(obj.name,frame,delta)
    for pb in rig.pose.bones:
        if pb.name.startswith(('piston_housing_','piston_rod_')):
            end=rig.pose.bones[pb.constraints['Hydraulic aim'].subtarget].head
            error=math.degrees(pb.y_axis.angle(end-pb.head));assert error<.05,(pb.name,frame,error)
            alignment.append(error)
    if frame in [31,91]:assert travel>5,('Preview did not exercise joints',frame,travel)
    report['poses'].append(dict(frame=frame,maximum_edge_length_change_cm=max_delta,maximum_travel_cm=travel,piston_alignment_errors_degrees=alignment))
    report['maximum_edge_length_change_cm']=max(report['maximum_edge_length_change_cm'],max_delta)

scene.frame_set(1);rig['FootIK']=1.0;rig.update_tag();report['foot_ik']=[]
for offset in [(0,0,5),(0,-8,5),(0,8,5),(0,0,0)]:
    for side in ['l','r']:
        control=rig.pose.bones['foot_control_'+side]
        control.location=control.bone.matrix_local.to_3x3().inverted()@Vector(offset)
    bpy.context.view_layer.update()
    errors=[(rig.pose.bones['lower_leg_'+side].tail-rig.pose.bones['foot_control_'+side].head).length for side in ['l','r']]
    assert max(errors)<.1,('Foot IK missed reachable target',offset,errors)
    report['foot_ik'].append(dict(offset_cm=offset,errors_cm=errors))
rig['FootIK']=0.0;rig.update_tag();bpy.context.view_layer.update()

# Actual model captures; no image generation or edits.
scene.render.engine='CYCLES';scene.cycles.samples=16
scene.world=bpy.data.worlds.new('MechanicalStudio');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.18,.21,.25,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7
center=Vector((0,0,90));size=180
for offset,energy in [((1,-2,2),400),((-2,-1,1),250),((1,2,2),600)]:
    bpy.ops.object.light_add(type='AREA',location=center+Vector(offset)*size)
    lamp=bpy.context.object;lamp.data.energy=energy*size*size;lamp.data.size=size*2;lamp.rotation_euler=(center-lamp.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();camera=bpy.context.object;camera.data.type='ORTHO';camera.data.ortho_scale=235;camera.data.clip_end=10000;scene.camera=camera
scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
for label,frame,offset in [('Rest',1,(3,-4,1.5)),('BentSide',31,(4,0,0)),('Bent',31,(3,-4,1.5))]:
    scene.frame_set(frame);camera.location=center+Vector(offset)*size;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/(label+'.png'));bpy.ops.render.render(write_still=True)

# Reimport the delivered FBX and verify the actual portable skin, not just Blender.
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(ASSET/'Export'/(NAME+'.fbx')))
imported=[o for o in bpy.context.scene.objects if o.type=='MESH'];arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
assert len(imported)==len(meshes),(len(imported),len(meshes))
for obj in imported:
    assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-5 for v in obj.data.vertices),obj.name
assert all(n in arm.data.bones for n in ['root','chassis','upper_leg_l','middle_leg_l','lower_leg_l','foot_l','upper_leg_r','middle_leg_r','lower_leg_r','foot_r'])
report.update(passed=True,fbx_parts=len(imported),fbx_bones=len(arm.data.bones),maximum_influences=1)
(OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('ROBOT_RIG_VALIDATED',json.dumps(report),flush=True)
