import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # audit/ (so this also works as a plain script inside the sandbox)
from shuna_probe.cli import main
main()
