export const CLUSTER_COLORS = [
  '#1ed760',
  '#4f46e5',
  '#f59e0b',
  '#ef4444',
  '#06b6d4',
  '#ec4899',
  '#84cc16',
  '#8b5cf6',
  '#f97316',
  '#14b8a6',
  '#eab308',
  '#64748b',
]

export function clusterColor(i) {
  return CLUSTER_COLORS[i % CLUSTER_COLORS.length]
}
