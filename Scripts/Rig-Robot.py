"""Cut fused robot sculpts into closed rigid parts, fit mechanical rigs and export.

Run Inspect-RobotSources.py first. It caches a UV-preserving game-resolution
copy; the supplied FBX/textures always remain untouched in Source/.
"""
import bpy,bmesh,json,math,sys
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion

ROOT=Path(__file__).resolve().parents[1]
NAME=sys.argv[sys.argv.index('--')+1]
CFG=json.loads((ROOT/'resources/RobotRigs.json').read_text())[NAME]
ASSET=ROOT/'Art/Robots'/NAME
OUT=ROOT/'Artifacts/Robots'/NAME;OUT.mkdir(parents=True,exist_ok=True)
EXPORT=ASSET/'Export';EXPORT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Artifacts/Robots'/(NAME+'_Working.blend')))
scene=bpy.context.scene
source=next(o for o in scene.objects if o.type=='MESH')

def metal(name,color,roughness):
    mat=bpy.data.materials.new(NAME+'_'+name);mat.use_nodes=True
    bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Metallic'].default_value=.85;bs.inputs['Roughness'].default_value=roughness
    return mat

inner=metal('JointMetal',(.075,.085,.095),.33)
chrome=metal('PistonMetal',(.32,.36,.40),.22)
original=source.data.materials[0];original.name='M_'+NAME
bs=original.node_tree.nodes.get('Principled BSDF')
for kind,socket in [('Metallic','Metallic'),('Roughness','Roughness'),('Normal',None)]:
    tex=original.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ASSET/'Source'/(NAME+'_'+kind+'.png')))
    tex.image.name=NAME+'_'+kind
    tex.image.colorspace_settings.name='Non-Color'
    if socket:original.node_tree.links.new(tex.outputs['Color'],bs.inputs[socket])
    else:
        n=original.node_tree.nodes.new('ShaderNodeNormalMap');original.node_tree.links.new(tex.outputs['Color'],n.inputs['Color']);original.node_tree.links.new(n.outputs['Normal'],bs.inputs['Normal'])
source.data.materials.append(inner)
parts=[];cap_count=0

def activate(obj):
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj

sys.path.insert(0,str(ROOT/'Scripts'))
from RobotMeshTools import modularize
parts,cap_count=modularize(source,NAME,CFG,inner)

arm=bpy.data.armatures.new(NAME+'_Rig');rig=bpy.data.objects.new('Armature',arm);bpy.context.collection.objects.link(rig)
activate(rig);bpy.ops.object.mode_set(mode='EDIT')
def bone(name,a,b,parent=None,deform=True):
    a,b=Vector(a),Vector(b)
    eb=arm.edit_bones.new(name);eb.head=a;eb.tail=b;eb.use_deform=deform
    # All sagittal hinges rotate around local X = robot lateral X.
    y=(b-a).normalized();x=Vector((1,0,0));x=(x-y*x.dot(y)).normalized();z=x.cross(y)
    eb.matrix=Matrix((x,y,z)).transposed().to_4x4();eb.head=a;eb.tail=b
    if parent:eb.parent=arm.edit_bones[parent]
    return eb
bone('root',(0,0,0),(0,0,.10),deform=False)
bone('chassis',(0,0,CFG['leg_top']),(0,0,CFG['leg_top']+.20),'root')
for side,sign in [('l',1),('r',-1)]:
    # Moving a pivot along its lateral axle does not change that hinge's axis.
    # Keep the bone chain coplanar so foot IK can honor true mechanical hinges.
    points=[Vector((CFG['joints'][0][0]*sign,p[1],p[2])) for p in CFG['joints']]
    for index,label in enumerate(['upper_leg','middle_leg','lower_leg','foot']):
        a=points[index];b=points[index+1] if index<3 else a+Vector((0,-.16,-.08))
        parent='chassis' if index==0 else ['upper_leg','middle_leg','lower_leg'][index-1]+'_'+side
        bone(label+'_'+side,a,b,parent)
    bone('foot_control_'+side,points[3],points[3]+Vector((0,-.12,0)),'root',False)
    bone('knee_pole_'+side,points[1]+Vector((0,-.7,0)),points[1]+Vector((0,-.7,.12)),'root',False)
    if 'piston' in CFG:
        a=Vector(CFG['piston']['a']);b=Vector(CFG['piston']['b']);a.x*=sign;b.x*=sign
        bone('piston_anchor_a_'+side,a,a+Vector((0,0,.04)),'upper_leg_'+side,False)
        bone('piston_anchor_b_'+side,b,b+Vector((0,0,.04)),'middle_leg_'+side,False)
        bone('piston_housing_'+side,a,b,'upper_leg_'+side)
        bone('piston_rod_'+side,b,a,'middle_leg_'+side)
bpy.ops.object.mode_set(mode='OBJECT');rig.show_in_front=True
rig['FootIK']=0.0;rig.id_properties_ui('FootIK').update(min=0,max=1,description='0: FK hinge controls; 1: three-link foot IK with knee pole controls')
for side,sign in [('l',1),('r',-1)]:
    points=[Vector((p[0]*sign,p[1],p[2])) for p in CFG['joints']]
    # Axle inserts conceal the interiors exposed when adjacent rigid sections
    # rotate. The original textured external housings are retained.
    for index,(pivot,radius) in enumerate(zip(points,CFG['radii'])):
        bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=radius,depth=.06 if NAME=='SentinelWalker' else .08,location=pivot,rotation=(0,math.pi/2,0))
        obj=bpy.context.object;obj.name=NAME+'_Axle_'+str(index)+'_'+side;obj.data.materials.append(inner)
        activate(obj);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        for p in obj.data.polygons:p.use_smooth=len(p.vertices)==4
        parts.append((obj,['upper_leg','middle_leg','lower_leg','foot'][index]+'_'+side))
    if 'piston' in CFG:
        a=Vector(CFG['piston']['a']);b=Vector(CFG['piston']['b']);a.x*=sign;b.x*=sign
        for label,start,end,length,radius,mat in [('housing',a,b,.64,CFG['piston']['radius'],inner),('rod',b,a,.65,CFG['piston']['radius']*.55,chrome)]:
            axis=(end-start).normalized();extent=(end-start).length*length
            bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=radius,depth=extent,location=start+axis*extent*.5)
            obj=bpy.context.object;obj.name=NAME+'_Piston_'+label+'_'+side;obj.rotation_euler=axis.to_track_quat('Z','Y').to_euler();obj.data.materials.append(mat)
            activate(obj);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
            for p in obj.data.polygons:p.use_smooth=len(p.vertices)==4
            parts.append((obj,'piston_'+label+'_'+side))
            pb=rig.pose.bones['piston_'+label+'_'+side];track=pb.constraints.new('DAMPED_TRACK');track.name='Hydraulic aim';track.target=rig;track.subtarget='piston_anchor_'+('b' if label=='housing' else 'a')+'_'+side;track.track_axis='TRACK_Y'
    for label,limit in [('upper_leg',30),('middle_leg',35),('lower_leg',35),('foot',45)]:
        pb=rig.pose.bones[label+'_'+side];pb.rotation_mode='XYZ';pb.lock_rotation=(False,True,True)
        pb.lock_location=(True,True,True);pb.lock_scale=(True,True,True)
        stop=pb.constraints.new('LIMIT_ROTATION');stop.name='Mechanical hinge stops';stop.owner_space='LOCAL';stop.use_limit_x=True;stop.min_x=math.radians(-limit);stop.max_x=math.radians(limit);stop.use_limit_y=True;stop.use_limit_z=True
        pb.lock_ik_y=True;pb.lock_ik_z=True;pb.use_ik_limit_x=True;pb.ik_min_x=math.radians(-limit);pb.ik_max_x=math.radians(limit)
    ik=rig.pose.bones['lower_leg_'+side].constraints.new('IK');ik.name='Foot placement (optional)';ik.target=rig;ik.subtarget='foot_control_'+side;ik.chain_count=3;ik.use_stretch=False;ik.pole_target=rig;ik.pole_subtarget='knee_pole_'+side
    driver=ik.driver_add('influence').driver;var=driver.variables.new();var.name='blend';var.targets[0].id=rig;var.targets[0].data_path='["FootIK"]';driver.expression='blend'

# One group per piece: there are no blended weights and no triangles bridging
# adjacent moving parts. This preserves the shape of every metal panel.
for obj,bone_name in parts:
    assert len(obj.data.polygons)>0,obj.name
    obj.parent=rig;group=obj.vertex_groups.new(name=bone_name);group.add(list(range(len(obj.data.vertices))),1.0,'REPLACE')
    mod=obj.modifiers.new('Rigid mechanical binding','ARMATURE');mod.object=rig
    obj['RigidBone']=bone_name

# Export in centimetres with unit object/bone scales, matching the game's pipeline.
for obj,_ in parts:obj.data.transform(Matrix.Scale(100,4))
arm.transform(Matrix.Scale(100,4))
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01;scene.render.fps=30
scene.frame_start=1;scene.frame_end=121
for frame,amount in [(1,0),(31,1),(61,0),(91,-1),(121,0)]:
    for side,phase in [('l',1),('r',-1)]:
        for label,angle in [('upper_leg',10),('middle_leg',-18),('lower_leg',13),('foot',-5)]:
            pb=rig.pose.bones[label+'_'+side];pb.rotation_euler.x=math.radians(angle*amount*phase);pb.keyframe_insert('rotation_euler',frame=frame,group=pb.name)
action=rig.animation_data.action;action.name=NAME+'_JointCheck';action.use_fake_user=True
scene.frame_set(1);bpy.context.view_layer.update()
# Imported FBXs contain unused embedded images with obsolete Meshy paths.
# Purge only unused Blender datablocks, leaving the original source files intact.
bpy.data.orphans_purge(do_recursive=True)
bpy.data.use_autopack=False
for image in bpy.data.images:
    if image.source=='FILE':image.filepath=str(ASSET/'Source'/Path(image.filepath).name)
activate(rig)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active;space.clip_end=100000;space.shading.type='MATERIAL'
            space.region_3d.view_location=(0,0,90);space.region_3d.view_distance=330
            space.region_3d.view_rotation=Vector((-3,4,-1.5)).to_track_quat('-Z','Y');space.region_3d.view_perspective='PERSP'
bpy.ops.wm.save_as_mainfile(filepath=str(ASSET/(NAME+'.blend')))
bpy.ops.file.make_paths_relative();bpy.ops.wm.save_as_mainfile(filepath=str(ASSET/(NAME+'.blend')))

def select_rig():
    bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
    for obj,_ in parts:obj.select_set(True)
    bpy.context.view_layer.objects.active=rig
select_rig()
fbx=dict(use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,axis_forward='-Z',axis_up='Y',use_mesh_modifiers=True,mesh_smooth_type='FACE',path_mode='STRIP',use_armature_deform_only=True)
bpy.ops.export_scene.fbx(filepath=str(EXPORT/(NAME+'.fbx')),bake_anim=False,**fbx)
bpy.ops.export_scene.fbx(filepath=str(EXPORT/(NAME+'_JointCheck.fbx')),bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,bake_anim_simplify_factor=0,bake_anim_step=1,**fbx)
# Individual rigid part exports use bone-local pivots for sockets, replacement
# parts and future break-apart effects. They do not contain skinning or actions.
part_dir=EXPORT/'Parts';part_dir.mkdir(exist_ok=True)
for obj,bone_name in parts:
    data=obj.data.copy();data.transform(arm.bones[bone_name].matrix_local.inverted())
    temp=bpy.data.objects.new(obj.name+'_Export',data);bpy.context.collection.objects.link(temp);activate(temp)
    bpy.ops.export_scene.fbx(filepath=str(part_dir/(obj.name+'.fbx')),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Z',axis_up='Y',mesh_smooth_type='FACE',path_mode='STRIP')
    bpy.data.objects.remove(temp,do_unlink=True);bpy.data.meshes.remove(data)
manifest=dict(name=NAME,rig_type='three-link mechanical legs',parts=[dict(name=o.name,bone=b,vertices=len(o.data.vertices),triangles=sum(len(p.vertices)-2 for p in o.data.polygons)) for o,b in parts],bones=[b.name for b in arm.bones if b.use_deform],closed_cut_faces=cap_count,height_cm=180,preview_action=action.name,has_hydraulic_constraints='piston' in CFG)
(ASSET/'RigManifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('ROBOT_RIG_READY',NAME,len(parts),'rigid objects',flush=True)
