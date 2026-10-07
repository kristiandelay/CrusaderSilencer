"""Export the existing weapon bind rigs before preparing their replacements."""
from pathlib import Path
import unreal as u

assert not u.EditorLevelLibrary.get_pie_worlds(False)
out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/WeaponReplacements'
out.mkdir(parents=True,exist_ok=True)
for kind,path in [('Pistol','/Game/Weapons/Pistol/Mesh/SK_Pistol'),
                  ('Shotgun','/Game/Weapons/Shotgun/Mesh/SKM_Shotgun')]:
    task=u.AssetExportTask()
    task.object=u.load_asset(path);task.filename=str(out/(kind+'.fbx'))
    task.automated=True;task.prompt=False;task.replace_identical=True
    task.exporter=u.SkeletalMeshExporterFBX();task.options=u.FbxExportOption()
    task.options.set_editor_property('level_of_detail',False)
    assert u.Exporter.run_asset_export_task(task)
