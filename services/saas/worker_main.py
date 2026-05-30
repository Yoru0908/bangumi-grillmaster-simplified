from __future__ import annotations

import argparse

from services.saas.runtime import load_runtime_config
from services.saas.worker_daemon import create_worker_daemon


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the SaaS worker daemon")
    parser.add_argument("--worker-id", default="worker-1")
    parser.add_argument("--max-iterations", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    daemon = create_worker_daemon(
        load_runtime_config(),
        worker_id=args.worker_id,
    )
    daemon.run_forever(max_iterations=args.max_iterations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
