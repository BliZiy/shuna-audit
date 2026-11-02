"""Shuna sandbox backend: every script that executes model-written (or mutant) code calls sandbox.enter()
at the very top. Default backend = OpenShell: the WHOLE script is re-run inside a fresh OpenShell sandbox
(image shuna-sandbox:py312, CPU/memory limits, deny-all network, Landlock FS policy tools/sandbox_policy.yaml),
then results/ is copied back and the sandbox deleted.
  Host fallback (unsafe, no isolation): SHUNA_SANDBOX=host  or pass --sandbox=host to the script.
  Limits: SHUNA_SB_CPU (default 4), SHUNA_SB_MEM (default 8Gi). Keep sandbox for debugging: SHUNA_SB_KEEP=1.
  Prereq after every box restart: bash tools/start_openshell.sh"""
import os, sys, subprocess, time, shlex
AUDIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(os.path.dirname(AUDIT), 'tools')
REMOTE = '/sandbox/audit'
IMAGE = os.environ.get('SHUNA_SB_IMAGE', 'shuna-sandbox:py312')
EXCLUDE = ['models', 'site', '__pycache__', '.pytest_cache']
def _log(*a): print('[sandbox]', *a, file=sys.stderr, flush=True)
def _remote_argv():
    a0 = os.path.abspath(sys.argv[0])
    if a0.startswith(AUDIT + os.sep): head = [os.path.relpath(a0, AUDIT)]
    elif 'pytest' in a0: head = ['-m', 'pytest']
    else: raise SystemExit(f'[sandbox] cannot map entrypoint {sys.argv[0]} into the sandbox; use SHUNA_SANDBOX=host')
    rest = [x.replace(AUDIT, REMOTE) for x in sys.argv[1:]]
    return ['python3'] + head + rest
def _os(*args, **kw): return subprocess.run(['openshell', *args], **kw)
def enter():
    if '--sandbox=host' in sys.argv: sys.argv.remove('--sandbox=host'); os.environ['SHUNA_SANDBOX'] = 'host'
    if os.environ.get('SHUNA_IN_SANDBOX') == '1': return
    mode = os.environ.get('SHUNA_SANDBOX', 'openshell')
    if mode == 'host':
        if not os.environ.get('_SHUNA_WARNED'): _log('WARNING host mode: model code runs UNSANDBOXED on this box'); os.environ['_SHUNA_WARNED'] = '1'
        return
    if mode != 'openshell': raise SystemExit(f'[sandbox] unknown SHUNA_SANDBOX={mode}')
    os.environ.setdefault('DOCKER_HOST', 'unix:///tmp/dock/docker.sock')
    if b'Connected' not in _os('status', capture_output=True).stdout:
        raise SystemExit('[sandbox] OpenShell gateway not reachable. Run: bash tools/start_openshell.sh  (or SHUNA_SANDBOX=host to run unsandboxed)')
    cpu, mem = os.environ.get('SHUNA_SB_CPU', '4'), os.environ.get('SHUNA_SB_MEM', '8Gi')
    name = f"shuna-{os.getpid()}-{os.urandom(2).hex()}"[:19]  # OpenShell max name length 19
    t0 = time.time(); rc = 1
    r = _os('sandbox', 'create', '--name', name, '--from', IMAGE, '--cpu', cpu, '--memory', mem,
            '--policy', os.path.join(TOOLS, 'sandbox_policy.yaml'), capture_output=True, text=True)
    if r.returncode: raise SystemExit(f'[sandbox] create failed: {r.stdout[-500:]}{r.stderr[-500:]}')
    try:
        tb = f'/tmp/{name}-in.tar'
        subprocess.run(['tar', 'cf', tb] + [f'--exclude={e}' for e in EXCLUDE] + ['-C', os.path.dirname(AUDIT), os.path.basename(AUDIT)], check=True)
        r = _os('sandbox', 'upload', '--no-git-ignore', name, tb, '/sandbox/in.tar', capture_output=True, text=True); os.unlink(tb)
        if r.returncode: raise SystemExit(f'[sandbox] upload failed: {r.stderr[-400:]}')
        r = _os('sandbox', 'exec', '-n', name, '--no-tty', '--', 'sh', '-c',
                f'mkdir -p {REMOTE} && tar xf /sandbox/in.tar -C {REMOTE} --strip-components=1 && rm /sandbox/in.tar')
        if r.returncode: raise SystemExit('[sandbox] unpack failed')
        t1 = time.time(); argv = _remote_argv()
        _log(f'{name}: cpu={cpu} mem={mem} image={IMAGE} net=deny; upload {t1-t0:.1f}s; running: {" ".join(argv)}')
        cmd = f'cd {REMOTE} && SHUNA_IN_SANDBOX=1 PYTHONDONTWRITEBYTECODE=1 exec ' + ' '.join(map(shlex.quote, argv))
        rc = _os('sandbox', 'exec', '-n', name, '--no-tty', '--', 'sh', '-c', cmd).returncode
        if rc == 137: _log('exit 137: killed (likely sandbox memory limit SHUNA_SB_MEM)')
        tb = f'/tmp/{name}-out.tar'
        ok = _os('sandbox', 'exec', '-n', name, '--no-tty', '--', 'tar', 'cf', '/sandbox/out.tar', '-C', REMOTE, 'results').returncode == 0 \
             and _os('sandbox', 'download', name, '/sandbox/out.tar', tb, capture_output=True).returncode == 0
        if ok: subprocess.run(['tar', 'xf', tb, '-C', AUDIT], check=True); os.unlink(tb)
        else: _log('WARNING: could not copy results/ back')
        _log(f'{name}: exit {rc}; total {time.time()-t0:.1f}s')
    finally:
        if os.environ.get('SHUNA_SB_KEEP') != '1': _os('sandbox', 'delete', name, capture_output=True)
    sys.stdout.flush(); sys.stderr.flush(); os._exit(rc)
