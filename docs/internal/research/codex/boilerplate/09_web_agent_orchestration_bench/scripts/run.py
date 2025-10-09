from __future__ import annotations
import argparse, asyncio, os, sys
from pathlib import Path

# Add shared harness to path
SHARED = Path(__file__).resolve().parents[2] / '_shared' / 'harness'
sys.path.append(str(SHARED))

import runner  # type: ignore

def main() -> int:
    parser = argparse.ArgumentParser(description='Run boilerplate noop batch experiment')
    parser.add_argument('--config', default=str(Path(__file__).resolve().parents[0]/'configs'/'experiment.json'))
    args = parser.parse_args()
    cfg = runner.ExperimentConfig.from_json(args.config)
    asyncio.run(runner._run_noop_batch_async(cfg))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
