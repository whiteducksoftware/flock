"""
Static Files Component Examples

This example demonstrates the StaticFilesServerComponent capabilities:
1. Serving static files (HTML, CSS, JS)
2. SPA (Single Page Application) routing
3. Custom directory configuration
4. Priority management (must be last!)
"""

import asyncio
from pathlib import Path

from flock import Flock
from flock.components.server import (
    StaticFilesComponentConfig,
    StaticFilesServerComponent,
)


async def create_demo_files():
    """Create demo static files for the example."""
    # Create demo directory
    demo_dir = Path("./demo_static")
    demo_dir.mkdir(exist_ok=True)

    # Create index.html
    index_html = demo_dir / "index.html"
    index_html.write_text(
        """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flock Static Files Demo</title>
    <link rel="stylesheet" href="/styles.css">
</head>
<body>
    <div class="container">
        <h1>🦆 Flock Static Files Demo</h1>
        <p>This is served by the StaticFilesServerComponent!</p>
        <div class="info">
            <h2>Component Features:</h2>
            <ul>
                <li>✅ Serves static HTML, CSS, JavaScript files</li>
                <li>✅ SPA routing support (serves index.html for all routes)</li>
                <li>✅ Custom directory configuration</li>
                <li>✅ Must be registered with highest priority (last)</li>
            </ul>
        </div>
        <div class="navigation">
            <h3>Try SPA Routing:</h3>
            <a href="/about">About Page</a>
            <a href="/contact">Contact Page</a>
            <a href="/dashboard">Dashboard</a>
        </div>
    </div>
    <script src="/app.js"></script>
</body>
</html>
"""
    )

    # Create styles.css
    styles_css = demo_dir / "styles.css"
    styles_css.write_text(
        """body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
}

.container {
    background: white;
    border-radius: 12px;
    padding: 40px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}

h1 {
    color: #667eea;
    margin-top: 0;
}

h2 {
    color: #764ba2;
    border-bottom: 2px solid #667eea;
    padding-bottom: 10px;
}

.info {
    background: #f7f9fc;
    padding: 20px;
    border-radius: 8px;
    margin: 20px 0;
}

ul {
    list-style: none;
    padding: 0;
}

li {
    padding: 8px 0;
    font-size: 16px;
}

.navigation {
    margin-top: 30px;
    padding: 20px;
    background: #e8eaf6;
    border-radius: 8px;
}

.navigation a {
    display: inline-block;
    margin: 10px 10px 10px 0;
    padding: 10px 20px;
    background: #667eea;
    color: white;
    text-decoration: none;
    border-radius: 6px;
    transition: background 0.3s;
}

.navigation a:hover {
    background: #764ba2;
}
"""
    )

    # Create app.js
    app_js = demo_dir / "app.js"
    app_js.write_text(
        """console.log('🦆 Flock Static Files Component loaded!');

// Display current route
const currentPath = window.location.pathname;
console.log('Current path:', currentPath);

// Update page based on route (SPA simulation)
if (currentPath !== '/') {
    const routeName = currentPath.substring(1);
    const infoDiv = document.querySelector('.info');
    infoDiv.innerHTML = `
        <h2>Current Route: ${routeName}</h2>
        <p>This is the ${routeName} page, but we're still serving index.html!</p>
        <p>This demonstrates SPA routing with the StaticFilesServerComponent.</p>
        <a href="/">← Back to Home</a>
    `;
}

// Add some interactivity
document.addEventListener('DOMContentLoaded', () => {
    console.log('Page loaded successfully!');
    console.log('StaticFilesServerComponent is working! 🎉');
});
"""
    )

    return demo_dir


async def main():
    """Demonstrate Static Files component usage."""
    print("📁 Static Files Component Examples\n")
    print("=" * 60)

    # Create demo files
    print("\n📝 Creating demo static files...")
    demo_dir = await create_demo_files()
    print(f"✅ Demo files created in: {demo_dir.absolute()}")

    # Example 1: Basic Static Files component
    print("\n1️⃣  Basic Static Files Component")
    print("-" * 60)

    flock = Flock()

    static_component = StaticFilesServerComponent(
        config=StaticFilesComponentConfig(
            directory=str(demo_dir),
            html=True,  # Enable SPA routing
        ),
        priority=99,  # MUST BE LAST!
    )

    print("✅ Static Files component created")
    print(f"   Directory: {static_component.config.directory}")
    print(f"   SPA routing: {static_component.config.html}")
    print(f"   Priority: {static_component.priority} (highest = last)")

    # Example 2: Why priority matters
    print("\n2️⃣  Understanding Priority")
    print("-" * 60)
    print("""
    ⚠️  CRITICAL: StaticFilesServerComponent MUST have the highest priority!

    Why? Static file routes use a catch-all pattern that would override
    other routes if registered first.

    ✅ CORRECT Priority Order:
       1. HealthComponent (priority=0)
       2. CORSComponent (priority=8)
       3. AuthenticationComponent (priority=7)
       4. AgentsComponent (priority=20)
       5. ArtifactsComponent (priority=20)
       6. StaticFilesServerComponent (priority=99) ← LAST!

    ❌ WRONG: Static files with low priority will break API routes!
    """)

    # Example 3: Full server setup
    print("\n3️⃣  Full Server Setup with SPA Routing")
    print("-" * 60)

    print("\n🚀 Starting server with Static Files component...")
    print("   Server will run on http://127.0.0.1:8344")
    print("\n   Try these URLs:")
    print("   - http://127.0.0.1:8344/")
    print("   - http://127.0.0.1:8344/about")
    print("   - http://127.0.0.1:8344/contact")
    print("   - http://127.0.0.1:8344/dashboard")
    print("\n   All routes will serve index.html (SPA routing)")
    print("\n   Press Ctrl+C to stop the server")

    # Start server (non-blocking for demo)
    await flock.serve(
        components=[static_component],
        host="127.0.0.1",
        port=8344,
        blocking=False,
    )

    # Wait for server to start
    await asyncio.sleep(2)
    print("\n✅ Server is running!")
    print("\n   Open your browser and visit the URLs above!")

    # Keep server running
    print("\n⏳ Keeping server running for 60 seconds...")
    print("   Try navigating between pages to see SPA routing in action!")
    try:
        await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
    finally:
        # Clean up demo files
        print("\n🧹 Cleaning up demo files...")
        import shutil

        shutil.rmtree(demo_dir)
        print("✅ Demo files removed")


if __name__ == "__main__":
    asyncio.run(main())
