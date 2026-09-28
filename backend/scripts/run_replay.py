"""Run or resume a chronological replay.

Examples::

    python -m scripts.run_replay --mode off --run-id smoke --rep-id priya --quarter 2017-Q1
    python -m scripts.run_replay --mode off --run-id demo
    python -m scripts.run_replay --mode on --run-id demo
"""
from __future__ import annotations

import argparse
import importlib

from app.replay.engine import DATA, run


def _load_services(spec: str | None):
    if not spec:
        return None
    module_name, separator, attribute = spec.partition(":")
    if not separator:
        raise SystemExit("--services must be module.path:factory_or_object")
    target = getattr(importlib.import_module(module_name), attribute)
    return target() if callable(target) else target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("on", "off"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--rep-id", help="limit the replay to one rep for a quick smoke run")
    parser.add_argument("--quarter", help="limit forecasts to one calendar quarter")
    parser.add_argument("--deals", help="input deals.csv (defaults to backend/data/deals.csv)")
    parser.add_argument("--services", help="Role 2 adapter as module.path:factory (required for memory ON)")
    parser.add_argument("--no-resume", action="store_true", help="reprocess completed quarters")
    args = parser.parse_args()
    service_spec = args.services
    if args.mode == "on" and service_spec is None:
        service_spec = "app.replay.hindsight_services:build_services"
    try:
        services = _load_services(service_spec)
    except (ImportError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
    result = run(
        mode=args.mode,
        run_id=args.run_id,
        deals_path=args.deals if args.deals else DATA / "deals.csv",
        rep_id=args.rep_id,
        forecast_quarter=args.quarter,
        resume=not args.no_resume,
        services=services,
    )
    print(f"{result.mode} replay {result.run_id}: {result.output_dir} ({len(result.completed_quarters)} quarters complete)")


if __name__ == "__main__":
    main()
