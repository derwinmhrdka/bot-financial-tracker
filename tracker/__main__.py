from tracker.env import load_env_local
from tracker.cli import main

load_env_local()
raise SystemExit(main())
