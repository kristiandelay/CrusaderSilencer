"""Check archive provenance, normalized filenames and prepared exports for the delivery."""
import hashlib,json,re,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
rows=json.loads((root/'resources/Level3Sources.json').read_text())
out=root/'Artifacts/Level3';out.mkdir(exist_ok=True)
checked=[]
for row in rows:
    name=row['name'];archive=root/row['archive'];folder=root/'Art/Environment/Level3'/name
    source=folder/'Source';manifest=json.loads((source/'SourceManifest.json').read_text())
    assert archive.name==name+'.zip' and re.fullmatch(r'[A-Za-z][A-Za-z0-9]*',name)
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==row['sha256']==manifest['archive_sha256']
    assert manifest['original_archive_name'].startswith('Meshy_AI_')
    assert {f['file'] for f in manifest['files']}=={name+'.fbx'}|{name+'_'+kind+'.png' for kind in ['BaseColor','Normal','Metallic','Roughness']}
    with zipfile.ZipFile(archive) as package:
        for member in manifest['files']:
            data=(source/member['file']).read_bytes()
            assert hashlib.sha256(data).hexdigest()==member['sha256']
            assert data==package.read(member['original'])
    assert (folder/'Export'/(name+'.fbx')).is_file()
    assert (folder/(name+'.blend')).is_file()
    checked.append(name)
assert len(checked)==len(set(checked))==74
assert not list((root/'mockups/Environment/Level3').rglob('Meshy_AI_*.zip'))
(out/'source-validation.json').write_text(json.dumps(dict(passed=True,models=checked,archives_unchanged=True),indent=2)+'\n')
print('LEVEL3_SOURCE_VALIDATION',len(checked),'archives, normalized source sets, Blender files and FBX exports')
