"""Capture a real rifle shot in the traversal range at reduced playback speed."""
from pathlib import Path
import unreal as u

lc_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
lc_source=(lc_root/'Scripts/Capture-WeaponEffects.py').read_text().replace("/'Artifacts/WeaponFX'","/'Artifacts/LaserTracer'")
lc_source=lc_source.replace("cfx_image(world,'SurfaceRange',u.Vector(1700,-4350,1500),u.Vector(1200,-6440,70),78)","pass")
lc_source=lc_source.replace("cfx_image(world,'RifleMuzzle',muzzle+u.Vector(130,150,55),muzzle+u.Vector(0,-25,0),60)","cfx_image(world,'LaserTrace5',u.Vector(1550,-6340,600),u.Vector(370,-6310,170),70)")
lc_source=lc_source.replace("cfx_image(world,'MetalImpact',u.Vector(660,-6570,235),u.Vector(370,-6920,170),55)","pass")
exec(compile(lc_source,'Capture-WeaponEffects.py','exec'),globals())
