import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { TerminalTheme } from '../types/theme';
import {
  applyBuiltInTheme,
  applyTheme,
  applyThemeByName,
  contrastRatio,
  MIN_CONTRAST,
  resetToDefaultTheme,
  terminalThemeTokens,
  THEME_TOKENS,
} from './themeApplicator';

// The terminal themes the backend serves (src/flock/themes), as raw TOML
const THEME_FILES = import.meta.glob('../../../themes/*.toml', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

/** The [colors.*] tables of a theme TOML file. */
function loadTheme(file: string): TerminalTheme {
  const path = Object.keys(THEME_FILES).find((p) => p.endsWith(`/${file}`))!;
  const colors: Record<string, Record<string, string>> = {};
  let table: Record<string, string> | null = null;
  for (const line of THEME_FILES[path]!.split('\n')) {
    const header = line.match(/^\[colors\.(\w+)\]/);
    if (header) {
      table = colors[header[1]!] = {};
    } else if (line.startsWith('[')) {
      table = null;
    } else {
      const entry = line.match(/^(\w+)\s*=\s*["']\s*(#[0-9a-fA-F]{3,8})\s*["']/);
      if (entry && table) table[entry[1]!] = entry[2]!;
    }
  }
  return { name: file.replace(/\.toml$/, ''), colors } as unknown as TerminalTheme;
}

const dark: TerminalTheme = {
  name: 'dark',
  colors: {
    primary: { background: '#101010', foreground: '#e0e0e0' },
    normal: {
      black: '#000000', red: '#cc4444', green: '#44cc44', yellow: '#ccaa33',
      blue: '#4488ee', magenta: '#cc44cc', cyan: '#44cccc', white: '#cccccc',
    },
    bright: {
      black: '#222222', red: '#ff6666', green: '#66ff66', yellow: '#ffdd55',
      blue: '#66aaff', magenta: '#ff66ff', cyan: '#66ffff', white: '#ffffff',
    },
    selection: { background: '#333333', text: '#ffffff' },
    cursor: { cursor: '#ffffff', text: '#000000' },
  },
};

describe('terminal themes on the tokens', () => {
  it('maps a terminal palette onto the four signals', () => {
    const tokens = terminalThemeTokens(dark);

    expect(tokens['--bg']).toBe('#101010');
    expect(tokens['--text']).toBe('#e0e0e0');
    expect(tokens['--signal']).toBe('#ccaa33');
    expect(tokens['--sure']).toBe('#4488ee');
    expect(tokens['--error']).toBe('#cc4444');
  });

  it('lifts text that would be unreadable on the cards', () => {
    // bright black (#222222) on a dark card fails 4.5:1 as it is
    const tokens = terminalThemeTokens(dark);

    expect(contrastRatio('#222222', tokens['--surface'])).toBeLessThan(MIN_CONTRAST);
    expect(contrastRatio(tokens['--text-3'], tokens['--surface'])).toBeGreaterThanOrEqual(
      MIN_CONTRAST
    );
  });

  it('puts readable text on every solid signal fill', () => {
    for (const file of Object.keys(THEME_FILES).map((path) => path.split('/').pop()!)) {
      const tokens = terminalThemeTokens(loadTheme(file));
      for (const [text, fill] of [
        ['--on-signal', '--signal'],
        ['--on-sure', '--sure'],
        ['--on-error', '--error'],
      ] as const) {
        expect(contrastRatio(tokens[text], tokens[fill]), `${file} ${text}`).toBeGreaterThanOrEqual(
          MIN_CONTRAST
        );
      }
    }
  });

  it('keeps every text token readable for all bundled terminal themes', () => {
    const files = Object.keys(THEME_FILES).map((path) => path.split('/').pop()!);
    expect(files.length).toBeGreaterThan(300);
    const failing: string[] = [];
    for (const file of files) {
      const tokens = terminalThemeTokens(loadTheme(file));
      for (const token of ['--text', '--text-2', '--text-3', '--signal-ink', '--sure-ink', '--error-ink'] as const) {
        if (contrastRatio(tokens[token], tokens['--surface']) < MIN_CONTRAST) {
          failing.push(`${file} ${token}`);
        }
      }
    }
    expect(failing).toEqual([]);
  });
});

describe('applying themes', () => {
  beforeEach(() => {
    applyBuiltInTheme('graphite');
  });

  it('puts a dark terminal theme on Graphite and a light one on Paper', () => {
    const root = document.documentElement;
    applyTheme(dark);
    expect(root.dataset.theme).toBe('graphite');
    expect(root.style.getPropertyValue('--bg')).toBe('#101010');

    const light = loadTheme('3024-day.toml');
    applyTheme(light);
    expect(root.dataset.theme).toBe('paper');
  });

  it('removes every override when going back to a built-in theme', () => {
    const root = document.documentElement;
    applyTheme(dark);

    applyBuiltInTheme('paper');

    expect(root.dataset.theme).toBe('paper');
    for (const token of THEME_TOKENS) {
      expect(root.style.getPropertyValue(token)).toBe('');
    }
    resetToDefaultTheme();
    expect(root.dataset.theme).toBe('graphite');
  });

  it('restores a stored theme by name', async () => {
    const root = document.documentElement;
    const load = vi.fn(async () => dark);

    // 'default' was stored by the old dashboard
    expect(await applyThemeByName('default', root, load)).toBe('graphite');
    expect(root.dataset.theme).toBe('graphite');
    expect(await applyThemeByName('paper', root, load)).toBe('paper');
    expect(root.dataset.theme).toBe('paper');
    expect(load).not.toHaveBeenCalled();

    expect(await applyThemeByName('dracula', root, load)).toBe('dracula');
    expect(load).toHaveBeenCalledWith('dracula');
    expect(root.style.getPropertyValue('--bg')).toBe('#101010');
  });

  it('drops a theme that finishes loading after another one was chosen', async () => {
    const root = document.documentElement;
    let finish: (theme: TerminalTheme) => void = () => {};
    const loading = applyThemeByName('dracula', root, () => new Promise((resolve) => (finish = resolve)));

    applyBuiltInTheme('paper', root); // the user picks Paper meanwhile
    finish(dark);

    expect(await loading).toBeNull();
    expect(root.dataset.theme).toBe('paper');
    expect(root.style.getPropertyValue('--bg')).toBe('');
  });

  it('falls back to Graphite when a terminal theme cannot be loaded', async () => {
    const root = document.documentElement;
    vi.spyOn(console, 'error').mockImplementation(() => {});
    applyTheme(dark);

    const applied = await applyThemeByName('gone', root, async () => {
      throw new Error('404');
    });

    expect(applied).toBe('graphite'); // so the settings stop asking for it
    expect(root.dataset.theme).toBe('graphite');
    expect(root.style.getPropertyValue('--bg')).toBe('');
  });
});
