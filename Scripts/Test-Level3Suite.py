"""Run the facility walkthrough with temporary PIE settings and restore preferences."""
from pathlib import Path
import unreal as u
ls_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
(ls_root/'Artifacts/Level3').mkdir(exist_ok=True)
exec(compile((ls_root/'Scripts/Test-RollNetworkSuite.py').read_text().replace('Artifacts/Roll/network-suite.json','Artifacts/Level3/suite.json'),'Test-RollNetworkSuite.py','exec'),globals())
addition_steps=[('Test-Level3Facility.py','lt_test','Level3/walkthrough.json','PIE_Standalone',1)]
addition_test['deadline']=time.monotonic()+850
ls_original_tick=addition_tick
u.unregister_slate_post_tick_callback(addition_test['handle'])
def ls_tick(delta):
    if addition_test['phase']=='ready':
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if worlds and u.NavigationSystemV1.is_navigation_being_built_or_locked(worlds[0]):return
    ls_original_tick(delta)
addition_test['handle']=u.register_slate_post_tick_callback(ls_tick)
