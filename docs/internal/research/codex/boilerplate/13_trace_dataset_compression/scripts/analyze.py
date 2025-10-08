from __future__ import annotations
import argparse, sys, os
from pathlib import Path

SHARED = Path(__file__).resolve().parents[2] / '_shared' / 'scripts'
sys.path.append(str(SHARED))

import analyze_template as analyze  # type: ignore

if __name__=='__main__':
    raise SystemExit(analyze.main())
