"""Verify sandbox limits enforce: SHUNA_SB_CPU=1 SHUNA_SB_MEM=256Mi python3 src/sandbox_selftest.py [mem|cpu|net|fs]"""
import os as _o, sys as _s; _s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__))); import sandbox as _sb; _sb.enter()  # run model code in OpenShell (see src/sandbox.py)
import sys, os, time, subprocess
what = sys.argv[1] if len(sys.argv) > 1 else 'mem'
if what == 'mem':   # hog 2 GB in 10 MB steps
    b = []
    for i in range(200): b.append(bytearray(10**7)); print('MB', 10*(i+1), flush=True) if i % 10 == 9 else None
    print('mem hog NOT capped'); sys.exit(0)
if what == 'cpu':   # 4 busy processes for 5 s wall each; uncapped ~20 CPU-s, capped at 1 CPU ~5 CPU-s
    s = time.time(); ps = [subprocess.Popen([sys.executable, '-c', 'import time\nt=time.time()\nwhile time.time()-t<5: pass']) for _ in range(4)]
    [p.wait() for p in ps]; r = os.times(); c = r.children_user + r.children_system
    print(f'cpu: wall {time.time()-s:.1f}s, child CPU {c:.1f}s -> effective cores {c/(time.time()-s):.2f}')
if what == 'net':
    import urllib.request
    try: urllib.request.urlopen('https://example.com', timeout=5); print('net OPEN')
    except Exception as e: print('net blocked:', e)
if what == 'fs':
    for p in ('/etc/pwned', '/usr/x'):
        try: open(p, 'w'); print('fs WRITABLE', p)
        except Exception as e: print('fs blocked:', p, e)
