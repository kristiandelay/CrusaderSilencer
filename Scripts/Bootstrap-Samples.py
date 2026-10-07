"""Restore the pristine local Lyra snapshot and stage GASP without path collisions."""
import hashlib
import json
import pathlib
import shutil
import subprocess
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
LYRA = pathlib.Path(r'C:\Development\Game\silencer3d')
GASP = pathlib.Path(r'C:\Development\Game\GameAnimationSample')
REVISION = 'b7b15cb48690fdcd782633a1abb432825aa128ef'
DEST = ROOT / 'src'
ARTIFACTS = ROOT / 'Artifacts'
ARTIFACTS.mkdir(exist_ok=True)
archive = ARTIFACTS / 'pristine-lyra.tar'
subprocess.run(['git', '-C', str(LYRA), 'archive', '--format=tar', '-o', str(archive), REVISION, 'LyraStarterGame'], check=True)
rows = []
with tarfile.open(archive) as source:
    for entry in source:
        if not entry.isfile():
            continue
        relative = pathlib.PurePosixPath(entry.name).relative_to('LyraStarterGame')
        target = DEST.joinpath(*relative.parts)
        data = source.extractfile(entry).read()
        if data.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
            fields = dict(line.split(' ', 1) for line in data.decode().splitlines()[1:])
            oid = fields['oid'].removeprefix('sha256:')
            cached = LYRA / '.git/lfs/objects' / oid[:2] / oid[2:4] / oid
            if not cached.is_file():
                raise FileNotFoundError(f'Missing local LFS object {oid} for {relative}')
            data = cached.read_bytes()
            assert len(data) == int(fields['size']) and hashlib.sha256(data).hexdigest() == oid
        digest = hashlib.sha256(data).hexdigest()
        if target.exists():
            assert hashlib.sha256(target.read_bytes()).hexdigest() == digest, f'Existing destination differs: {target}'
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        rows.append({'source': 'Lyra', 'path': relative.as_posix(), 'sha256': digest, 'bytes': len(data)})
print(f'Restored {len(rows)} Lyra files', flush=True)
for source in sorted((GASP / 'Content').rglob('*')):
    if not source.is_file():
        continue
    relative = source.relative_to(GASP)
    target = DEST / relative
    assert not target.exists(), f'GASP collision: {relative}'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    rows.append({'source': 'GASP', 'path': relative.as_posix(), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'bytes': source.stat().st_size})
engine = pathlib.Path(r'C:\Program Files\Epic Games\UE_5.8\Engine\Build\Build.version')
manifest = {'engine': json.loads(engine.read_text()), 'lyra_repository': str(LYRA), 'lyra_revision': REVISION, 'gasp_project': str(GASP), 'files': rows}
(ARTIFACTS / 'source-manifest.json').write_text(json.dumps(manifest, indent=2))
print(f'Staged {len(rows)} total files; recorded SHA-256 provenance', flush=True)
