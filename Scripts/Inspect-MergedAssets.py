import unreal as u
from pathlib import Path
root = Path(__file__).resolve().parents[1] / 'Artifacts/Inspection'
root.mkdir(parents=True, exist_ok=True)
paths = ['/Game/Blueprints/SandboxCharacter_CMC', '/Game/Blueprints/AC_TraversalLogic', '/Game/Blueprints/PC_Sandbox', '/Game/Blueprints/AC_VisualOverrideManager', '/Game/Blueprints/SandboxCharacter_CMC_ABP']
for path in paths:
    asset = u.load_asset(path)
    (root / (asset.get_name() + '-graph.txt')).write_text(u.CRBlueprintTools.describe_blueprint(asset), encoding='utf-8')
    (root / (asset.get_name() + '-defaults.txt')).write_text(u.CRBlueprintTools.describe_object(u.get_default_object(asset.generated_class())), encoding='utf-8')
imc = u.load_asset('/Game/Input/IMC_Sandbox')
(root / 'input.txt').write_text(u.CRBlueprintTools.describe_object(imc), encoding='utf-8')
for path in ['/Game/Characters/UEFN_Mannequin/Meshes/SK_UEFN_Mannequin', '/Game/Characters/Heroes/Mannequin/Meshes/SKM_Manny', '/Game/Characters/Heroes/Mannequin/Meshes/SK_Mannequin']:
    asset = u.load_asset(path)
    if asset:
        (root / (asset.get_name() + '.txt')).write_text(u.CRBlueprintTools.describe_object(asset), encoding='utf-8')
u.log('CR_MERGED_INSPECTION_COMPLETE')
