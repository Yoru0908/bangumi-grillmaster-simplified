from __future__ import annotations

import argparse

from services.saas.runtime import BootstrapOptions, bootstrap_runtime, load_runtime_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap SaaS runtime state")
    parser.add_argument("--invite-code")
    parser.add_argument("--invite-email")
    parser.add_argument("--invite-role", default="member", choices=["member", "admin"])
    parser.add_argument("--initial-credit-minutes", type=float, default=0)
    parser.add_argument("--now", default="2026-01-01T00:00:00Z")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = bootstrap_runtime(
        load_runtime_config(),
        BootstrapOptions(
            invite_code=args.invite_code,
            invite_email=args.invite_email,
            invite_role=args.invite_role,
            initial_credit_minutes=args.initial_credit_minutes,
            now=args.now,
        ),
    )
    connection = result.get("connection")
    if connection is not None:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
