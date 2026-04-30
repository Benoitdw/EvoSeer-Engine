export const GENE_COLORS: Record<string, string> = {
  BRAF: '#58a6ff', NRAS: '#3fb950', NF1: '#ffa657',
  MAP2K1: '#d2a8ff', KRAS: '#79c0ff', EGFR: '#f78166',
};
export const FALLBACK = ['#3fb950','#58a6ff','#ffa657','#d2a8ff','#f78166','#79c0ff','#56d364','#a5f3fc'];
export const WT_COLOR = '#6e7681';

function lighten(hex: string, amount: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `#${[r, g, b].map(c => Math.round(c + (255 - c) * amount).toString(16).padStart(2, '0')).join('')}`;
}

/**
 * Build a node_id → color map.
 * Multiple clones of the same gene get progressively lightened shades
 * so they remain visually related but distinguishable.
 */
export function buildCloneColorMap(nodes: { id: string; gene?: string | null }[]): Map<string, string> {
  const geneOccurrence: Record<string, number> = {};
  const map = new Map<string, string>();
  let fallbackIdx = 0;

  for (const node of nodes) {
    if (node.id === 'wt') { map.set('wt', WT_COLOR); continue; }

    const gene = node.gene ?? '';
    const base = GENE_COLORS[gene];

    if (base) {
      const occ = geneOccurrence[gene] ?? 0;
      geneOccurrence[gene] = occ + 1;
      // 0th occurrence → base color; each next → lighten by 25% per step
      map.set(node.id, occ === 0 ? base : lighten(base, Math.min(occ * 0.28, 0.7)));
    } else {
      map.set(node.id, FALLBACK[fallbackIdx++ % FALLBACK.length]);
    }
  }

  return map;
}
