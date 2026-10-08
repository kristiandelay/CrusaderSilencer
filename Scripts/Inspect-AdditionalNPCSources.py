"""Blender: inspect new body/hand landmarks and cache reduced source geometry."""
import bpy,json,sys
from pathlib import Path
from mathutils import Vector
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
names=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [r['name'] for r in json.loads((ROOT/'resources/NPCAdditions.json').read_text())]
for name in names:
    folder=ROOT/'Artifacts/NPCCharacters'/name;folder.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(ROOT/'Art/Characters'/name/'Source'/(name+'.fbx')))
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:o.select_set(True)
    bpy.context.view_layer.objects.active=meshes[0]
    if len(meshes)>1:bpy.ops.object.join()
    mesh=bpy.context.object;bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    original=len(mesh.data.polygons)
    modifier=mesh.modifiers.new('Game topology','DECIMATE');modifier.ratio=min(1,85000/original);modifier.use_collapse_triangulate=True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.remove_doubles(threshold=.00001);bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'Working.blend'))
    coords=np.empty(len(mesh.data.vertices)*3,dtype=np.float32);mesh.data.vertices.foreach_get('co',coords);coords=coords.reshape(-1,3)
    low,high=coords.min(axis=0),coords.max(axis=0)
    hand=coords[(coords[:,0]>high[0]-.16)&(coords[:,2]>.9)]
    center=np.median(hand,axis=0);center[0]=high[0]-.075
    slices=[]
    for x in np.arange(.2,float(high[0]),.035):
        points=coords[(abs(coords[:,0]-x)<.015)&(coords[:,2]>.9)]
        if len(points)>5:slices.append(dict(x=round(float(x),3),median=np.median(points,axis=0).tolist(),low=points.min(axis=0).tolist(),high=points.max(axis=0).tolist()))
    report=dict(name=name,source_triangles=original,minimum=low.tolist(),maximum=high.tolist(),hand_center=center.tolist(),hand_width=.34,slices=slices)
    (folder/'source-inspection.json').write_text(json.dumps(report,indent=2)+'\n')
    mat=bpy.data.materials.new(name);mat.use_nodes=True;mesh.data.materials.clear();mesh.data.materials.append(mat)
    bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.65
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ROOT/'Art/Characters'/name/'Source'/(name+'_BaseColor.png')))
    mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=8
    scene.world=bpy.data.worlds.new('Studio');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8
    for loc,energy in [((1,-3,3),600),((-2,-1,1),300)]:
        bpy.ops.object.light_add(type='AREA',location=loc);lamp=bpy.context.object;lamp.data.energy=energy;lamp.data.size=3
        lamp.rotation_euler=(Vector((0,0,1))-lamp.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add();camera=bpy.context.object;camera.data.type='ORTHO';scene.camera=camera
    scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
    for label,target,offset,width in [('BodyFront',(0,0,.9),(0,-4,0),2.07),('HandFront',center,(0,-4,0),.34),('HandTop',center,(0,0,4),.34)]:
        target=Vector(target);camera.location=target+Vector(offset);camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=width
        scene.render.filepath=str(folder/(label+'.png'));bpy.ops.render.render(write_still=True)
    print('CHARACTER_INSPECTED',name,flush=True)
