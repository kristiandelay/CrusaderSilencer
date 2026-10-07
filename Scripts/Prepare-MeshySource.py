"""Extract a Meshy FBX archive with stable model and texture names.

Usage: python Scripts/Prepare-MeshySource.py ARCHIVE NAME DESTINATION
The original archive is retained; source provenance is recorded beside the files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile


def prepare(archive, name, destination):
    assert re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name), 'Use an asset-safe name'
    destination.mkdir(parents=True, exist_ok=True)
    files = []
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            if member.is_dir():
                continue
            source = Path(member.filename)
            if source.suffix.lower() == '.fbx':
                filename = name + '.fbx'
            elif source.suffix.lower() == '.png':
                kind = next((kind for suffix, kind in [('_metallic', 'Metallic'), ('_normal', 'Normal'), ('_roughness', 'Roughness')]
                             if source.stem.endswith(suffix)), 'BaseColor')
                filename = name + '_' + kind + '.png'
            else:
                raise ValueError('Unrecognized source file: ' + member.filename)
            data = package.read(member)
            output = destination / filename
            if output.exists():
                assert output.read_bytes() == data, 'Refusing to replace modified source: ' + str(output)
            else:
                output.write_bytes(data)
            files.append({'original': member.filename, 'file': filename, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    manifest_path = destination / 'SourceManifest.json'
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest = {'name': name, 'archive': archive.name, 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': files}
    if previous.get('archive_sha256') == manifest['archive_sha256']:
        for key in ['original_archive_name', 'archive_path']:
            if key in previous:
                manifest[key] = previous[key]
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('name')
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    prepare(args.archive, args.name, args.destination)
