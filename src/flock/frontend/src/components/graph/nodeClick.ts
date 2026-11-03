/** Elements inside a node that do something of their own when clicked. */
const CONTROLS = 'button, a[href], input, select, textarea, [role="button"], [role="tab"]';

/**
 * Whether a click inside a node landed on one of its controls (the failed
 * run's trace button, a review button), which then is all the click does.
 */
export function fromControl(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  const control = target.closest(CONTROLS);
  return control !== null && control.closest('.react-flow__node') !== null;
}
