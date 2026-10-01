"""Guided local Docker setup. Run: python start.py. Requires Docker Desktop/Engine."""
import argparse
import json
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description='Start Parallel Arcade locally with Docker')
    parser.add_argument('--skip-model', action='store_true', help='Skip one-time model download')
    parser.add_argument('--no-browser', action='store_true')
    options = parser.parse_args()
    if not shutil.which('docker'):
        raise SystemExit('Install and start Docker Desktop/Engine first: https://docs.docker.com/get-started/get-docker/')
    try:
        run('docker','compose','version')
    except subprocess.CalledProcessError:
        raise SystemExit('Docker Compose is required. Start Docker Desktop, then try again.')
    env = ROOT / '.env'
    if not env.exists():
        token = secrets.token_urlsafe(32)
        env.write_text((ROOT/'.env.example').read_text().replace('replace-with-a-random-token-at-least-24-characters',token),encoding='utf-8')
        try:
            env.chmod(0o600)
        except OSError:
            pass
    values = {}
    for line in env.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value = line.split('=',1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    token = values.get('PARALLEL_TOKEN','')
    if len(token)<24 or token.startswith('replace-with-'):
        raise SystemExit('Replace PARALLEL_TOKEN in .env with a random token of at least 24 characters, then rerun.')
    print('Building local services. First run downloads dependencies and may take several minutes.',flush=True)
    run('docker','compose','up','--build','-d')
    if not options.skip_model:
        print('Installing the English → Arabic model if missing…',flush=True)
        run('docker','compose','exec','-T','gateway','python','backend/install_model.py')
    url = 'http://localhost:8000'
    last_error = ''
    for _ in range(15):
        try:
            req = urllib.request.Request(url+'/api/health',headers={'Authorization':'Bearer '+token})
            with urllib.request.urlopen(req,timeout=8) as response:
                health = json.load(response)
            break
        except Exception as exc:
            last_error = str(exc)
            time.sleep(2)
    else:
        raise SystemExit('Server did not become ready: '+last_error+'\nCheck: docker compose logs gateway')
    print('\nOpen: '+url+'\nAccess token (paste into Server & sync):\n'+token)
    print('Arabic model: '+str(health.get('translation_ready'))+' | OCR: '+str(health.get('ocr_ready')))
    print('No commercial emulator or game is installed by this launcher.')
    if not options.no_browser:
        webbrowser.open(url)


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print('Setup command failed. Check Docker logs/network and retry. Exit code:',exc.returncode,file=sys.stderr)
        sys.exit(exc.returncode)
