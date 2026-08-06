export const MAHARASHTRA_BOUNDS = [
  [15.5, 72.5],
  [22.1, 81.0],
];

export function applyMaharashtraBounds(map, { minZoom = 6, viscosity = 1 } = {}) {
  map.setMaxBounds(MAHARASHTRA_BOUNDS);
  map.options.maxBoundsViscosity = viscosity;
  map.setMinZoom(minZoom);
}
