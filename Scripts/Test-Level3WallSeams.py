"""Probe visible wall joins with and without the kit-metal seam liners."""
import hashlib,json,math
from pathlib import Path
import unreal as u

ws_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
ws_world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
ws_bytes=(ws_root/'resources/Level3Facility.json').read_bytes()
ws_manifest=json.loads(ws_bytes);ws_origin=u.Vector(*ws_manifest['origin'])
ws_actors={a.get_actor_label():a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()}
ws_liners=[ws_actors[r['actor']] for r in ws_manifest['meshes'] if r['section']=='Wall Seam Liners']
assert ws_liners
for actor in ws_liners:
    c=actor.static_mesh_component
    assert c.is_visible() and not actor.get_editor_property('hidden')
    assert c.static_mesh.get_name()=='PlainWall'
    assert c.get_collision_response_to_channel(u.CollisionChannel.ECC_VISIBILITY)==u.CollisionResponseType.ECR_BLOCK
    assert c.get_material(0).get_editor_property('blend_mode')==u.BlendMode.BLEND_OPAQUE
ws_probes=set()
for wall in ws_manifest['wall_spans']:
    start,end=wall['start'],wall['end'];low,high=wall['bottom'],wall['top']
    boundaries=sorted({low,high,*([330] if low<330<high else [])})
    joints=[start+i*wall['width'] for i in range(wall['count']+1)]
    def add(p,z):
        if not start<=p<=end or not low<=z<=high:return
        # Sample inside the declared wall span; an adjacent doorway above a
        # floor-depth band must remain open, including its flush threshold.
        z=min(high-.5,max(low+.5,z))
        ws_probes.add((wall['axis'],wall['fixed'],round(p,3),round(wall['base']+z,3)))
    for p in joints:
        heights=[low+10+i*50 for i in range(math.ceil((high-low-20)/50))]
        for z in heights:
            for offset in [-4,0,4]:add(p+offset,z)
    for z in boundaries:
        positions=[start+10+i*50 for i in range(math.ceil((end-start-20)/50))]+joints
        for p in positions:
            for offset in [-4,0,4]:add(p,z+offset)

def ws_scan():
    misses=[]
    for axis,fixed,p,z in sorted(ws_probes):
        point=ws_origin+(u.Vector(p,fixed,z) if axis=='x' else u.Vector(fixed,p,z))
        normal=u.Vector(0,110,0) if axis=='x' else u.Vector(110,0,0)
        hit=u.SystemLibrary.line_trace_single(ws_world,point-normal,point+normal,
            u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],u.DrawDebugTrace.NONE)
        if not hit:misses.append([axis,fixed,p,z])
    return misses

try:
    for actor in ws_liners:
        actor.static_mesh_component.set_collision_response_to_channel(u.CollisionChannel.ECC_VISIBILITY,u.CollisionResponseType.ECR_IGNORE)
    ws_before=ws_scan()
finally:
    for actor in ws_liners:
        actor.static_mesh_component.set_collision_response_to_channel(u.CollisionChannel.ECC_VISIBILITY,u.CollisionResponseType.ECR_BLOCK)
ws_after=ws_scan()
ws_windows=[]
for row in ws_manifest['meshes']:
    if row['model']!='QuantumViewport':continue
    actor=ws_actors[row['actor']];center,_=actor.get_actor_bounds(False)
    normal=u.MathLibrary.transform_direction(actor.get_actor_transform(),u.Vector(0,110,0))
    hit=u.SystemLibrary.line_trace_single(ws_world,center-normal,center+normal,
        u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],u.DrawDebugTrace.NONE)
    assert not hit or hit.to_dict()['hit_actor'] not in ws_liners,('Window blocked by liner',row['actor'])
    ws_windows.append(row['actor'])
ws_result=dict(passed=not ws_after,manifest_sha256=hashlib.sha256(ws_bytes).hexdigest(),
    probes=len(ws_probes),wall_spans=len(ws_manifest['wall_spans']),liners=len(ws_liners),
    open_probes_without_liners=len(ws_before),open_probes_after=len(ws_after),
    preserved_window_centres=len(ws_windows),misses=ws_after)
(ws_root/'resources/Level3WallSeamValidation.json').write_text(json.dumps(ws_result,indent=2)+'\n')
print('LEVEL3_WALL_SEAMS',ws_result)
assert ws_result['passed'],'Wall seams remain open'
