"""Blender source profiles for fitting the guard/NPC deformation rigs."""
import bpy
import json
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'Artifacts/NPCCharacters'
reports={}
for name in ['ObsidianSentinel','RegalCommander','TheSteadfastOfficer','UrbanTrailblazer']:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    folder=ROOT/'Art/Characters'/name/'Source'
    bpy.ops.import_scene.fbx(filepath=str(folder/(name+'.fbx')))
    mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
    bpy.context.view_layer.objects.active=mesh
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    low=Vector(tuple(min(v.co[i] for v in mesh.data.vertices) for i in range(3)))
    high=Vector(tuple(max(v.co[i] for v in mesh.data.vertices) for i in range(3)))
    reports[name]={'min':list(low),'max':list(high),'vertices':len(mesh.data.vertices),'triangles':len(mesh.data.polygons)}
    mat=bpy.data.materials.new(name);mat.use_nodes=True
    mesh.data.materials.clear();mesh.data.materials.append(mat)
    bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.6
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(folder/(name+'_BaseColor.png')))
    mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=12
    scene.world=bpy.data.worlds.new('Studio');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.5,.5,.5,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8
    for loc,energy in [((1,-3,3),600),((-2,-1,1),300)]:
        bpy.ops.object.light_add(type='AREA',location=loc)
        lamp=bpy.context.object;lamp.data.energy=energy;lamp.data.size=3
        lamp.rotation_euler=(Vector((0,0,1))-lamp.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add();camera=bpy.context.object;camera.data.type='ORTHO';scene.camera=camera
    scene.render.resolution_x=1200;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
    hand=(.79,.02,1.35) if name=='UrbanTrailblazer' else (.65,.0,1.09)
    for label,center,offset,width in [
                                      ('HandFront',hand,(0,-4,0),.32),
                                      ('HandTop',hand,(0,0,4),.32)]:
        camera.location=Vector(center)+Vector(offset)
        camera.rotation_euler=(Vector(center)-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.ortho_scale=width
        scene.render.filepath=str(OUT/(name+'_'+label+'.png'))
        bpy.ops.render.render(write_still=True)
    print('INSPECTED',name,json.dumps(reports[name]),flush=True)
(OUT/'source-inspection.json').write_text(json.dumps(reports,indent=2))
