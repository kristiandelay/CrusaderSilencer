"""Run the existing mapped-input GASP regression while carrying a rifle."""
from pathlib import Path
import unreal as u

rtr_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
rtr_world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
rtr_pawn=u.GameplayStatics.get_player_pawn(rtr_world,0)
rtr_pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(rtr_world,u.BaselineWeaponPickup) if 'Rifle' in a.item_definition.get_name())
rtr_pos=rtr_pickup.get_actor_location()
rtr_pawn.set_actor_location(rtr_pos+u.Vector(-110,0,94-rtr_pos.z),False,True)
rtr_pawn.baseline_equipment.server_pickup(rtr_pickup)
source=(rtr_root/'Scripts/Test-TraversalGym.py').read_text().replace("'Artifacts/GymTests'","'Artifacts/Roll/Traversal'")
exec(compile(source,'Test-TraversalGym.py','exec'),globals())
rtr_original_finish=gym_finish
def gym_finish(error=None):
    rtr_original_finish(error)
    gym_test.update(finished=True,error=error)
