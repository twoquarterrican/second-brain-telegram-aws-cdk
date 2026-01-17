#!/usr/bin/env python3
"""Check for banned imports in common and lambdas packages.

Banned modules:
- click: Should only be used in scripts package

Usage:
    python scripts/check_banned_imports.py
    pre-commit run check-banned-imports --all-files
"""

from pathlib import Path


BANNED = {
    "click": ["common", "lambdas"],
}

EXCLUDED = ["packages/scripts/"]


def check_file(path: Path) -> list[tuple[int, str]]:
    """Check a file for banned imports."""
    if path.suffix != ".py":
        return []

    if any(str(path).startswith(excl) for excl in EXCLUDED):
        return []

    try:
        content = path.read_text()
    except Exception:
        return []

    errors = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        line = line.strip()
        if line.startswith("#"):
            continue

        for module, allowed_pkgs in BANNED.items():
            if line.startswith(f"import {module}") or line.startswith(f"from {module} "):
                pkg = determine_package(path)
                if pkg and pkg not in allowed_pkgs:
                    errors.append((line_no, f"'{module}' not allowed in {pkg}"))

    return errors


def determine_package(path: Path) -> str | None:
    """Determine which package this file belongs to."""
    s = str(path)
    if "/common/" in s:
        return "common"
    if "/lambdas/" in s:
        return "lambdas"
    return None


def main() -> int:
    """Main entry point."""
    base = Path(__file__).parent.parent

    all_errors = []
    for py_file in base.rglob("*.py"):
        for line_no, msg in check_file(py_file):
            all_errors.append((py_file, line_no, msg))

    if all_errors:
        print("❌ Banned import violations:\n")
        for path, line_no, msg in all_errors:
            print(f"  {msg}")
            print(f"    {path}:{line_no}")
        print(f"\n{len(all_errors)} violation(s)")
        return 1

    print("✅ No banned imports")
    return 0


if __name__ == "__main__":
    exit(main())
