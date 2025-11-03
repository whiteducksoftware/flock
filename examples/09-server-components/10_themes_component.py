"""
Themes Component Examples

This example demonstrates the ThemesComponent capabilities:
1. Custom theme configuration
2. Dashboard appearance customization
3. Theme API endpoints
4. Real-time theme switching
"""

import asyncio

from flock import Flock
from flock.components.server import ThemesComponent, ThemesComponentConfig


async def main():
    """Demonstrate Themes component usage."""
    print("🎨 Themes Component Examples\n")
    print("=" * 60)

    # Example 1: Basic Themes component
    print("\n1️⃣  Basic Themes Component")
    print("-" * 60)

    flock = Flock()

    themes_component = ThemesComponent(
        config=ThemesComponentConfig(
            prefix="/api/v1",
            tags=["Themes"],
            default_theme="dark",
        )
    )

    print("✅ Themes component created")
    print(f"   Default theme: {themes_component.config.default_theme}")
    print("   Endpoints:")
    print(f"   - GET {themes_component.config.prefix}/themes")
    print(f"   - GET {themes_component.config.prefix}/themes/current")
    print(f"   - POST {themes_component.config.prefix}/themes/set")

    # Example 2: Available themes
    print("\n2️⃣  Available Themes")
    print("-" * 60)
    print("""
    Built-in themes:

    📱 light    - Clean light theme with high contrast
    🌙 dark     - Modern dark theme (default)
    🌈 colorful - Vibrant colors and gradients
    🏢 corporate - Professional business theme
    🌿 nature   - Earthy tones and organic colors

    Themes customize:
    - Primary and accent colors
    - Background colors
    - Text colors
    - Border styles
    - Shadow effects
    - Font selections
    """)

    # Example 3: Custom theme configuration
    print("\n3️⃣  Custom Theme Configuration")
    print("-" * 60)

    custom_theme_config = ThemesComponentConfig(
        prefix="/api/v1",
        tags=["Themes"],
        default_theme="corporate",
        # Additional custom configuration can be added here
    )

    custom_themes = ThemesComponent(config=custom_theme_config)

    print("✅ Custom themes component created")
    print(f"   Default: {custom_themes.config.default_theme}")

    # Example 4: Full server setup
    print("\n4️⃣  Full Server Setup")
    print("-" * 60)

    print("\n🚀 Starting server with Themes component...")
    print("   Server will run on http://127.0.0.1:8344")
    print("\n   Available endpoints:")
    print("   - GET  http://127.0.0.1:8344/api/v1/themes")
    print("   - GET  http://127.0.0.1:8344/api/v1/themes/current")
    print("   - POST http://127.0.0.1:8344/api/v1/themes/set")
    print("\n   Press Ctrl+C to stop the server")

    # Start server (non-blocking for demo)
    await flock.serve(
        components=[themes_component],
        host="127.0.0.1",
        port=8344,
        blocking=False,
    )

    # Wait for server to start
    await asyncio.sleep(2)
    print("\n✅ Server is running!")

    # Example 5: Using the Themes API
    print("\n5️⃣  Using the Themes API")
    print("-" * 60)

    print("\n   You can interact with themes using curl:")
    print("\n   # Get all available themes:")
    print("   curl http://127.0.0.1:8344/api/v1/themes")
    print("\n   # Get current theme:")
    print("   curl http://127.0.0.1:8344/api/v1/themes/current")
    print("\n   # Set a new theme:")
    print("   curl -X POST http://127.0.0.1:8344/api/v1/themes/set \\")
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"theme": "colorful"}\'')

    print("\n   Example Python code:")
    print("""
    import requests

    # Get available themes
    response = requests.get("http://127.0.0.1:8344/api/v1/themes")
    themes = response.json()
    print(f"Available themes: {themes}")

    # Change theme
    response = requests.post(
        "http://127.0.0.1:8344/api/v1/themes/set",
        json={"theme": "nature"}
    )
    print(response.json())
    """)

    # Keep server running
    print("\n⏳ Keeping server running for 60 seconds...")
    print("   Try the curl commands above!")
    try:
        await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
