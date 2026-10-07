"""Render source weapon profiles and record dimensions/legacy rig transforms."""
import bpy
import json
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'Artifacts/WeaponReplacements'
reports={}
for name,path in [
    ('FuturisticPistol',ROOT/'Art/Weapons/FuturisticPistol/Source/FuturisticPistol.fbx'),
    ('TitanBreaker',ROOT/'Art/Weapons/TitanBreaker/Source/TitanBreaker.fbx'),
    ('Pistol',OUT/'Pistol.fbx'),('Shotgun',OUT/'Shotgun.fbx')]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path))
    objects=list(bpy.context.scene.objects)
    meshes=[o for o in objects if o.type=='MESH']
    points=[o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    low=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    center=(low+high)*.5
    report={'min':list(low),'max':list(high),'dimensions':list(high-low),
            'vertices':sum(len(o.data.vertices) for o in meshes),
            'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)}
    for rig in [o for o in objects if o.type=='ARMATURE']:
        report['rig']={'matrix':list(map(list,rig.matrix_world)),
                       'bones':{b.name:{'head':list(b.head_local),'tail':list(b.tail_local),
                                        'matrix':list(map(list,b.matrix_local))} for b in rig.data.bones}}
    if name in ['FuturisticPistol','TitanBreaker']:
        for mesh in meshes:
            mat=bpy.data.materials.new(name);mat.use_nodes=True
            mesh.data.materials.clear();mesh.data.materials.append(mat)
            bsdf=mat.node_tree.nodes.get('Principled BSDF')
            tex=mat.node_tree.nodes.new('ShaderNodeTexImage')
            tex.image=bpy.data.images.load(str(path.parent/(name+'_BaseColor.png')))
            mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
            bsdf.inputs['Roughness'].default_value=.65
    scene=bpy.context.scene
    scene.render.engine='CYCLES';scene.cycles.samples=16
    scene.world=bpy.data.worlds.new('Studio');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.6,.6,.6,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8
    size=max(high-low)
    bpy.ops.object.camera_add(location=center+Vector((0,-size*2,0)))
    camera=bpy.context.object;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=max(high.x-low.x,(high.z-low.z)*1.6)*1.12
    scene.camera=camera
    for delta,energy in [((0,-1,1.5),700),((1,1,.7),450)]:
        bpy.ops.object.light_add(type='AREA',location=center+Vector(delta)*size)
        light=bpy.context.object;light.data.energy=energy*size*size;light.data.shape='DISK';light.data.size=size
        light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
    scene.render.resolution_x=1600;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
    scene.render.filepath=str(OUT/(name+'_Source.png'))
    report['render']={'center':list(center),'width':camera.data.ortho_scale,'height':camera.data.ortho_scale/1.6}
    reports[name]=report
    bpy.ops.render.render(write_still=True)
    print(name,json.dumps(report),flush=True)
(OUT/'source-inspection.json').write_text(json.dumps(reports,indent=2))
