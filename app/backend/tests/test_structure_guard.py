"""Enforce that main.py contains no @app.<method> route decorators.

All route handlers must live in routers/. This test fails the fast gate when someone
bypasses the convention, pointing them to the routers/ package.
"""

import pathlib
import re


def test_main_has_no_app_route_decorators():
    main_src = (pathlib.Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    pattern = re.compile(r"@app\.(get|post|put|patch|delete)\b")
    matches = pattern.findall(main_src)
    assert not matches, (
        f"main.py contains {len(matches)} @app.<method> decorator(s): {matches}. "
        "Route handlers must live in routers/, not main.py."
    )
