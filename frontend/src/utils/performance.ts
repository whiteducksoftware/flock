export function measureRenderTime(componentName: string, startMark: string, endMark: string) {
  performance.mark(endMark);
  const measure = performance.measure(
    `${componentName}-render`,
    startMark,
    endMark
  );
  console.log(`[Performance] ${componentName} render time: ${measure.duration.toFixed(2)}ms`);
  return measure.duration;
}

export function startRenderMeasure(componentName: string) {
  const markName = `${componentName}-start`;
  performance.mark(markName);
  return markName;
}
