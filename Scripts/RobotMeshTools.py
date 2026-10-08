"""Preserve every sculpt triangle while separating rigid mechanical assemblies.

Face partitioning avoids unreliable Boolean volume classification on fused Meshy
surfaces. Cut borders get new interior caps; no original exterior faces are
reconstructed. Only the explicitly replaced hydraulic spans are removed.
"""
import bpy,bmesh,math
from collections import defaultdict
from mathutils import Vector

def modularize(source,name,config,inner):
    groups=defaultdict(list);removed=[]
    leg_top=max(config['leg_top'],config['joints'][0][2]+config['radii'][0]*1.5+.005)
    pelvis_bottom=config['pelvis_bottom']
    normals=[Vector(n) for n in config.get('cut_normals',[(0,0,1)]*3)]
    offsets=config.get('cut_offsets',[0,0,config['radii'][3]*.65])
    # Insert exact border edges before partitioning, so seams do not follow the
    # jagged edges of the decimated sculpt triangles. Local convex axle cuts
    # avoid any assumptions about the source's inside/outside volume.
    bm=bmesh.new();bm.from_mesh(source.data)
    planes=[((0,0,leg_top),(0,0,1)),((0,0,pelvis_bottom),(0,0,1)),((0,0,0),(1,0,0)),((config['inner_hip'],0,0),(1,0,0)),((-config['inner_hip'],0,0),(1,0,0))]
    planes += [(Vector(config['joints'][i+1])+Vector((0,0,offsets[i])),normals[i]) for i in range(3)]
    for point,normal in planes:
        bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.0000001,plane_co=point,plane_no=normal,clear_inner=False,clear_outer=False)
    circle_normals=[Vector((0,math.cos(i*math.tau/24),math.sin(i*math.tau/24))) for i in range(24)]
    for pivot,radius in zip(config['joints'],config['radii']):
        pivot=Vector(pivot);radius*=1.5
        region={f for f in bm.faces if (f.calc_center_median().y-pivot.y)**2+(f.calc_center_median().z-pivot.z)**2<(radius*1.8)**2}
        for normal in circle_normals:
            region={f for f in region if f.is_valid}
            geom=set(region)
            for f in region:geom.update(f.verts);geom.update(f.edges)
            cut=bmesh.ops.bisect_plane(bm,geom=list(geom),dist=.0000001,plane_co=pivot+normal*radius,plane_no=normal,clear_inner=False,clear_outer=False)
            for edge in cut['geom_cut']:
                if isinstance(edge,bmesh.types.BMEdge):region.update(edge.link_faces)
    bm.to_mesh(source.data);bm.free();source.data.update()
    for face in source.data.polygons:
        point=face.center
        if point.z>=leg_top or (point.z>=pelvis_bottom and abs(point.x)<=config['inner_hip']):
            groups[('Chassis','chassis')].append(face.index);continue
        side='l' if point.x>=0 else 'r';sign=1 if side=='l' else -1
        if 'piston' in config:
            a=Vector(config['piston']['a']);b=Vector(config['piston']['b']);a.x*=sign;b.x*=sign
            axis=b-a;t=(point-a).dot(axis)/axis.length_squared
            # A narrow span, excluding the original hinge mounts at both ends.
            if .07<t<.93 and (point-(a+t*axis)).length<config['piston']['clearance']:
                removed.append(face.index);continue
        joints=[Vector((p[0]*sign,p[1],p[2])) for p in config['joints']]
        near=[max(n.dot(point-j) for n in circle_normals)/(r*1.5) for j,r in zip(joints,config['radii'])]
        index=min(range(4),key=lambda i:near[i])
        if near[index]<1:
            bone=['upper_leg','middle_leg','lower_leg','foot'][index]+'_'+side
            groups[('JointHousing_'+str(index)+'_'+side,bone)].append(face.index);continue
        index=3
        for i in range(3):
            if (point-joints[i+1]-Vector((0,0,offsets[i]))).dot(normals[i])>=0:index=i;break
        bone=['upper_leg','middle_leg','lower_leg','foot'][index]+'_'+side
        groups[(bone,bone)].append(face.index)
    assert sum(map(len,groups.values()))+len(removed)==len(source.data.polygons)
    assert len(removed)<len(source.data.polygons)*.03,'Hydraulic removal region is too broad'
    parts=[];caps=0
    for (label,bone_name),indices in groups.items():
        keep=set(indices);bm=bmesh.new();bm.from_mesh(source.data)
        bm.faces.ensure_lookup_table();bm.faces.index_update()
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index not in keep],context='FACES')
        loose=[v for v in bm.verts if not v.link_faces]
        if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
        boundary=[e for e in bm.edges if e.is_boundary]
        caps+=len(boundary)
        data=bpy.data.meshes.new(name+'_'+label);bm.to_mesh(data);bm.free()
        for mat in source.data.materials:data.materials.append(mat)
        obj=bpy.data.objects.new(name+'_'+label,data);bpy.context.collection.objects.link(obj)
        if boundary:
            # Give the open sculpt patch a closed metal shell. Filling a long,
            # curved border with one planar ngon makes spikes across the part.
            bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
            shell=obj.modifiers.new('Closed metal wall and cut rim','SOLIDIFY');shell.thickness=.002; shell.offset=-1; shell.use_rim=True
            shell.material_offset=1;shell.material_offset_rim=1
            bpy.ops.object.modifier_apply(modifier=shell.name)
        obj['OriginalFaces']=len(indices);parts.append((obj,bone_name))
        if bone_name=='chassis':assert min(v.co.z for v in obj.data.vertices)>pelvis_bottom-.01,'A low leg/foot detail was left attached to the chassis'
    for side in ['l','r']:
        assert all(any(b==label+'_'+side for _,b in parts) for label in ['upper_leg','middle_leg','lower_leg','foot'])
    print('MECHANICAL_PARTITION',name,'original faces',len(source.data.polygons),'replaced hydraulic faces',len(removed),'closed borders',caps,flush=True)
    bpy.data.objects.remove(source,do_unlink=True)
    return parts,caps
