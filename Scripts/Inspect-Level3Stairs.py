"""Blender: record stair tread profile along its centre for exact placement."""
import bpy,json
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(root/'Art/Environment/Level3/IndustrialStaircase/IndustrialStaircase.blend'))
obj=bpy.data.objects['IndustrialStaircase']
deps=bpy.context.evaluated_depsgraph_get()
hits=[]
for y in range(-550,551,25):
    hit,location,normal,index=obj.ray_cast(Vector((0,y,1000)),Vector((0,0,-1)))
    if hit:hits.append(dict(y=y,z=round(location.z,3),normal=list(normal)))
(root/'Artifacts/Environment/Level3StairProfile.json').write_text(json.dumps(hits,indent=2))
print('STAIR_PROFILE',[(r['y'],r['z']) for r in hits])
