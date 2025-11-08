"""Tests for the /themes API endpoints."""

import pytest
from fastapi import HTTPException

from flock.api import themes


@pytest.mark.asyncio
async def test_list_themes_returns_sorted_names(monkeypatch, tmp_path):
    """list_themes should return sorted theme names from the directory."""

    (tmp_path / "b-theme.toml").write_text("[meta]\nname = 'B'")
    (tmp_path / "a-theme.toml").write_text("[meta]\nname = 'A'")
    (tmp_path / "ignore.txt").write_text("not a toml theme")

    monkeypatch.setattr(themes, "THEMES_DIR", tmp_path)

    result = await themes.list_themes()

    assert result == {"themes": ["a-theme", "b-theme"]}


@pytest.mark.asyncio
async def test_list_themes_handles_missing_directory(monkeypatch, tmp_path):
    """Missing theme directory should return empty list instead of error."""

    missing_dir = tmp_path / "does-not-exist"
    monkeypatch.setattr(themes, "THEMES_DIR", missing_dir)

    result = await themes.list_themes()

    assert result == {"themes": []}


@pytest.mark.asyncio
async def test_get_theme_returns_theme_payload(monkeypatch, tmp_path):
    """get_theme should load the TOML theme and return its data."""

    theme_file = tmp_path / "solarized.toml"
    theme_file.write_text(
        """
[colors]
background = "#002b36"
foreground = "#839496"
""".strip()
    )

    monkeypatch.setattr(themes, "THEMES_DIR", tmp_path)

    result = await themes.get_theme("solarized")

    assert result["name"] == "solarized"
    assert result["data"]["colors"]["background"] == "#002b36"


@pytest.mark.asyncio
async def test_get_theme_missing_file_raises_404(monkeypatch, tmp_path):
    """Requesting a non-existent theme should raise a 404 HTTPException."""

    monkeypatch.setattr(themes, "THEMES_DIR", tmp_path)

    with pytest.raises(HTTPException) as excinfo:
        await themes.get_theme("ghost-theme")

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_theme_invalid_toml_raises_500(monkeypatch, tmp_path):
    """Invalid TOML content should be surfaced as a 500 HTTPException."""

    bad_file = tmp_path / "broken.toml"
    bad_file.write_text("[colors\nbackground = '#000000'")

    monkeypatch.setattr(themes, "THEMES_DIR", tmp_path)

    with pytest.raises(HTTPException) as excinfo:
        await themes.get_theme("broken")

    assert excinfo.value.status_code == 500


@pytest.mark.asyncio
async def test_list_themes_propagates_unexpected_errors(monkeypatch):
    """Unexpected filesystem errors should raise a 500 HTTPException."""

    class ExplodingPath:
        def exists(self) -> bool:
            return True

        def glob(self, pattern: str):  # pragma: no cover - not executed fully
            raise RuntimeError("boom")

    monkeypatch.setattr(themes, "THEMES_DIR", ExplodingPath())

    with pytest.raises(HTTPException) as excinfo:
        await themes.list_themes()

    assert excinfo.value.status_code == 500
