import unreal as u
import json
from pathlib import Path

report = {}
for path in ['/Game/Blueprints/SandboxCharacter_CMC', '/Game/Blueprints/AC_TraversalLogic', '/Game/Blueprints/PC_Sandbox', '/Game/Blueprints/GM_Sandbox']:
    asset = u.load_asset(path)
    cdo = u.get_default_object(asset.generated_class())
    props = {}
    for name in dir(cdo):
        if name.startswith('_'):
            continue
        try:
            value = cdo.get_editor_property(name)
            props[name] = str(value)
        except Exception:
            pass
    report[path] = props
    report[path]['methods'] = [name for name in dir(cdo) if not name.startswith('_')]
    if isinstance(cdo, u.Actor):
        sub = u.get_engine_subsystem(u.SubobjectDataSubsystem)
        lib = u.SubobjectDataBlueprintFunctionLibrary
        report[path]['components'] = []
        for handle in sub.k2_gather_subobject_data_for_blueprint(asset):
            obj = lib.get_object(lib.get_data(handle))
            report[path]['components'].append({'name': obj.get_name(), 'class': obj.get_class().get_path_name()})
imc = u.load_asset('/Game/Input/IMC_Sandbox')
report['input'] = [{'action': m.action.get_name(), 'key': str(m.key)} for m in imc.get_editor_property('mappings')]
Path(r'C:/Development/Game/CrusaderSilencer/Artifacts/gasp-inspection.json').write_text(json.dumps(report, indent=2))
u.log('CR_GASP_INSPECTION_COMPLETE')
