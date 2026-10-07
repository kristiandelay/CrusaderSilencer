"""Local file-based automation for this project's editor; no network listener."""
import contextlib
import io
import json
import time
import traceback
from pathlib import Path
import unreal as u

bridge_root = Path(__file__).resolve().parents[1] / 'Artifacts/EditorBridge'
bridge_root.mkdir(parents=True, exist_ok=True)
bridge_state = {'last': None, 'next': 0.0}
try:
    bridge_state['last'] = json.loads((bridge_root / 'request.json').read_text())['id']
except (OSError, ValueError, KeyError):
    pass
u.EditorPythonScripting.set_keep_python_script_alive(True)

def bridge_tick(delta):
    if time.monotonic() < bridge_state['next']:
        return
    bridge_state['next'] = time.monotonic() + 0.2
    path = bridge_root / 'request.json'
    if not path.exists():
        return
    try:
        request = json.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError, OSError):
        return
    if request['id'] == bridge_state['last']:
        return
    bridge_state['last'] = request['id']
    output = io.StringIO()
    error = None
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        try:
            exec(compile(request['code'], '<project-editor-request>', 'exec'), globals())
        except Exception:
            error = traceback.format_exc()
    (bridge_root / 'response.json').write_text(json.dumps({'id': request['id'], 'output': output.getvalue(), 'error': error}, indent=2), encoding='utf-8')

bridge_handle = u.register_slate_post_tick_callback(bridge_tick)
(bridge_root / 'ready.json').write_text(json.dumps({'project': u.Paths.get_project_file_path(), 'time': time.time()}))
u.log('CR_EDITOR_BRIDGE_READY')
