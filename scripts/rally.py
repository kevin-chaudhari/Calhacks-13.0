"""Cross-platform task runner (works on Windows without make).

    python scripts/rally.py setup      install Python and web dependencies
    python scripts/rally.py dev        run API (:8000) and web (:3000) together
    python scripts/rally.py api        run only the API
    python scripts/rally.py test       unit + integration tests
    python scripts/rally.py eval       negotiation evaluation (writes tests/evaluation/results)
    python scripts/rally.py contracts  regenerate packages/contracts/ts/index.ts
    python scripts/rally.py reset      reset the running API to the scuba scenario
    python scripts/rally.py health     print adapter modes of the running API
    python scripts/rally.py bureau     real uAgents round trip in a local Bureau
"""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
ENV = {**os.environ,
       "PYTHONPATH": os.pathsep.join([str(ROOT / "packages/contracts"), str(ROOT / "services/api")])}
SHELL = os.name == "nt"           # npm is npm.cmd on Windows


def run(cmd, cwd=ROOT, env=ENV):
    print("$", " ".join(cmd))
    return subprocess.call(cmd, cwd=cwd, env=env, shell=SHELL and cmd[0] in {"npm", "npx"})


def api_call(path, body=None):
    url = os.environ.get("API_URL", "http://localhost:8000") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))


def main(task):
    if task == "setup":
        return run([PY, "-m", "pip", "install", "-r", "requirements.txt"]) or run(["npm", "install"])
    if task == "api":
        return run([PY, "-m", "uvicorn", "rally.main:app", "--reload", "--port", "8000",
                    "--reload-dir", str(ROOT / "services"), "--reload-dir", str(ROOT / "packages")])
    if task == "dev":
        api = subprocess.Popen([PY, "-m", "uvicorn", "rally.main:app", "--port", "8000"], cwd=ROOT, env=ENV)
        try:
            return run(["npm", "--workspace", "apps/web", "run", "dev"])
        finally:
            api.terminate()
    if task == "test":
        return run([PY, "-m", "pytest", "tests/unit", "tests/integration", "-q"])
    if task == "eval":
        return run([PY, "tests/evaluation/run_negotiation.py", "50"])
    if task == "contracts":
        return run([PY, "packages/contracts/gen_ts.py"])
    if task == "reset":
        print(api_call("/v1/demo/reset", {"scenario": "scuba"}))
        return 0
    if task == "health":
        print(json.dumps(api_call("/v1/health"), indent=2))
        return 0
    if task == "bureau":
        return run([PY, "agents/bureau_demo.py"])
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
