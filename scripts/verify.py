"""Run upstream regression and UI integration suites in separate processes."""
from pathlib import Path
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
temp_dir = root / '.tmp'
temp_dir.mkdir(exist_ok=True)
env = os.environ.copy()
env.update(TEMP=str(temp_dir), TMP=str(temp_dir), PYTHONPATH=str(root / 'bind-zero-x' / 'code'))
for directory in (root / 'bind-zero-x' / 'code', root / 'tests'):
    completed = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(directory), '-p', 'test_*.py', '-q'], cwd=root, env=env)
    if completed.returncode:
        raise SystemExit(completed.returncode)
print('All local suites passed. This does not certify physical/AWS/OpenCV5 readiness.')
