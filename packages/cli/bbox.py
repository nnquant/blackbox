from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
for package_dir in ("packages/common", "packages/sdk", "packages/cli", "apps/server"):
    path = str(ROOT / package_dir)
    if path not in sys.path:
        sys.path.insert(0, path)

from blackbox_cli.main import main


if __name__ == "__main__":
    raise SystemExit(main())
