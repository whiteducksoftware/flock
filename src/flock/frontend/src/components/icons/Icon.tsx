/**
 * The dashboard's line icons (docs/internal/design-system/README.md, Icons):
 * a 24 px grid, 1.8 px stroke, round caps, currentColor. The shapes are the
 * ones of the mockups. `◆` stays the decision glyph and is text, not an icon.
 */

import React from 'react';

const SHAPES = {
  plus: <path d="M12 5v14M5 12h14" />,
  minus: <path d="M5 12h14" />,
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="M16 16l4 4" />
    </>
  ),
  chevronDown: <path d="M6 9l6 6 6-6" />,
  chevronUp: <path d="M6 15l6-6 6 6" />,
  chevronLeft: <path d="M15 6l-6 6 6 6" />,
  chevronRight: <path d="M9 6l6 6-6 6" />,
  fold: <path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" />,
  focus: <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />,
  fit: (
    <>
      <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
      <rect x="9" y="9" width="6" height="6" rx="1" />
    </>
  ),
  layout: (
    <>
      <rect x="3" y="4" width="6" height="5" rx="1" />
      <rect x="3" y="15" width="6" height="5" rx="1" />
      <rect x="15" y="9.5" width="6" height="5" rx="1" />
      <path d="M9 6.5h2.5a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5H9M13 12h2" />
    </>
  ),
  history: (
    <>
      <path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1M3.5 4.5v4h4" />
      <path d="M12 8v4l2.5 1.5" />
    </>
  ),
  traces: <path d="M4 6h9M8 12h11M6 18h6" />,
  scheduled: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  join: <path d="M7 4v16M17 4v16M7 12h10" />,
  batch: (
    <>
      <rect x="4" y="4" width="7" height="7" rx="1.5" />
      <rect x="13" y="4" width="7" height="7" rx="1.5" />
      <rect x="4" y="13" width="7" height="7" rx="1.5" />
      <rect x="13" y="13" width="7" height="7" rx="1.5" strokeDasharray="2 2" />
    </>
  ),
  settings: (
    <>
      <path d="M4 7h9M18 7h2M4 17h3M12 17h8" />
      <circle cx="15.5" cy="7" r="2.3" />
      <circle cx="9.5" cy="17" r="2.3" />
    </>
  ),
  shortcuts: (
    <>
      <rect x="3" y="6" width="18" height="12" rx="2.5" />
      <path d="M7 10h.01M11 10h.01M15 10h.01M8 14h8" />
    </>
  ),
  error: (
    <>
      <path d="M12 8v5M12 16.5h.01" />
      <circle cx="12" cy="12" r="9" />
    </>
  ),
  open: <path d="M7 17L17 7M9 7h8v8" />,
  lanes: <path d="M3 6h4M10 6h4M17 6h4M3 12h4M10 12h4M3 18h4M10 18h4M17 18h4" />,
  graph: (
    <>
      <circle cx="6" cy="6" r="2.5" />
      <circle cx="18" cy="12" r="2.5" />
      <circle cx="6" cy="18" r="2.5" />
      <path d="M8.3 7.2l7.4 3.6M8.3 16.8l7.4-3.6" />
    </>
  ),
  person: (
    <>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c1.2-3.5 3.8-5 7-5s5.8 1.5 7 5" />
    </>
  ),
} satisfies Record<string, React.ReactNode>;

export type IconName = keyof typeof SHAPES;

export const ICON_NAMES = Object.keys(SHAPES) as IconName[];

export interface IconProps {
  name: IconName;
  /** Width and height in px (default 16). */
  size?: number;
  /** An accessible name; without it the icon is decorative (aria-hidden). */
  label?: string;
  className?: string;
  style?: React.CSSProperties;
}

export const Icon: React.FC<IconProps> = ({ name, size = 16, label, className, style }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.8}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    style={style}
    {...(label ? { role: 'img', 'aria-label': label } : { 'aria-hidden': true })}
  >
    {SHAPES[name]}
  </svg>
);

/** The flock mark: three chevrons, the lead one amber. */
export const FlockMark: React.FC<{ size?: number; className?: string }> = ({
  size = 20,
  className,
}) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden
  >
    <path d="M8 3.5l4 3-4 3" stroke="currentColor" />
    <path d="M8 14.5l4 3-4 3" stroke="currentColor" />
    <path d="M15 9l4 3-4 3" stroke="var(--signal)" />
  </svg>
);
