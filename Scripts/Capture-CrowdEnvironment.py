"""Capture the actual authored district, imported models and surface pads in PIE."""
from pathlib import Path
import unreal as u
ce_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
ce_world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
exec((ce_root/'Scripts/Capture-WeaponEffects.py').read_text().split('def cfx_tick')[0],globals())
capture_folder=ce_root/'Artifacts/Environment'
cfx_image(ce_world,'CrowdDistrict',u.Vector(11900,-3700,3900),u.Vector(12400,1400,0),82)
cfx_image(ce_world,'FootstepPads',u.Vector(7600,-2400,3500),u.Vector(7800,-6350,0),85)
cfx_image(ce_world,'EnvironmentGallery',u.Vector(7200,-7600,3200),u.Vector(7100,-11300,0),88)
for role in ['Guard','Civilian']:
    p=next(a for a in u.GameplayStatics.get_all_actors_of_class(ce_world,u.CRTraversalCharacter) if a.crowd_agent.enabled and a.crowd_agent.guard==(role=='Guard'))
    center=p.get_actor_location()+u.Vector(0,0,25)
    cfx_image(ce_world,role,center+p.get_actor_forward_vector()*380+p.get_actor_right_vector()*240+u.Vector(0,0,120),center,48)
print('Captured district, pads, gallery, guard and civilian')
