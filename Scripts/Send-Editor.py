"""Execute a Python file in the task-owned Unreal editor and print its result."""
import json
from pathlib import Path
import sys
import time
import uuid

root = Path(__file__).resolve().parents[1] / 'Artifacts/EditorBridge'
code = Path(sys.argv[1]).read_text(encoding='utf-8-sig') if len(sys.argv) > 1 else sys.stdin.read()
identifier = uuid.uuid4().hex
temporary = root / 'request.tmp'
temporary.write_text(json.dumps({'id': identifier, 'code': code}), encoding='utf-8')
temporary.replace(root / 'request.json')
deadline = time.monotonic() + 120
while time.monotonic() < deadline:
    try:
        response = json.loads((root / 'response.json').read_text())
        if response['id'] == identifier:
            print(response['output'])
            if response['error']:
                print(response['error'])
                sys.exit(1)
            break
    except (ValueError, OSError):
        pass
    time.sleep(0.25)
else:
    raise TimeoutError('Editor request is still pending; inspect the editor process and response before retrying')
