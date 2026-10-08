"""Blender: consistent centimetres, floor pivots, named materials and UE exports."""
import bpy
import json,sys
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'Artifacts/Environment'
OUT.mkdir(exist_ok=True,parents=True)
records=json.loads((ROOT/'resources/EnvironmentModels.json').read_text())
selected=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
if selected:records=[r for r in records if r['name'] in selected or r['category'] in selected]
reports=json.loads((OUT/'models.json').read_text()) if (OUT/'models.json').exists() else []
for entry in records:
    name=entry['name'];folder=ROOT/'Art/Environment'/entry['category']/name
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(folder/'Source'/(name+'.fbx')))
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    assert meshes,name
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:o.select_set(True)
    bpy.context.view_layer.objects.active=meshes[0]
    bpy.ops.object.join();mesh=bpy.context.object
    mesh.name=name;mesh.data.name=name
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    lo=Vector([min(v.co[i] for v in mesh.data.vertices) for i in range(3)])
    hi=Vector([max(v.co[i] for v in mesh.data.vertices) for i in range(3)])
    scale=entry['longest_dimension_cm']/max(hi-lo)
    pivot=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
    for v in mesh.data.vertices:v.co=(v.co-pivot)*scale
    mat=bpy.data.materials.new('M_'+name);mat.use_nodes=True
    mesh.data.materials.clear();mesh.data.materials.append(mat)
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    for kind,input_name in [('BaseColor','Base Color'),('Metallic','Metallic'),('Roughness','Roughness'),('Normal','Normal')]:
        tex=mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image=bpy.data.images.load(str(folder/'Source'/(name+'_'+kind+'.png')))
        tex.image.name=name+'_'+kind
        if kind!='BaseColor':tex.image.colorspace_settings.name='Non-Color'
        if kind=='Normal':
            normal=mat.node_tree.nodes.new('ShaderNodeNormalMap')
            mat.node_tree.links.new(tex.outputs['Color'],normal.inputs['Color'])
            mat.node_tree.links.new(normal.outputs['Normal'],bsdf.inputs[input_name])
        else:mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs[input_name])
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01
    export=folder/'Export';export.mkdir(exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=str(export/(name+'.fbx')),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',bake_anim=False,add_leaf_bones=False,path_mode='STRIP')
    for image in bpy.data.images:
        if image.source=='FILE':image.filepath='//Source/'+Path(image.filepath).name
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/(name+'.blend')))
    # Render the actual mesh for inspection, scaled to metres for studio lights.
    mesh.scale=(.01,)*3
    bpy.context.view_layer.update()
    dims=mesh.dimensions.copy();center=Vector((0,0,dims.z/2));width=max(dims)*1.6
    scene.render.engine='CYCLES';scene.cycles.samples=4
    scene.world=bpy.data.worlds.new('Studio');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.3,.3,.3,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7
    for offset,power in [((2,-3,4),900),((-3,-1,2),500)]:
        bpy.ops.object.light_add(type='AREA',location=center+Vector(offset)*max(dims))
        lamp=bpy.context.object;lamp.data.energy=power*max(dims)**2;lamp.data.size=max(dims)*2
        lamp.rotation_euler=(center-lamp.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add(location=center+Vector((1,-1.7,.8))*max(dims)*2)
    camera=bpy.context.object;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=width;scene.camera=camera
    scene.render.resolution_x=384;scene.render.resolution_y=384;scene.render.resolution_percentage=100
    scene.render.filepath=str(OUT/(name+'.png'))
    bpy.ops.render.render(write_still=True)
    mesh.data.calc_loop_triangles()
    reports=[r for r in reports if r['name']!=name]+[dict(name=name,dimensions_cm=[round(v*100,2) for v in dims],triangles=len(mesh.data.loop_triangles),vertices=len(mesh.data.vertices))]
    (OUT/'models.json').write_text(json.dumps(reports,indent=2))
    print('ENVIRONMENT_READY',name,flush=True)
