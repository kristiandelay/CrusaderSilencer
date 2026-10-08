"""Check each added widget entry on host/client and all new replicated residents."""
from pathlib import Path
import unreal as u

an_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
exec(compile((an_root/'Scripts/Test-VisualOverrides-Network.py').read_text(),'Test-VisualOverrides-Network.py','exec'),globals())
visual_net['index']=11
visual_net_out=an_root/'Artifacts/NPCCharacters/Additions/network.json'
an_original_finish=vn_finish

def vn_finish(error=None):
    if error is None:
        try:
            groups=[]
            for w in u.EditorLevelLibrary.get_pie_worlds(False):
                rows={}
                residents=[p for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if p.get_actor_label().startswith('CR_ControlCrowd_')]
                assert len(residents)==10 and all(p.crowd_agent.initialized for p in residents)
                for p in residents:
                    visual=p.selected_visual_override.child_actor
                    weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
                    assert visual and visual.get_class() in p.crowd_agent.visuals
                    assert bool(weapon)==p.crowd_agent.guard
                    rows[p.get_actor_label()]=dict(visual=visual.get_class().get_name(),guard=p.crowd_agent.guard,weapon=weapon.effects_profile.get_name() if weapon else None)
                groups.append(rows)
            assert len(groups)==2 and groups[0]==groups[1]
            visual_net['results'].append(dict(case='all_ten_replicated_residents',residents=groups[0]))
        except Exception:error=traceback.format_exc()
    an_original_finish(error)
