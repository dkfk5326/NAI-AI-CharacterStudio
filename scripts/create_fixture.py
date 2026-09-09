"""Small synthetic DB for repeatable UI testing, explicitly not a real release."""
import sys,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tests.test_core import fixture
p=argparse.ArgumentParser();p.add_argument('path',nargs='?',default=str(ROOT/'data/demo-fixture.sqlite'));args=p.parse_args();target=Path(args.path)
if target.exists():raise SystemExit('Target exists. Choose another path.')
target.parent.mkdir(parents=True,exist_ok=True);fixture(target);print('Synthetic test fixture:',target.resolve())
