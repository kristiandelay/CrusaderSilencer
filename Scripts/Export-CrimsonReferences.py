"""Export the project's Lyra rifle bind rig for the Blender preparation step."""
from pathlib import Path
import unreal as u

assert not u.EditorLevelLibrary.get_pie_worlds(False)
out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/CrimsonSentinel'
out.mkdir(parents=True,exist_ok=True)
task=u.AssetExportTask()
task.object=u.load_asset('/Game/Weapons/Rifle/Mesh/SK_Rifle')
task.filename=str(out/'Rifle.fbx')
task.automated=True;task.prompt=False;task.replace_identical=True
task.exporter=u.SkeletalMeshExporterFBX()
task.options=u.FbxExportOption()
task.options.set_editor_property('level_of_detail',False)
assert u.Exporter.run_asset_export_task(task)
print('Exported rifle bind rig:',task.filename)
