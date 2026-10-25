// Shared, overdamped timing keeps the scroll scene coherent without a scroll hijack.
// Tight rest thresholds avoid visible snapping of normalized 0–1 scroll progress.
export const SCROLL_SPRING = {
  stiffness: 75, damping: 28, mass: 1.2, restDelta: .0001, restSpeed: .0001,
};
export const POINTER_SPRING = {
  stiffness: 80, damping: 24, mass: 1, restDelta: .001, restSpeed: .001,
};
