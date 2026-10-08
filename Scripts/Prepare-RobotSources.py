"""Normalize robot archives/FBXs/PBR names while retaining original hashes."""
import contextlib,io,json,runpy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
profiles=json.loads((ROOT/'resources/RobotRigs.json').read_text())
prepare=runpy.run_path(str(ROOT/'Scripts/Prepare-MeshySource.py'))['prepare']
catalog_path=ROOT/'mockups/AssetSources.json';catalog=json.loads(catalog_path.read_text())
for name,profile in profiles.items():
    target=ROOT/'mockups/Robots'/(name+'.zip')
    source=next((ROOT/'mockups/Robots').glob('*'+profile['id']+'*.zip'),target)
    previous=next((r for r in catalog if r['name']==name),{})
    original=previous.get('original_archive_name',source.name)
    if source!=target:
        assert source.resolve().parent==target.resolve().parent==(ROOT/'mockups/Robots').resolve()
        assert not target.exists(),target
        source.rename(target)
    folder=ROOT/'Art/Robots'/name/'Source'
    with contextlib.redirect_stdout(io.StringIO()):prepare(target,name,folder)
    manifest_path=folder/'SourceManifest.json';manifest=json.loads(manifest_path.read_text())
    manifest.update(original_archive_name=original,archive_path=target.relative_to(ROOT).as_posix())
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    record={**previous,**dict(name=name,category='Robots',archive=manifest['archive_path'],original_archive_name=original,sha256=manifest['archive_sha256'],imported=previous.get('imported',False))}
    catalog=[r for r in catalog if r['name']!=name]+[record]
    print('ROBOT_SOURCE_READY',name)
catalog_path.write_text(json.dumps(catalog,indent=2)+'\n')
