"""Comprehensive tests for StaticFilesServerComponent."""

import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from flock.components.server.static_files import (
    StaticFilesComponentConfig,
    StaticFilesServerComponent,
)
from flock.core.orchestrator import Flock


@pytest.fixture
def orchestrator():
    """Create a test orchestrator."""
    return Flock("openai/gpt-4o")


@pytest.fixture
def app():
    """Create a FastAPI app."""
    return FastAPI()


@pytest.fixture
def temp_static_dir():
    """Create a temporary directory with static files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create test files
        (tmp_path / "index.html").write_text("<html><body>Home</body></html>")
        (tmp_path / "about.html").write_text("<html><body>About</body></html>")
        (tmp_path / "styles.css").write_text("body { color: red; }")

        # Create subdirectory
        subdir = tmp_path / "assets"
        subdir.mkdir()
        (subdir / "logo.png").write_bytes(b"fake-png-data")

        yield tmp_path


class TestStaticFilesComponentConfig:
    """Tests for StaticFilesComponentConfig."""

    def test_default_values(self, temp_static_dir):
        """Test default configuration values."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)

        assert config.enabled is True
        assert config.prefix == ""
        assert config.tags == ["Static Files"]
        assert config.mount_point == "/"
        assert config.static_files_path == temp_static_dir

    def test_custom_values(self, temp_static_dir):
        """Test custom configuration values."""
        config = StaticFilesComponentConfig(
            prefix="/custom",
            tags=["Custom", "Files"],
            mount_point="/static",
            static_files_path=temp_static_dir,
        )

        assert config.prefix == "/custom"
        assert config.tags == ["Custom", "Files"]
        assert config.mount_point == "/static"
        assert config.static_files_path == temp_static_dir

    def test_static_files_path_as_string(self, temp_static_dir):
        """Test that static_files_path can be a string."""
        config = StaticFilesComponentConfig(static_files_path=str(temp_static_dir))

        assert isinstance(config.static_files_path, (str, Path))


class TestStaticFilesServerComponent:
    """Tests for StaticFilesServerComponent."""

    def test_init_defaults(self, temp_static_dir):
        """Test component initialization with defaults."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)

        assert component.name == "static_files"
        assert component.priority == 10_000_000  # Very high - should be last
        assert component.config.static_files_path == temp_static_dir

    def test_init_custom_config(self, temp_static_dir):
        """Test component initialization with custom config."""
        config = StaticFilesComponentConfig(
            static_files_path=temp_static_dir, mount_point="/assets"
        )
        component = StaticFilesServerComponent(config=config)

        assert component.config.mount_point == "/assets"

    def test_configure_no_op(self, app, orchestrator, temp_static_dir):
        """Test that configure is a no-op."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)

        # Should not raise or modify anything
        component.configure(app, orchestrator)

    def test_register_routes_nonexistent_dir_raises(self, app, orchestrator):
        """Test that registering routes with nonexistent directory raises error."""
        import tempfile
        import os
        
        # Create a path that definitely doesn't exist on any OS
        with tempfile.TemporaryDirectory() as temp_dir:
            nonexistent_path = os.path.join(temp_dir, "definitely_does_not_exist_12345")
            config = StaticFilesComponentConfig(static_files_path=nonexistent_path)
            component = StaticFilesServerComponent(config=config)

            with pytest.raises(ValueError, match="does not exist"):
                component.register_routes(app, orchestrator)

    @pytest.mark.asyncio
    async def test_on_startup_async_no_op(self, orchestrator, temp_static_dir):
        """Test that on_startup_async is a no-op."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)

        # Should not raise
        await component.on_startup_async(orchestrator)

    @pytest.mark.asyncio
    async def test_on_shutdown_async_no_op(self, orchestrator, temp_static_dir):
        """Test that on_shutdown_async is a no-op."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)

        # Should not raise
        await component.on_shutdown_async(orchestrator)

    def test_get_dependencies_none(self, temp_static_dir):
        """Test that component has no dependencies."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)

        deps = component.get_dependencies()

        assert deps == []


class TestStaticFilesServing:
    """Tests for static file serving functionality."""

    @pytest.mark.asyncio
    async def test_serve_index_html(self, app, orchestrator, temp_static_dir):
        """Test serving index.html."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/index.html")

            assert response.status_code == 200
            assert "Home" in response.text

    @pytest.mark.asyncio
    async def test_serve_css_file(self, app, orchestrator, temp_static_dir):
        """Test serving CSS file."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/styles.css")

            assert response.status_code == 200
            assert "color: red" in response.text
            assert response.headers["content-type"].startswith("text/css")

    @pytest.mark.asyncio
    async def test_serve_subdirectory_file(self, app, orchestrator, temp_static_dir):
        """Test serving file from subdirectory."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/assets/logo.png")

            assert response.status_code == 200
            assert response.content == b"fake-png-data"

    @pytest.mark.asyncio
    async def test_serve_root_returns_index(self, app, orchestrator, temp_static_dir):
        """Test that root path serves index.html."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/")

            assert response.status_code == 200
            assert "Home" in response.text

    @pytest.mark.asyncio
    async def test_nonexistent_file_returns_404(
        self, app, orchestrator, temp_static_dir
    ):
        """Test that nonexistent file returns 404."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/nonexistent.html")

            assert response.status_code == 404


class TestStaticFilesIntegration:
    """Integration tests for static files component."""

    @pytest.mark.asyncio
    async def test_static_files_with_api_routes(
        self, app, orchestrator, temp_static_dir
    ):
        """Test that static files work alongside API routes."""

        # Add an API route
        @app.get("/api/test")
        async def api_test():
            return {"api": "works"}

        # Add static files component
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # API route should work
            api_response = await client.get("/api/test")
            assert api_response.status_code == 200
            assert api_response.json() == {"api": "works"}

            # Static file should work
            static_response = await client.get("/index.html")
            assert static_response.status_code == 200
            assert "Home" in static_response.text

    @pytest.mark.asyncio
    async def test_multiple_html_files(self, app, orchestrator, temp_static_dir):
        """Test serving multiple HTML files."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Index page
            index_resp = await client.get("/index.html")
            assert index_resp.status_code == 200
            assert "Home" in index_resp.text

            # About page
            about_resp = await client.get("/about.html")
            assert about_resp.status_code == 200
            assert "About" in about_resp.text

    @pytest.mark.asyncio
    async def test_content_types(self, app, orchestrator, temp_static_dir):
        """Test that correct content types are set."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # HTML file
            html_resp = await client.get("/index.html")
            assert html_resp.headers["content-type"].startswith("text/html")

            # CSS file
            css_resp = await client.get("/styles.css")
            assert css_resp.headers["content-type"].startswith("text/css")

    @pytest.mark.asyncio
    async def test_spa_fallback_to_index(self, app, orchestrator, temp_static_dir):
        """Test that the html=True setting enables SPA-style routing."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Root should serve index.html
            root_resp = await client.get("/")
            assert root_resp.status_code == 200
            assert "Home" in root_resp.text


class TestStaticFilesEdgeCases:
    """Edge case tests for static files component."""

    @pytest.mark.asyncio
    async def test_with_string_path(self, app, orchestrator, temp_static_dir):
        """Test that component works with string path."""
        config = StaticFilesComponentConfig(static_files_path=str(temp_static_dir))
        component = StaticFilesServerComponent(config=config)
        component.register_routes(app, orchestrator)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/index.html")
            assert response.status_code == 200

    def test_priority_is_very_high(self, temp_static_dir):
        """Test that static files component has very high priority."""
        config = StaticFilesComponentConfig(static_files_path=temp_static_dir)
        component = StaticFilesServerComponent(config=config)

        # Priority should be very high to ensure it's registered last
        assert component.priority > 1000
        assert component.priority == 10_000_000
