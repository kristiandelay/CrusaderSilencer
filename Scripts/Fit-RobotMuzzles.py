"""Blender: fit barrel depths to source geometry using inspected front-view centres.

Uses the orthographic views/cache from Inspect-RobotSources.py. No mesh edits.
Unreal's imported model coordinates are X, -Y, Z in centimetres.
"""
import bpy,json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
# Pixel centres of actual gun openings in the 900px orthographic source views.
centres={
    'IronSentinel':[(240,270),(660,258)],
    'SentinelWalker':[(434,237),(469,237)],
    'APP5200IndustrialM':[(295,264),(605,264),(297,301),(603,301)],
    'IroncladTitan':[(252,277),(648,277)],
    'IroncladVanguard':[(287,273),(291,350)],
    'IroncladSentinel':[(270,250),(630,250)]}
path=root/'resources/RobotGameplay.json';config=json.loads(path.read_text());report=[]
for row in config['robots']:
    name=row['name'];source=json.loads((root/'Artifacts/Robots'/f'{name}_Source.json').read_text())
    low,high=source['minimum'],source['maximum'];extent=max(b-a for a,b in zip(low,high));pixel_scale=extent*1.15/900
    bpy.ops.wm.open_mainfile(filepath=str(root/'Artifacts/Robots'/f'{name}_Working.blend'))
    mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH');points=[]
    for px,pz in centres[name]:
        x=(low[0]+high[0])*.5+(px-450)*pixel_scale
        z=(low[2]+high[2])*.5+(450-pz)*pixel_scale
        candidates=[v.co.y for v in mesh.data.vertices if (v.co.x-x)**2+(v.co.z-z)**2<.055**2]
        assert candidates,(name,px,pz)
        y=min(candidates)-.008 # just ahead of the metal rim
        points.append([round(x*100,2),round(-y*100,2),round(z*100,2)])
    row['muzzles']=points;report.append(dict(name=name,front_pixels=centres[name],muzzles=points))
path.write_text(json.dumps(config,indent=2)+'\n')
(root/'Artifacts/RobotGameplay/muzzle-fitting.json').write_text(json.dumps(report,indent=2)+'\n')
print('ROBOT_BARRELS_FITTED',json.dumps(report))
