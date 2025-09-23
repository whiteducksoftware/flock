from __future__ import annotations

import re

###########################
#  Low–level colour utils #
###########################

_HEX_RE = re.compile(r"^#?([0-9a-f]{6})$", re.I)

def _hex_to_rgb(hex_str: str) -> tuple[int, int, int] | None:
    if hex_str is None:
        return None
    # Clean the string - remove any leading/trailing whitespace
    hex_str = hex_str.strip()
    m = _HEX_RE.match(hex_str)
    if not m:
        return None
    h = m.group(1)
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[misc]

def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

def _rel_lum(rgb: tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = map(channel, rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def _contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    if a is None or b is None:
        return 1.0  # Default value if invalid colors provided
    try:
        la, lb = _rel_lum(a), _rel_lum(b)
        darker, lighter = sorted((la, lb))
        return (lighter + 0.05) / (darker + 0.05)
    except (TypeError, ValueError, ZeroDivisionError) as e:
        print(f"Error calculating contrast: {e}")
        return 1.0  # Default value on error

def _mix(rgb: tuple[int, int, int], other: tuple[int, int, int], pct: float) -> tuple[int, int, int]:
    if rgb is None or other is None:
        # Return a fallback color if either input is None
        return (128, 128, 128)  # Default to gray
    try:
        return tuple(int(rgb[i] * (1 - pct) + other[i] * pct) for i in range(3))
    except (TypeError, IndexError) as e:
        print(f"Error mixing colors: {e}")
        return (128, 128, 128)  # Default to gray

def _rgba(rgb: tuple[int, int, int], alpha: float) -> str:
    if rgb is None:
        rgb = (128, 128, 128)  # Default gray if rgb is None
    return f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {alpha})"

########################################
#  Theme → Pico-CSS conversion engine  #
########################################

AccentOrder = ["blue", "cyan", "magenta", "green", "yellow", "red"]

def _theme_color(theme: dict, group: str, name: str) -> tuple[int, int, int] | None:
    try:
        raw = (
            theme.get("colors", {})
                .get(group, {},)
                .get(name)
        )
        return _hex_to_rgb(raw) if raw else None
    except (TypeError, AttributeError) as e:
        print(f"Error extracting color {group}.{name}: {e}")
        return None

def _order_colors(theme: dict, color_to_compare_to: tuple[int, int, int]) -> list[tuple[int, int, int]]:
    colors = []

    # Extract all colors from the theme recursively
    def extract_colors(data):
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and value.startswith('#'):
                    rgb = _hex_to_rgb(value)
                    if rgb:
                        colors.append(rgb)
                else:
                    extract_colors(value)
        elif isinstance(data, list):
            for item in data:
                extract_colors(item)

    # Start extraction from the root of the theme
    extract_colors(theme)

    # Sort colors by contrast with color_to_compare_to, highest contrast first
    colors.sort(key=lambda c: _contrast(c, color_to_compare_to), reverse=True)

    return colors

def _best_contrast(
    candidates: list[tuple[int, int, int]],
    bg: tuple[int, int, int],
    min_ratio: float = 4.5,
) -> tuple[int, int, int]:
    if not candidates:
        # Instead of raising an exception, return a fallback color
        # Use white or black depending on the background
        return (255, 255, 255) if sum(bg) < 384 else (0, 0, 0)
    best = max(candidates, key=lambda c: _contrast(c, bg))
    if _contrast(best, bg) >= min_ratio:
        return best
    return best  # return highest available even if below threshold

def alacritty_to_pico(theme: dict) -> dict[str, str]:
    css: dict[str, str] = {}

    # 1  Main surface colours
    fixed_background = _theme_color(theme, "primary", "background") or (0, 0, 0)
    fixed_foreground = _theme_color(theme, "primary", "foreground") or (255, 255, 255)

    fixed_background2 = _theme_color(theme, "selection", "background") or (0, 0, 0)
    # Try theme's own foreground first, then fall back to palette extremes
    # fg_candidates = [
    #     _theme_color(theme, "primary", "foreground"),
    #     _theme_color(theme, "normal", "white"),
    #     _theme_color(theme, "bright", "white"),
    #     _theme_color(theme, "normal", "black"),
    #     _theme_color(theme, "bright", "black"),
    # ]
    # fg = _best_contrast([c for c in fg_candidates if c], bg)

    css["--pico-background-color"] = _rgb_to_hex(fixed_background)
    css["--pico-color"] = _rgb_to_hex(fixed_foreground)

    # 2  Pick an accent colour that stands out
    accent = None
    for shade in ("normal", "bright"):
        for name in AccentOrder:
            c = _theme_color(theme, shade, name)
            if c and _contrast(c, fixed_background) >= 3:
                accent = c
                break
        if accent:
            break
    accent = accent or fixed_foreground  # worst case

    accent_hover = _mix(accent, (255, 255, 255), 0.15)              # lighten 15 %
    accent_active = _mix(accent, (0, 0, 0), 0.15)                   # darken 15 %
    accent_focus = _rgba(accent, 0.25)                              # 25 % overlay
    accent_inv = _best_contrast([fixed_foreground, fixed_background, (255, 255, 255), (0, 0, 0)], accent, 4.5)

    css["--pico-primary"] = _rgb_to_hex(accent)
    css["--pico-primary-hover"] = _rgb_to_hex(accent_hover)
    css["--pico-primary-active"] = _rgb_to_hex(accent_active)
    css["--pico-primary-focus"] = accent_focus
    css["--pico-primary-inverse"] = _rgb_to_hex(accent_inv)

    # 3  Secondary accent = next colour in queue with sufficient contrast
    sec = None
    for name in AccentOrder:
        if sec is None and _hex_to_rgb(css["--pico-primary"]) != _theme_color(theme, "normal", name):
            for shade in ("normal", "bright"):
                c = _theme_color(theme, shade, name)
                if c and _contrast(c, fixed_background) >= 3:
                    sec = c
                    break
    sec = sec or _mix(accent, (255, 255, 255), 0.25)

    css["--pico-secondary"] = _rgb_to_hex(sec)
    css["--pico-secondary-hover"] = _rgb_to_hex(_mix(sec, (255, 255, 255), 0.15))
    css["--pico-secondary-focus"] = _rgba(sec, 0.25)
    css["--pico-secondary-active"] = _rgb_to_hex(sec)
    css["--pico-secondary-inverse"] = _rgb_to_hex(_best_contrast([fixed_foreground, fixed_background], sec, 4.5))

    # 4  Headings inherit the accent spectrum
    css["--pico-h1-color"] = css["--pico-primary"]
    css["--pico-h2-color"] = css["--pico-secondary"]
    css["--pico-h3-color"] = css["--pico-color"]  # body colour

    # 5  Muted text & borders use the least-contrasty greys we can still read
    grey_candidates = [
        _theme_color(theme, "bright", "black"),
        _theme_color(theme, "normal", "black"),
        _theme_color(theme, "bright", "white"),
        _theme_color(theme, "normal", "white"),
    ]
    muted = _best_contrast([c for c in grey_candidates if c], fixed_background, 3)
    css["--pico-muted-color"] = _rgb_to_hex(muted)
    css["--pico-border-color"] = _rgb_to_hex(_mix(muted, fixed_background, 0.5))
    css["--pico-muted-border-color"] = css["--pico-border-color"]

    # 6  Cards, selections, cursor, code — pick safe defaults
    css["--pico-card-background-color"] = css["--pico-background-color"]
    css["--pico-card-sectioning-background-color"] = _rgb_to_hex(fixed_background2)
    css["--pico-card-border-color"] = css["--pico-border-color"]

    sel_bg = _theme_color(theme, "selection", "background") or _mix(fixed_background, fixed_foreground, 0.20)
    sel_fg = _best_contrast([fixed_foreground, muted, accent, sec], sel_bg, 4.5)
    css["--pico-selection-background-color"] = _rgb_to_hex(sel_bg)
    css["--pico-selection-color"] = _rgb_to_hex(sel_fg)

    cur_bg = _theme_color(theme, "cursor", "cursor") or sel_bg

    # Try theme's own foreground first, then fall back to palette extremes
    fg_cur_candidates = [
        _theme_color(theme, "primary", "foreground"),
        _theme_color(theme, "normal", "white"),
        _theme_color(theme, "bright", "white"),
        _theme_color(theme, "normal", "blue"),
        _theme_color(theme, "bright", "blue"),
        _theme_color(theme, "normal", "cyan"),
        _theme_color(theme, "bright", "cyan"),
        _theme_color(theme, "normal", "magenta"),
        _theme_color(theme, "bright", "magenta"),
        _theme_color(theme, "normal", "green"),
        _theme_color(theme, "bright", "green"),
        _theme_color(theme, "normal", "yellow"),
        _theme_color(theme, "bright", "yellow"),
        _theme_color(theme, "normal", "red"),
        _theme_color(theme, "bright", "red"),
        _theme_color(theme, "normal", "black"),
        _theme_color(theme, "bright", "black"),
    ]
    cur_fg = _best_contrast([c for c in fg_cur_candidates if c], cur_bg)

    css["--pico-code-background-color"] = _rgb_to_hex(cur_bg)
    css["--pico-code-color"] = _rgb_to_hex(cur_fg)

    # 7  Form elements and buttons reuse the existing tokens
    css["--pico-form-element-background-color"] = css["--pico-background-color"]
    css["--pico-form-element-border-color"] = css["--pico-border-color"]
    css["--pico-form-element-color"] = css["--pico-color"]
    css["--pico-form-element-focus-color"] = css["--pico-primary-hover"]
    css["--pico-form-element-placeholder-color"] = css["--pico-muted-color"]
    css["--pico-form-element-active-border-color"] = css["--pico-primary"]
    css["--pico-form-element-active-background-color"] = css["--pico-selection-background-color"]
    css["--pico-form-element-disabled-background-color"] = _rgb_to_hex(_mix(fixed_background, fixed_foreground, 0.1))
    css["--pico-form-element-disabled-border-color"] = css["--pico-border-color"]
    css["--pico-form-element-invalid-border-color"] = _rgb_to_hex(_theme_color(theme, "normal", "red") or accent_active)
    css["--pico-form-element-invalid-focus-color"] = _rgb_to_hex(_theme_color(theme, "bright", "red") or accent_hover)

    # 8  Buttons follow primary palette by default
    css["--pico-button-base-background-color"] = css["--pico-primary"]
    css["--pico-button-base-color"] = css["--pico-primary-inverse"]
    css["--pico-button-hover-background-color"] = css["--pico-primary-hover"]
    css["--pico-button-hover-color"] = css["--pico-primary-inverse"]

    # 9  Semantic markup helpers
    yellow = _theme_color(theme, "normal", "yellow") or _mix(accent, (255, 255, 0), 0.5)
    css["--pico-mark-background-color"] = _rgba(yellow, 0.2)
    css["--pico-mark-color"] = css["--pico-color"]
    css["--pico-ins-color"] = _rgb_to_hex(_theme_color(theme, "normal", "green") or accent)
    css["--pico-del-color"] = _rgb_to_hex(_theme_color(theme, "normal", "red") or accent_active)

    # 10  Contrast helpers
    css["--pico-contrast"] = css["--pico-color"]
    css["--pico-contrast-inverse"] = css["--pico-primary-inverse"]

    return css

if __name__ == "__main__":
    import pathlib
    import sys

    try:
        import toml
        import uvicorn
        from fastapi import FastAPI, Request
        from fastapi.responses import HTMLResponse
        from fastapi.templating import Jinja2Templates
    except ImportError as e:
        print(f"Error: Required module not found: {e}")
        print("Please install required packages: pip install toml fastapi uvicorn jinja2")
        sys.exit(1)

    # Find themes directory
    current_dir = pathlib.Path(__file__).parent
    themes_dir = current_dir.parent.parent / 'themes'

    # Check if themes directory exists
    if not themes_dir.exists():
        print(f"Error: Themes directory not found at {themes_dir}")
        print(f"Current directory is {current_dir}")
        sys.exit(1)

    # Get list of all theme files
    theme_files = list(themes_dir.glob('*.toml'))

    if not theme_files:
        print(f"Error: No theme files found in {themes_dir}")
        sys.exit(1)

    # Make sure alabaster is included
    alabaster_path = themes_dir / 'alabaster.toml'
    if alabaster_path not in theme_files and alabaster_path.exists():
        theme_files.append(alabaster_path)

    # Load a few random themes plus alabaster
    selected_themes = theme_files
    if alabaster_path.exists() and alabaster_path not in selected_themes:
        selected_themes.append(alabaster_path)

    # Dictionary to store theme data
    themes = {}

    # Load each theme
    for theme_path in selected_themes:
        try:
            # Read the file as text to handle whitespace issues
            with open(theme_path) as f:
                content = f.read()

            # Remove leading/trailing whitespace from each line
            cleaned_content = '\n'.join(line.rstrip() for line in content.splitlines())

            # Parse using StringIO
            from io import StringIO
            theme_data = toml.load(StringIO(cleaned_content))
            themes[theme_path.stem] = theme_data
        except Exception as e:
            print(f"Error loading {theme_path.name}: {e}")

    # Check if any themes were successfully loaded
    if not themes:
        print("Error: No themes could be loaded successfully.")
        sys.exit(1)

    # Create a FastAPI application
    app = FastAPI(title="Theme Mapper")

    # Create template directory
    template_dir = current_dir / "templates"
    try:
        template_dir.mkdir(exist_ok=True)
    except Exception as e:
        print(f"Error creating template directory: {e}")
        sys.exit(1)

    # Create and write template file
    template_path = template_dir / "theme_mapper.html"
    template_content = '''
    <!DOCTYPE html>
    <html lang="en" data-theme="light">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Theme Mapper</title>
        <!-- Use Pico CSS only -->
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@1/css/pico.min.css">
        <style>
            {{ css_vars | safe }}

            /* Only use Pico CSS classes and variables */
           
            .color-sample {
                height: 20px;
                width: 100%;
                border-radius: 4px;
                margin-bottom: 5px;
            }
            .theme-selector {
                position: fixed;
                top: 10px;
                right: 10px;
                z-index: 100;
                background-color: var(--pico-card-background-color);
                padding: 10px;
                border-radius: 8px;
                border: 1px solid var(--pico-border-color);
            }
            article {
                margin-bottom: 1rem;
            }
            .contrast-table td {
                padding: 5px;
                text-align: center;
            }
            .good-contrast {
                background-color: var(--pico-ins-color);
                color: var(--pico-background-color);
            }
            .bad-contrast {
                background-color: var(--pico-del-color);
                color: var(--pico-background-color);
            }
            
            /* New: give demo content cards a themed background so text always contrasts */
            article {
                background-color: var(--pico-card-sectioning-background-color);
                border: 1px solid var(--pico-card-border-color);
                padding: 1rem;
                border-radius: 8px;
            }
            /* New: background for the two grid columns */
            .grid > div {
                background-color: var(--pico-card-background-color);
                padding: 1rem;
                border-radius: 8px;
            }
            
            /* Override any non-pico CSS variables */
            body {
                background-color: var(--pico-background-color);
                color: var(--pico-color);
            }
            a {
                color: var(--pico-primary);
            }
            a:hover {
                color: var(--pico-primary-hover);
            }
            h1 {
                color: var(--pico-h1-color);
            }
            h2 {
                color: var(--pico-h2-color);
            }
            h3 {
                color: var(--pico-h3-color);
            }
            mark {
                background-color: var(--pico-mark-background-color);
                color: var(--pico-mark-color);
            }
            ins {
                color: var(--pico-ins-color);
            }
            del {
                color: var(--pico-del-color);
            }
            code {
                background-color: var(--pico-code-background-color);
                color: var(--pico-code-color);
            }
            button, input[type="submit"], input[type="button"] {
                background-color: var(--pico-button-base-background-color);
                color: var(--pico-button-base-color);
                border-color: var(--pico-button-base-background-color);
            }
            button:hover, input[type="submit"]:hover, input[type="button"]:hover {
                background-color: var(--pico-button-hover-background-color);
                color: var(--pico-button-hover-color);
                border-color: var(--pico-button-hover-background-color);
            }
            button.secondary, input[type="submit"].secondary, input[type="button"].secondary {
                background-color: var(--pico-secondary);
                color: var(--pico-secondary-inverse);
                border-color: var(--pico-secondary);
            }
            button.secondary:hover, input[type="submit"].secondary:hover, input[type="button"].secondary:hover {
                background-color: var(--pico-secondary-hover);
                color: var(--pico-secondary-inverse);
                border-color: var(--pico-secondary-hover);
            }
            button.contrast, input[type="submit"].contrast, input[type="button"].contrast {
                background-color: var(--pico-contrast);
                color: var(--pico-contrast-inverse);
                border-color: var(--pico-contrast);
            }
            /* Improve grid columns on wider screens */
            @media (min-width: 768px) {
                .grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
                    gap: 2rem;
                }
            }
            /* Ensure container can grow a little wider than Pico default */
            .container {
                max-width: 90rem; /* ~1440px */
            }
            /* Ensure tables use full-strength text colour */
            table th,
            table td {
                color: var(--pico-color);
                opacity: 1; /* override Pico's default fade */
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="theme-selector">
                <label for="theme-select">Select Theme:</label>
                <select id="theme-select" onchange="window.location.href='/?theme=' + this.value">
                    {% for theme_name in themes %}
                    <option value="{{ theme_name }}" {% if theme_name == current_theme %}selected{% endif %}>{{ theme_name }}</option>
                    {% endfor %}
                </select>
            </div>
            
            <h1>Theme Mapper: {{ current_theme }}</h1>
            
            <div class="grid">
                <div>
                    <h2>UI Elements</h2>
                    <article>
                        <h3>Headings and Text</h3>
                        <h1>Heading 1</h1>
                        <h2>Heading 2</h2>
                        <h3>Heading 3</h3>
                        <p>Normal paragraph text. <a href="#">This is a link</a>. <mark>This is marked text</mark>.</p>
                        <p><small>This is small text</small></p>
                        <p><ins>This is inserted text</ins> and <del>this is deleted text</del>.</p>
                        <blockquote>
                            This is a blockquote with <cite>a citation</cite>.
                        </blockquote>
                        <code>This is inline code</code>
                        <pre><code>// This is a code block
function example() {
  return "Hello World";
}</code></pre>
                    </article>
                    
                    <article>
                        <h3>Buttons</h3>
                        <button>Default Button</button>
                        <button class="secondary">Secondary Button</button>
                        <button class="contrast">Contrast Button</button>
                    </article>
                    
                    <article>
                        <h3>Form Elements</h3>
                        <form>
                            <label for="text">Text Input</label>
                            <input type="text" id="text" placeholder="Text input">
                            
                            <label for="select">Select</label>
                            <select id="select">
                                <option>Option 1</option>
                                <option>Option 2</option>
                            </select>
                            
                            <label for="textarea">Textarea</label>
                            <textarea id="textarea" placeholder="Textarea"></textarea>
                            
                            <label for="invalid" aria-invalid="true">Invalid Input</label>
                            <input type="text" id="invalid" aria-invalid="true" placeholder="Invalid input">
                            
                            <fieldset>
                                <legend>Checkboxes</legend>
                                <label>
                                    <input type="checkbox" checked>
                                    Checkbox 1
                                </label>
                                <label>
                                    <input type="checkbox">
                                    Checkbox 2
                                </label>
                            </fieldset>
                            
                            <fieldset>
                                <legend>Radio Buttons</legend>
                                <label>
                                    <input type="radio" name="radio" checked>
                                    Radio 1
                                </label>
                                <label>
                                    <input type="radio" name="radio">
                                    Radio 2
                                </label>
                            </fieldset>
                        </form>
                    </article>
                </div>
                
                <div>
                    <h2>Theme Color Mapping</h2>
                    <article>
                        <h3>Main Colors</h3>
                        <div class="grid">
                            {% for color_name, color_value in main_colors %}
                            <div>
                                <div class="color-sample" style="background-color: {{ color_value }};"></div>
                                <small>{{ color_name }}<br>{{ color_value }}</small>
                            </div>
                            {% endfor %}
                        </div>
                    </article>
                    
                    <article>
                        <h3>All Pico CSS Variables</h3>
                        <div style="max-height: 300px; overflow-y: auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Variable</th>
                                        <th>Value</th>
                                        <th>Sample</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for var_name, var_value in all_vars %}
                                    <tr>
                                        <td>{{ var_name }}</td>
                                        <td>{{ var_value }}</td>
                                        <td>
                                            {% if var_value.startswith('#') or var_value.startswith('rgb') %}
                                            <div class="color-sample" style="background-color: {{ var_value }};"></div>
                                            {% endif %}
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </article>
                    
                    <article>
                        <h3>Color Contrast Checks</h3>
                        <table class="contrast-table">
                            <thead>
                                <tr>
                                    <th>Foreground</th>
                                    <th>Background</th>
                                    <th>Contrast</th>
                                    <th>WCAG AA</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for check in contrast_checks %}
                                <tr>
                                    <td>{{ check.fg_name }}</td>
                                    <td>{{ check.bg_name }}</td>
                                    <td>{{ check.contrast }}</td>
                                    <td class="{% if check.passes %}good-contrast{% else %}bad-contrast{% endif %}">
                                        {{ "Pass" if check.passes else "Fail" }}
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </article>

                    <article>
                        <h3>Original Theme Colors</h3>
                        <div style="max-height: 300px; overflow-y: auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Group</th>
                                        <th>Name</th>
                                        <th>Value</th>
                                        <th>Sample</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for group, names in original_colors.items() %}
                                        {% for name, value in names.items() %}
                                        <tr>
                                            <td>{{ group }}</td>
                                            <td>{{ name }}</td>
                                            <td>{{ value }}</td>
                                            <td><div class="color-sample" style="background-color: {{ value }};"></div></td>
                                        </tr>
                                        {% endfor %}
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </article>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

    try:
        with open(template_path, 'w') as f:
            f.write(template_content)
    except Exception as e:
        print(f"Error writing template file: {e}")
        sys.exit(1)

    # Setup Jinja2 templates
    try:
        templates = Jinja2Templates(directory=str(template_dir))
    except Exception as e:
        print(f"Error setting up Jinja2 templates: {e}")
        sys.exit(1)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, theme: str | None = None):
        try:
            # Get requested theme name from query parameter
            if theme is None or theme not in themes:
                # If no theme is provided or theme is invalid, default to alabaster or first theme
                theme_name = 'alabaster' if 'alabaster' in themes else next(iter(themes))
            else:
                # Use the requested theme directly
                theme_name = theme

            # Get the theme data
            theme_data = themes[theme_name]

            # Convert theme to pico css variables
            css_vars = alacritty_to_pico(theme_data)

            # Format css variables for the style tag - this is important for proper application of the theme
            css_vars_str = ":root {\n" + "\n".join([f"  {k}: {v};" for k, v in css_vars.items()]) + "\n}"

            # Prepare main colors for display
            main_colors = [
                ("Background", css_vars["--pico-background-color"]),
                ("Text", css_vars["--pico-color"]),
                ("Primary", css_vars["--pico-primary"]),
                ("Secondary", css_vars["--pico-secondary"]),
                ("Muted", css_vars["--pico-muted-color"]),
            ]

            # Extract original colors from theme
            original_colors = {}
            if "colors" in theme_data:
                for group, colors in theme_data["colors"].items():
                    if isinstance(colors, dict):
                        group_colors = {}
                        for name, value in colors.items():
                            if isinstance(value, str):
                                group_colors[name] = value.strip()
                        if group_colors:
                            original_colors[group] = group_colors

            # Check contrasts
            contrast_checks = []

            # Define relevant foreground/background variable pairs to evaluate
            contrast_pairs = [
                ("Text", "--pico-color", "Background", "--pico-background-color"),
                ("Primary", "--pico-primary", "Background", "--pico-background-color"),
                ("Secondary", "--pico-secondary", "Background", "--pico-background-color"),
                ("Muted", "--pico-muted-color", "Background", "--pico-background-color"),
                (
                    "Button Text",
                    "--pico-button-base-color",
                    "Button Background",
                    "--pico-button-base-background-color",
                ),
                (
                    "Secondary Btn Text",
                    "--pico-secondary-inverse",
                    "Secondary",
                    "--pico-secondary",
                ),
                (
                    "Contrast Text",
                    "--pico-contrast-inverse",
                    "Contrast Background",
                    "--pico-contrast",
                ),
                (
                    "Code",
                    "--pico-code-color",
                    "Code Background",
                    "--pico-code-background-color",
                ),
            ]

            for fg_name, fg_var, bg_name, bg_var in contrast_pairs:
                fg_hex = css_vars.get(fg_var)
                bg_hex = css_vars.get(bg_var)
                if not fg_hex or not bg_hex:
                    continue
                fg_rgb = _hex_to_rgb(fg_hex)
                bg_rgb = _hex_to_rgb(bg_hex)
                if fg_rgb is None or bg_rgb is None:
                    continue
                ratio = _contrast(fg_rgb, bg_rgb)
                contrast_checks.append({
                    "fg_name": fg_name,
                    "bg_name": bg_name,
                    "contrast": f"{ratio:.2f}",
                    "passes": ratio >= 4.5,
                })

            return templates.TemplateResponse(request, "theme_mapper.html",
                {
                    "request": request,
                    "css_vars": css_vars_str,
                    "themes": themes.keys(),
                    "current_theme": theme_name,
                    "main_colors": main_colors,
                    "all_vars": list(css_vars.items()),
                    "original_colors": original_colors,
                    "contrast_checks": contrast_checks
                }
            )
        except Exception as e:
            print(f"Error handling request: {e}")
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(f"Error processing theme: {e!s}", status_code=500)

    # Add a more robust error handler for the application
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        print(f"Global exception handler caught: {exc}")
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(f"Internal server error: {exc!s}", status_code=500)

    # Run the app
    print("Starting Theme Mapper web app...")
    print(f"Current directory: {current_dir}")
    print(f"Template directory: {template_dir} (exists: {template_dir.exists()})")
    print(f"Themes directory: {themes_dir} (exists: {themes_dir.exists()})")
    print(f"Loaded {len(themes)} themes: {', '.join(themes.keys())}")

    try:
        uvicorn.run(app, host="127.0.0.1", port=5050)
    except Exception as e:
        print(f"Error starting the web server: {e}")
        sys.exit(1)
