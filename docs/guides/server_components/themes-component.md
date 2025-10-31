---
title: ThemesComponent
description: Documentation for the ThemesComponent
tags:
  - themes
  - endpoints
search:
  boost: 0.1
---
# ThemesComponent

The `ThemesComponent` serves theme configuration files for the Flock dashboard, enabling customization of the UI appearance.

## Overview

This component provides HTTP endpoints for listing available themes and retrieving theme configurations in TOML format.

## Configuration

### ThemesComponentConfig

**Fields:**
- `prefix` (str, default: `"/plugin/"`) - URL prefix for endpoints
- `tags` (list[str], default: `["Theme files"]`) - OpenAPI tags

## Usage

```python
from flock import Flock
from flock.components.server import (
    ThemesComponent,
    ThemesComponentConfig
)

themes = ThemesComponent(
    config=ThemesComponentConfig(
        prefix="/api/themes",
        tags=["Themes", "UI"]
    )
)

await flock.serve(components=[themes])
```

## Endpoints

### GET /plugin/themes

List all available theme names.

**Response:**
```json
{
  "themes": [
    "default",
    "dark",
    "light",
    "custom"
  ]
}
```

### GET /plugin/themes/{theme_name}

Get theme configuration in TOML format.

**Response:**
```toml
[theme]
name = "default"
description = "Default Flock theme"

[colors]
primary = "#3B82F6"
secondary = "#10B981"
background = "#FFFFFF"
text = "#1F2937"

[typography]
font_family = "Inter, sans-serif"
font_size_base = "16px"
```

## Theme Structure

Themes are TOML files located in `src/flock/themes/`:

```toml
[theme]
name = "my-theme"
description = "Custom theme description"

[colors]
primary = "#FF6B6B"
secondary = "#4ECDC4"
background = "#1A1A1A"
surface = "#2D2D2D"
text = "#FFFFFF"
text_secondary = "#AAAAAA"

[typography]
font_family = "Roboto, sans-serif"
font_size_base = "14px"
font_size_heading = "24px"

[spacing]
unit = "8px"
```

## Best Practices

### 1. Create Custom Themes

```bash
# Create new theme file
cat > src/flock/themes/corporate.toml << EOF
[theme]
name = "corporate"
description = "Corporate brand theme"

[colors]
primary = "#0066CC"
secondary = "#00AA66"
background = "#FFFFFF"
text = "#333333"
EOF
```

### 2. Use in Dashboard

```typescript
// Frontend fetches theme
const response = await fetch('/plugin/themes/corporate');
const themeConfig = await response.text();
const theme = toml.parse(themeConfig);

// Apply theme colors
document.documentElement.style.setProperty('--primary-color', theme.colors.primary);
```

### 3. List Available Themes

```python
# Let users choose themes
response = await client.get('/plugin/themes')
themes = response.json()['themes']

for theme_name in themes:
    print(f"Available theme: {theme_name}")
```

## Component Properties

- **Name:** `themes`
- **Priority:** `2`
- **Default Directory:** `src/flock/themes/`

## Example

See: **[examples/09-server-components/10_themes_component.py](../../../examples/09-server-components/10_themes_component.py)**

## Troubleshooting

### Theme not found

**Problem:** 404 when fetching theme

**Solution:** Verify theme file exists in themes directory

```python
from pathlib import Path

themes_dir = Path("src/flock/themes")
available_themes = [f.stem for f in themes_dir.glob("*.toml")]
print(f"Available themes: {available_themes}")
```

### Invalid TOML format

**Problem:** Theme file cannot be parsed

**Solution:** Validate TOML syntax

```bash
# Validate TOML file
python -c "import toml; toml.load('src/flock/themes/my-theme.toml')"
```
