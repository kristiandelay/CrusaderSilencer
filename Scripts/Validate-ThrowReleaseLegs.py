"""Persist release-time leg measurements and saved montage slot assignments."""
import datetime,hashlib,json
from pathlib import Path
import unreal as u

trv_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
trv_checks={}
for name in ['release-legs','release-legs-network']:
    data=json.loads((trv_root/f'Artifacts/Throw/{name}.json').read_text())
    assert data['passed'] and len(data['results'])==10,(name,data.get('error'))
    trv_checks[name]=data['results']
assert json.loads((trv_root/'Artifacts/Throw/release-legs-suite.json').read_text())['passed']
trv_slots={};trv_hashes={}
for name in ['AM_Aim','AM_Left_Aim','AM_Throw','AM_Left_Throw']:
    montage=u.load_asset('/Game/Crusader/Equipment/Throw/'+name)
    slots=[str(track.get_editor_property('slot_name')) for track in montage.get_editor_property('slot_anim_tracks')]
    assert slots==['ThrowUpperBody'],(name,slots)
    path='src/Content/Crusader/Equipment/Throw/'+name+'.uasset'
    data=(trv_root/path).read_bytes();assert b'ThrowUpperBody' in data,'Slot assignment absent from saved asset'
    trv_slots[name]=slots;trv_hashes[path]=hashlib.sha256(data).hexdigest()
trv_report=dict(passed=True,validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=trv_checks,
    saved_slots=trv_slots,hashes=trv_hashes,
    cause='Editing an Unreal struct-array element without writing it back left the release montages in DefaultSlot.',
    scope='Actual source/visible foot movement during release, not only pawn displacement. Both hands/types, forward/diagonal movement, slide leg preservation, one item consumed, standalone and owning network client.')
(trv_root/'resources/ThrowReleaseLegValidation.json').write_text(json.dumps(trv_report,indent=2)+'\n')
trv_previous=json.loads((trv_root/'resources/ThrowValidation.json').read_text());trv_previous['release_legs_update']='resources/ThrowReleaseLegValidation.json'
(trv_root/'resources/ThrowValidation.json').write_text(json.dumps(trv_previous,indent=2)+'\n')
print('THROW_RELEASE_LEGS_VALIDATED',20,'checks; all four saved montage slots verified')
