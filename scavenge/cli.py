"""`probe inspect <url> --field price` — a thin shell over the evidence engine.

The CLI holds no logic of its own: it parses arguments, calls `inspect_field`, and prints.
MCP calls the same function, so the two interfaces cannot disagree.
"""

from __future__ import annotations

import argparse
import json
import sys

from scavenge import robots
from scavenge.acquire import USER_AGENT, rendering_session
from scavenge.engine import FIELDS, UnknownFieldError, inspect_field
from scavenge.render import render
from scavenge.safety import UnsafeTargetError, check_target

EXIT_REFUSED = 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scavenge", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="collect evidence for one field on one page")
    inspect.add_argument("url")
    inspect.add_argument("--field", default="price", choices=sorted(FIELDS))
    inspect.add_argument("--json", action="store_true", help="emit the report as JSON")
    inspect.add_argument("--no-render", action="store_true", help="skip the browser pass")
    args = parser.parse_args(argv)

    try:
        check_target(args.url)
    except UnsafeTargetError as exc:
        print(f"refusing: {exc}", file=sys.stderr)
        return EXIT_REFUSED

    decision = robots.fetch(args.url, USER_AGENT)
    if not decision.allowed:
        print(f"refusing: {decision.disposition.value} for {args.url}", file=sys.stderr)
        return EXIT_REFUSED

    try:
        if args.no_render:
            report = inspect_field(args.url, args.field, renderer=None)
        else:
            with rendering_session() as renderer:
                report = inspect_field(args.url, args.field, renderer=renderer)
    except (UnsafeTargetError, UnknownFieldError) as exc:
        print(f"refusing: {exc}", file=sys.stderr)
        return EXIT_REFUSED

    print(json.dumps(report.to_dict(), indent=2) if args.json else render(report), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
