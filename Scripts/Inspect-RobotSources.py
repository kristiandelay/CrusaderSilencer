"""Render front/side robot source views and cache UV-preserving working geometry."""
import bpy,json,sys
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'Artifacts/Robots';OUT.mkdir(parents=True,exist_ok=True)
names=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [p.name for p in (ROOT/'Art/Robots').iterdir() if p.is_dir()]
for name in names:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source=ROOT/'Art/Robots'/name/'Source'
    bpy.ops.import_scene.fbx(filepath=str(source/(name+'.fbx')))
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:o.select_set(True)
    bpy.context.view_layer.objects.active=meshes[0]
    if len(meshes)>1:bpy.ops.object.join()
    mesh=bpy.context.object;mesh.name=name
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    low=Vector(tuple(min(v.co[i] for v in mesh.data.vertices) for i in range(3)))
    high=Vector(tuple(max(v.co[i] for v in mesh.data.vertices) for i in range(3)))
    report=dict(name=name,minimum=list(low),maximum=list(high),vertices=len(mesh.data.vertices),polygons=len(mesh.data.polygons),source_objects=len(meshes))
    # A working copy for fitting/cutting; the supplied source remains intact.
    d=mesh.modifiers.new('Working topology','DECIMATE');d.ratio=min(1,160000/len(mesh.data.polygons));d.use_collapse_triangulate=True
    bpy.ops.object.modifier_apply(modifier=d.name)
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.remove_doubles(threshold=.000002);bpy.ops.object.mode_set(mode='OBJECT')
    mat=bpy.data.materials.new(name);mat.use_nodes=True
    mesh.data.materials.clear();mesh.data.materials.append(mat)
    bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.55
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(source/(name+'_BaseColor.png')))
    mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(name+'_Working.blend')))
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=8
    # Small inspection renders are fast on the CPU and don't compete with UE's GPU.
    scene.world=bpy.data.worlds.new('Studio');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.32,.36,.42,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8
    center=(low+high)*.5;size=max(high-low)
    for offset,energy in [((1,-2,2),600),((-2,-1,1),450),((1,2,2),800)]:
        bpy.ops.object.light_add(type='AREA',location=center+Vector(offset)*size)
        lamp=bpy.context.object;lamp.data.energy=energy*size*size;lamp.data.size=size*2
        lamp.rotation_euler=(center-lamp.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add();camera=bpy.context.object;camera.data.type='ORTHO';camera.data.ortho_scale=size*1.15;scene.camera=camera
    scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    for label,offset in [('Front',(0,-4,0)),('Side',(4,0,0)),('Perspective',(3,-4,2))]:
        camera.location=center+Vector(offset)*size;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(OUT/(name+'_'+label+'.png'));bpy.ops.render.render(write_still=True)
    (OUT/(name+'_Source.json')).write_text(json.dumps(report,indent=2))
    print('ROBOT_INSPECTED',json.dumps(report),flush=True)
