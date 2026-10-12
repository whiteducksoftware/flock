import { useEffect, useLayoutEffect, useRef, type RefObject } from 'react';
import { useUIStore } from '../../store/uiStore';
import { prefersLessMotion } from '../graph/animatePositions';

const GLIDE: KeyframeAnimationOptions = { duration: 320, easing: 'cubic-bezier(0.35, 0, 0.25, 1)' };

/** How far a glide moves an element right now (its transform's offset) */
function offsetOf(element: HTMLElement): { x: number; y: number } {
  const transform = getComputedStyle(element).transform;
  if (!transform || transform === 'none') return { x: 0, y: 0 };
  const values = transform.slice(transform.indexOf('(') + 1, -1).split(',').map(Number);
  return transform.startsWith('matrix3d') ? { x: values[12] ?? 0, y: values[13] ?? 0 } : { x: values[4] ?? 0, y: values[5] ?? 0 };
}

/** How much of a lane a running reveal hides at its bottom right now */
function hiddenOf(element: HTMLElement): number {
  const clip = getComputedStyle(element).clipPath;
  if (!clip?.startsWith('inset(')) return 0;
  return parseFloat(clip.slice(6).split(/\s+/)[2] ?? '0') || 0;
}

interface Layout {
  /** Each lane's top on the screen (without its glide) and height */
  lanes: Map<string, { top: number; height: number }>;
  /** Where each thing in a lane sits inside it (its cards, header and arrows, by `lane/data-glide`: a placeholder's ID repeats across lanes) */
  inside: Map<string, { x: number; y: number }>;
}

/**
 * The Blackboard's lanes move without jumping (FLIP): measured after every
 * render and whenever a lane changes its size on its own (a card unfolds, its
 * details arrive; ResizeObserver), and what moved glides from where it showed.
 *
 * - A lane that moves (one above arrived or grew) glides to its place. Its top
 *   is measured on the screen without the glide's own offset, so a scroll the
 *   browser keeps (scroll anchoring) moves nothing, and an interrupted glide
 *   continues from where the lane is (#642).
 * - A lane that grows opens downwards while the lanes below glide away, so
 *   nothing is drawn over it (#652).
 * - What changes its place inside a lane (a card, the header, an arrow: the
 *   lane's alignment changes when a card unfolds, a card arrives in a column)
 *   glides there too (#652).
 *
 * Returns what a scroll calls: it measures again, a scroll moves nothing.
 */
export function useLaneMotion(lanesRef: RefObject<HTMLDivElement | null>): () => void {
  // An unfold or fold renders here too: it moves things inside a lane even when no lane changes its size
  useUIStore((state) => state.unfoldedArtifactId);
  const last = useRef<Layout>({ lanes: new Map(), inside: new Map() });
  // What glides now, by `lane:`, `clip:` or `inside:` and the id
  const running = useRef(new Map<string, Animation>());
  const slots = () => [...(lanesRef.current?.querySelectorAll<HTMLElement>('[data-lane]') ?? [])];

  const measure = (): Layout => {
    const lanes = new Map<string, { top: number; height: number }>();
    const inside = new Map<string, { x: number; y: number }>();
    for (const slot of slots()) {
      const box = slot.getBoundingClientRect();
      lanes.set(slot.dataset.lane!, { top: box.top - offsetOf(slot).y, height: box.height });
      // The lane's own glide moves both boxes alike
      for (const item of slot.querySelectorAll<HTMLElement>('[data-glide]')) {
        const at = item.getBoundingClientRect();
        const own = offsetOf(item);
        inside.set(`${slot.dataset.lane}/${item.dataset.glide}`, { x: at.left - own.x - box.left, y: at.top - own.y - box.top });
      }
    }
    return { lanes, inside };
  };

  const play = (key: string, element: HTMLElement, frames: Keyframe[]) => {
    running.current.get(key)?.cancel();
    const animation = element.animate(frames, GLIDE);
    animation.onfinish = () => {
      if (running.current.get(key) === animation) running.current.delete(key);
    };
    running.current.set(key, animation);
  };

  const flip = () => {
    const before = last.current;
    const now = measure();
    last.current = now;
    for (const slot of slots()) {
      if (prefersLessMotion() || typeof slot.animate !== 'function') break;
      const id = slot.dataset.lane!;
      const was = before.lanes.get(id);
      const is = now.lanes.get(id)!;
      if (!was) continue;
      if (Math.abs(was.top - is.top) >= 1) {
        // From where it shows: the running glide's offset, read before it is cancelled
        const offset = offsetOf(slot).y;
        play(`lane:${id}`, slot, [{ transform: `translateY(${was.top - is.top + offset}px)` }, { transform: 'translateY(0)' }]);
      }
      // Growing again while it opens: from what shows now, read before the reveal is cancelled
      const grown = is.height - was.height;
      if (grown >= 1) {
        const hidden = hiddenOf(slot) + grown;
        play(`clip:${id}`, slot, [{ clipPath: `inset(0px 0px ${hidden}px 0px)` }, { clipPath: 'inset(0px 0px 0px 0px)' }]);
      } else if (grown <= -1) {
        // Shrinking: a reveal that still runs would hide what is left
        running.current.get(`clip:${id}`)?.cancel();
        running.current.delete(`clip:${id}`);
      }
      for (const item of slot.querySelectorAll<HTMLElement>('[data-glide]')) {
        const key = `${id}/${item.dataset.glide}`;
        const from = before.inside.get(key);
        const to = now.inside.get(key)!;
        if (!from || (Math.abs(from.x - to.x) < 1 && Math.abs(from.y - to.y) < 1)) continue;
        const own = offsetOf(item);
        play(`inside:${key}`, item, [
          { transform: `translate(${from.x - to.x + own.x}px, ${from.y - to.y + own.y}px)` },
          { transform: 'translate(0px, 0px)' },
        ]);
      }
    }
    // What left takes its glide along
    for (const [key, animation] of running.current) {
      const at = key.indexOf(':');
      const id = key.slice(at + 1);
      if (key.startsWith('inside:') ? now.inside.has(id) : now.lanes.has(id)) continue;
      animation.cancel();
      running.current.delete(key);
    }
  };

  const resizes = useRef<ResizeObserver | null>(null);
  const watched = useRef(new Set<Element>());
  const watch = () => {
    const observer = resizes.current;
    if (!observer) return;
    const current = new Set<Element>(slots());
    for (const slot of watched.current) if (!current.has(slot)) observer.unobserve(slot);
    for (const slot of current) if (!watched.current.has(slot)) observer.observe(slot);
    watched.current = current;
  };

  useLayoutEffect(() => {
    flip();
    watch();
  });
  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return;
    resizes.current = new ResizeObserver(() => flip());
    watch();
    return () => {
      resizes.current?.disconnect();
      resizes.current = null;
      watched.current = new Set();
    };
    // Once: flip and watch read refs only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return () => {
    last.current = measure();
  };
}
