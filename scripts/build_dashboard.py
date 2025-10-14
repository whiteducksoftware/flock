#!/usr/bin/env python3
"""
Build Dashboard - Copy frontend build artifacts to Python package

This script runs after `npm run build` to copy the built React dashboard
into the Python package so it can be served by DashboardHTTPService.

Usage:
    cd frontend && npm run build && cd .. && python scripts/build_dashboard.py && uv build
"""

import shutil
import sys
from pathlib import Path


def main():
    """Copy frontend build artifacts into Python package."""
    # Paths
    project_root = Path(__file__).parent.parent
    frontend_dist = project_root / "frontend" / "dist"
    dashboard_static = project_root / "src" / "flock" / "dashboard" / "static"

    # Validate frontend build exists
    if not frontend_dist.exists():
        print(f"❌ Frontend build not found at {frontend_dist}")
        print("   Run 'cd frontend && npm run build' first")
        return 1

    # Check for index.html (primary artifact)
    index_html = frontend_dist / "index.html"
    if not index_html.exists():
        print(f"❌ index.html not found in {frontend_dist}")
        print("   Frontend build may have failed")
        return 1

    # Create dashboard static directory
    print(f"📁 Creating dashboard static directory: {dashboard_static}")
    dashboard_static.mkdir(parents=True, exist_ok=True)

    # Remove old build artifacts
    if dashboard_static.exists() and any(dashboard_static.iterdir()):
        print(f"🗑️  Removing old build artifacts from {dashboard_static}")
        shutil.rmtree(dashboard_static)
        dashboard_static.mkdir(parents=True, exist_ok=True)

    # Copy all files from frontend/dist to dashboard/static
    print(f"📦 Copying frontend build: {frontend_dist} → {dashboard_static}")
    shutil.copytree(frontend_dist, dashboard_static, dirs_exist_ok=True)

    # Verify critical files
    critical_files = ["index.html", "assets"]
    for file in critical_files:
        target = dashboard_static / file
        if not target.exists():
            print(f"⚠️  Warning: {file} not found in build output")
        else:
            print(f"✅ {file}")

    print("\n✅ Dashboard build complete!")
    print(f"   Static files ready at: {dashboard_static}")
    print("\n📦 Next step: Run 'uv build' to package with Python distribution")
    return 0


if __name__ == "__main__":
    sys.exit(main())
