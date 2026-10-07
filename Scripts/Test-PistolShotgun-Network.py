"""Verify both replacement models and shoulder presentation in two-player PIE."""
from pathlib import Path
import traceback
import unreal as u

weapon_net_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
weapon_net_source=(weapon_net_root/'Scripts/Test-VisualOverrides-Network.py').read_text()
assert "[(host,'Pistol'),(server_client,'Rifle')]" in weapon_net_source
weapon_net_source=weapon_net_source.replace("[(host,'Pistol'),(server_client,'Rifle')]","[(host,'Pistol'),(server_client,'Shotgun')]")
exec(compile(weapon_net_source,'Test-VisualOverrides-Network.py','exec'),globals())
visual_net['index']=6
visual_net_out=weapon_net_root/'Artifacts/WeaponReplacements/network-validation.json'
weapon_net_original_finish=vn_finish

def weapon_net_finish(error=None):
    if error is None:
        try:
            for role,pawn in enumerate(vn_context()):
                expected='FuturisticPistol' if role in [0,3] else 'TitanBreaker'
                weapon=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_spawned_actors()[0]
                mesh=weapon.get_component_by_class(u.SkeletalMeshComponent)
                assert mesh.get_editor_property('skeletal_mesh_asset').get_name()==expected
                assert mesh.get_material(0).get_name()=='M_'+expected
                assert mesh.get_anim_instance()
                visual_net['results'].append({'case':'replicated_model_material_animation','role':role,'weapon':expected})
        except Exception:error=traceback.format_exc()
    weapon_net_original_finish(error)

vn_finish=weapon_net_finish

visual_net['last_index']=7
