export const WT_COLOR = '#6e7681';

// 20 visually distinct colors for clones — order matters for contrast between neighbours
const CLONE_PALETTE = [
  '#58a6ff', '#3fb950', '#ffa657', '#f78166', '#d2a8ff',
  '#79c0ff', '#56d364', '#ff9f43', '#ff6b6b', '#a29bfe',
  '#00cec9', '#fdcb6e', '#e17055', '#74b9ff', '#55efc4',
  '#fd79a8', '#b2bec3', '#6c5ce7', '#fab1a0', '#81ecec',
];

/**
 * Build a node_id → color map.
 * Each clone gets a unique color from the palette regardless of shared driver gene.
 * WT always uses WT_COLOR.
 */
export function buildCloneColorMap(nodes: { id: string; gene?: string | null }[]): Map<string, string> {
  const map = new Map<string, string>();
  let idx = 0;

  for (const node of nodes) {
    if (node.id === 'wt') { map.set('wt', WT_COLOR); continue; }
    map.set(node.id, CLONE_PALETTE[idx++ % CLONE_PALETTE.length]);
  }

  return map;
}
