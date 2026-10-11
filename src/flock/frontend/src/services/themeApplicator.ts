/**
 * Theme Applicator
 *
 * The dashboard has two built-in themes, Graphite (default) and Paper, set by
 * `data-theme` on the root element (styles/tokens.css). A terminal theme
 * overrides the same tokens: its colors are mapped onto them, surfaces and
 * lines are mixed from its background and foreground, and the text tokens are
 * checked for a contrast of 4.5:1 against --surface.
 *
 * Spec: docs/internal/design-system/README.md (Tokens, terminal themes).
 */

import { TerminalTheme } from '../types/theme';
import { fetchTheme } from './themeService';

export type BuiltInTheme = 'graphite' | 'paper';

export const BUILT_IN_THEMES: BuiltInTheme[] = ['graphite', 'paper'];

/** Every token a terminal theme sets; a built-in theme removes them all. */
export const THEME_TOKENS = [
  '--bg',
  '--board',
  '--dot',
  '--surface',
  '--surface-2',
  '--surface-3',
  '--line',
  '--line-2',
  '--text',
  '--text-2',
  '--text-3',
  '--invert',
  '--on-invert',
  '--signal',
  '--signal-ink',
  '--signal-soft',
  '--sure',
  '--sure-ink',
  '--sure-soft',
  '--error',
  '--error-ink',
  '--error-soft',
  '--on-signal',
  '--on-sure',
  '--on-error',
  '--hatch',
  '--scrim',
] as const;

export type ThemeToken = (typeof THEME_TOKENS)[number];

/** The text tokens that must reach MIN_CONTRAST on --surface. */
const TEXT_TOKENS: ThemeToken[] = [
  '--text',
  '--text-2',
  '--text-3',
  '--signal-ink',
  '--sure-ink',
  '--error-ink',
];

export const MIN_CONTRAST = 4.5;

type Rgb = [number, number, number];

function parseHex(hex: string): Rgb {
  const value = hex.trim().replace(/^#/, '');
  const full =
    value.length === 3
      ? value
          .split('')
          .map((c) => c + c)
          .join('')
      : value.slice(0, 6);
  return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16)) as Rgb;
}

function toHex([r, g, b]: Rgb): string {
  return `#${[r, g, b]
    .map((c) => Math.round(Math.min(255, Math.max(0, c))).toString(16).padStart(2, '0'))
    .join('')}`;
}

/** `amount` of the way from `from` to `to` (0 = from, 1 = to). */
export function mix(from: string, to: string, amount: number): string {
  const [r1, g1, b1] = parseHex(from);
  const [r2, g2, b2] = parseHex(to);
  return toHex([r1 + (r2 - r1) * amount, g1 + (g2 - g1) * amount, b1 + (b2 - b1) * amount]);
}

function alpha(hex: string, value: number): string {
  const [r, g, b] = parseHex(hex);
  return `rgba(${r}, ${g}, ${b}, ${value})`;
}

function luminance(hex: string): number {
  const channel = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  const [r, g, b] = parseHex(hex).map(channel) as Rgb;
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG contrast ratio of two hex colors (1 to 21). */
export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

export function isLight(hex: string): boolean {
  return luminance(hex) > 0.4;
}

/** `color`, moved towards `target` in steps until it reaches MIN_CONTRAST on `ground`. */
export function legible(color: string, ground: string, target: string): string {
  let result = color;
  for (let step = 1; step <= 20 && contrastRatio(result, ground) < MIN_CONTRAST; step++) {
    result = mix(color, target, step / 20);
  }
  return result;
}

/** Text for a solid `fill`: the theme's ground or text if it reads, else black or white. */
export function onFill(fill: string, bg: string, fg: string): string {
  const candidates = [bg, fg].sort((a, b) => contrastRatio(b, fill) - contrastRatio(a, fill));
  if (contrastRatio(candidates[0]!, fill) >= MIN_CONTRAST) return candidates[0]!;
  return contrastRatio('#000000', fill) >= contrastRatio('#ffffff', fill) ? '#000000' : '#ffffff';
}

/** The tokens a terminal theme sets, as CSS values. */
export function terminalThemeTokens(theme: TerminalTheme): Record<ThemeToken, string> {
  // Theme files may pad their values (" #f7f7f7"): every color as plain hex
  const hex = (color: string) => toHex(parseHex(color));
  const { primary, normal: n, bright: b } = theme.colors;
  const normal = { yellow: hex(n.yellow), blue: hex(n.blue), red: hex(n.red) };
  const bright = { black: hex(b.black), yellow: hex(b.yellow), blue: hex(b.blue), red: hex(b.red) };
  const bg = hex(primary.background);
  const fg = hex(primary.foreground);
  const light = isLight(bg);

  // Light grounds lift their cards towards white, dark ones towards the text
  const surface = light ? mix(bg, '#ffffff', 0.85) : mix(bg, fg, 0.045);
  const surface2 = light ? mix(bg, '#ffffff', 0.3) : mix(bg, fg, 0.07);
  const surface3 = mix(bg, fg, light ? 0.05 : 0.11);

  const tokens: Record<ThemeToken, string> = {
    '--bg': bg,
    '--board': mix(bg, fg, 0.015),
    '--dot': alpha(fg, light ? 0.08 : 0.06),
    '--surface': surface,
    '--surface-2': surface2,
    '--surface-3': surface3,
    '--line': alpha(fg, light ? 0.08 : 0.075),
    '--line-2': alpha(fg, light ? 0.15 : 0.14),
    '--text': fg,
    '--text-2': mix(fg, bg, 0.25),
    '--text-3': bright.black,
    '--invert': fg,
    '--on-invert': bg,
    '--signal': normal.yellow,
    '--signal-ink': bright.yellow,
    '--signal-soft': alpha(normal.yellow, 0.13),
    '--sure': normal.blue,
    '--sure-ink': bright.blue,
    '--sure-soft': alpha(normal.blue, 0.16),
    '--error': normal.red,
    '--error-ink': bright.red,
    '--error-soft': alpha(normal.red, 0.13),
    '--on-signal': onFill(normal.yellow, bg, fg),
    '--on-sure': onFill(normal.blue, bg, fg),
    '--on-error': onFill(normal.red, bg, fg),
    '--hatch': alpha(fg, light ? 0.24 : 0.22),
    '--scrim': alpha(bg, 0.72),
  };

  // Text must stay readable on cards, whatever the palette
  const towards = light ? '#000000' : '#ffffff';
  for (const token of TEXT_TOKENS) {
    tokens[token] = legible(tokens[token], surface, token === '--text' ? towards : fg);
    if (contrastRatio(tokens[token], surface) < MIN_CONTRAST) {
      tokens[token] = legible(tokens[token], surface, towards);
    }
  }
  return tokens;
}

// The latest theme choice; a terminal theme still loading for an older one is dropped
let latestChoice = 0;

function claim(): number {
  latestChoice += 1;
  return latestChoice;
}

function clearOverrides(root: HTMLElement): void {
  for (const token of THEME_TOKENS) {
    root.style.removeProperty(token);
  }
}

/** Graphite or Paper: the tokens of tokens.css, with no override left. */
export function applyBuiltInTheme(name: BuiltInTheme, root: HTMLElement = document.documentElement): void {
  claim();
  clearOverrides(root);
  root.dataset.theme = name;
}

/** A terminal theme on top of Graphite (dark grounds) or Paper (light grounds). */
export function applyTheme(theme: TerminalTheme, root: HTMLElement = document.documentElement): void {
  claim();
  const tokens = terminalThemeTokens(theme);
  root.dataset.theme = isLight(tokens['--bg']) ? 'paper' : 'graphite';
  for (const token of THEME_TOKENS) {
    root.style.setProperty(token, tokens[token]);
  }
}

/** Back to Graphite, with every token restored. */
export function resetToDefaultTheme(root: HTMLElement = document.documentElement): void {
  applyBuiltInTheme('graphite', root);
}

/** The built-in theme a stored name stands for, if any ('default' is Graphite). */
export function builtInTheme(name: string): BuiltInTheme | null {
  if (name === 'default' || name === '') return 'graphite';
  return (BUILT_IN_THEMES as string[]).includes(name) ? (name as BuiltInTheme) : null;
}

/**
 * Apply a theme by name: a built-in one at once, a terminal theme once it is
 * loaded. Falls back to Graphite when a terminal theme cannot be loaded.
 * Returns the name of the theme now applied ('default' comes back as
 * 'graphite'), so a caller can store it, or null when another theme was chosen
 * while this one loaded (that choice stands).
 */
export async function applyThemeByName(
  name: string,
  root: HTMLElement = document.documentElement,
  load: (name: string) => Promise<TerminalTheme> = fetchTheme
): Promise<string | null> {
  const builtIn = builtInTheme(name);
  if (builtIn) {
    applyBuiltInTheme(builtIn, root);
    return builtIn;
  }
  const choice = claim();
  try {
    const theme = await load(name);
    if (choice !== latestChoice) return null;
    applyTheme(theme, root);
    return name;
  } catch (error) {
    if (choice !== latestChoice) return null;
    console.error(`[Theme] Could not load "${name}", using Graphite`, error);
    applyBuiltInTheme('graphite', root);
    return 'graphite';
  }
}

/**
 * Get a preview swatch array for a theme (8 colors)
 */
export function getThemePreview(theme: TerminalTheme): string[] {
  return [
    theme.colors.normal.black,
    theme.colors.normal.red,
    theme.colors.normal.green,
    theme.colors.normal.yellow,
    theme.colors.normal.blue,
    theme.colors.normal.magenta,
    theme.colors.normal.cyan,
    theme.colors.normal.white,
  ];
}
