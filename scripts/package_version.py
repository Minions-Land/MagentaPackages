#!/usr/bin/env python3
"""
Extract the version field from a package's package.toml.

Usage: python scripts/package_version.py <PackageName>
Returns: the version string (e.g. "1.0.0") on stdout, exits 1 if missing.
"""
import sys
import tomllib
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: package_version.py <PackageName>", file=sys.stderr)
    sys.exit(1)

package = sys.argv[1]
manifest = Path(package) / "package.toml"

if not manifest.exists():
    print(f"Error: {manifest} not found", file=sys.stderr)
    sys.exit(1)

with manifest.open("rb") as f:
    data = tomllib.load(f)

version = data.get("version")
if not version or not isinstance(version, str):
    print(f"Error: {manifest} has no valid version field", file=sys.stderr)
    sys.exit(1)

print(version)
