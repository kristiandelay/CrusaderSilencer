"""Mirror the user-positioned front-left post and fit its beacons and rail wraps."""
import json
from pathlib import Path
import unreal as u

assert not u.EditorLevelLibrary.get_pie_worlds(False)
fa_actors={a.get_actor_label():a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()}
fa_prefix='CR_Facility_'
fa_platform=fa_actors[fa_prefix+'ContainmentPlatform'].get_actor_bounds(False)[0]
fa_reference=fa_actors[fa_prefix+'ContainmentPost_0']
fa_centre=fa_reference.get_actor_bounds(False)[0]
fa_dx=abs(fa_centre.x-fa_platform.x);fa_dy=abs(fa_centre.y-fa_platform.y)
fa_beacon_reference=fa_actors[fa_prefix+'ContainmentBeacon_0']
fa_beacon_offset=fa_beacon_reference.get_actor_bounds(False)[0]-fa_centre
fa_beacon_scale=fa_beacon_reference.get_actor_scale3d()
fa_beacon_rotation=fa_beacon_reference.get_actor_rotation()

def fa_move_centre(actor,centre):
    actor.set_actor_location(actor.get_actor_location()+centre-actor.get_actor_bounds(False)[0],False,True)

for index,(sx,sy) in enumerate([(-1,-1),(1,-1),(-1,1),(1,1)]):
    post=fa_actors[fa_prefix+'ContainmentPost_'+str(index)]
    centre=u.Vector(fa_platform.x+sx*fa_dx,fa_platform.y+sy*fa_dy,fa_centre.z)
    if index:
        post.set_actor_rotation(fa_reference.get_actor_rotation(),False)
        post.set_actor_scale3d(fa_reference.get_actor_scale3d())
        fa_move_centre(post,centre)
    beacon=fa_actors[fa_prefix+'ContainmentBeacon_'+str(index)]
    beacon.set_actor_scale3d(fa_beacon_scale)
    beacon.set_actor_rotation(fa_beacon_rotation,False)
    fa_move_centre(beacon,centre+fa_beacon_offset)
    beacon.attach_to_actor(post,'',u.AttachmentRule.KEEP_WORLD,u.AttachmentRule.KEEP_WORLD,u.AttachmentRule.KEEP_WORLD,False)

for level in range(2):
    for side,x,y,length in [('Rear',fa_platform.x,fa_platform.y+fa_dy,2*fa_dx),('Left',fa_platform.x-fa_dx,fa_platform.y,2*fa_dy),('Right',fa_platform.x+fa_dx,fa_platform.y,2*fa_dy)]:
        rail=fa_actors[fa_prefix+'Rail'+side+'_'+str(level)]
        z=rail.get_actor_bounds(False)[0].z
        bounds=rail.static_mesh_component.static_mesh.get_bounding_box()
        scale=rail.get_actor_scale3d();scale.x=length/(bounds.max.x-bounds.min.x)
        rail.set_actor_scale3d(scale);fa_move_centre(rail,u.Vector(x,y,z))

# Record actual user placements, including the lowered hatch, without rebuilding
# the rest of the level or resetting the editor's viewport/selection.
fa_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
fa_path=fa_root/'resources/FacilityMockup.json'
fa_manifest=json.loads(fa_path.read_text())
for record in fa_manifest['mesh_actors']:
    centre=fa_actors[record['actor']].get_actor_bounds(False)[0]-u.Vector(*fa_manifest['origin'])
    record['center']=[round(centre.x,5),round(centre.y,5),round(centre.z,5)]
fa_path.write_text(json.dumps(fa_manifest,indent=2)+'\n')
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
print('CONTAINMENT_ALIGNED',dict(post_half_width=fa_dx,post_half_depth=fa_dy,reference=[fa_centre.x,fa_centre.y,fa_centre.z]))
