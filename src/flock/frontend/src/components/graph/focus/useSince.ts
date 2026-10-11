import { useEffect, useState } from 'react';

/**
 * The seconds since `at`, ticking while the stage is open. The wall clock is
 * read once; the time after that comes from the monotonic clock, so a step of
 * the wall clock (a VM's time sync, daylight saving) does not move it.
 */
export const useSince = (at: string | null): number | null => {
  const [anchor] = useState(() => ({ wall: Date.now(), mono: performance.now() }));
  const [now, setNow] = useState(anchor.wall);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(anchor.wall + performance.now() - anchor.mono), 1000);
    return () => window.clearInterval(timer);
  }, [anchor]);
  return at ? Math.max(0, (now - Date.parse(at)) / 1000) : null;
};
