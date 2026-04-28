export interface ChartTheme {
  bg:   string;
  grid: string;
  axis: string;
  text: string;
}

export interface ChartOptions {
  xMin?:    number;
  xMax?:    number;
  yMin?:    number;
  yMax?:    number;
  xLabel?:  string;
  yLabel?:  string;
  pad?: { top: number; right: number; bottom: number; left: number };
}

const DEFAULT_PAD = { top: 18, right: 18, bottom: 42, left: 48 };

export class CanvasChart {
  readonly ctx: CanvasRenderingContext2D;
  readonly W:   number;
  readonly H:   number;
  readonly pad: { top: number; right: number; bottom: number; left: number };
  readonly PW:  number;
  readonly PH:  number;

  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
  xLabel: string;
  yLabel: string;

  private _observer: MutationObserver | null = null;

  constructor(canvas: HTMLCanvasElement, opts: ChartOptions = {}) {
    this.ctx    = canvas.getContext('2d')!;
    this.W      = canvas.width;
    this.H      = canvas.height;
    this.pad    = opts.pad ?? { ...DEFAULT_PAD };
    this.PW     = this.W - this.pad.left - this.pad.right;
    this.PH     = this.H - this.pad.top  - this.pad.bottom;
    this.xMin   = opts.xMin   ?? 0;
    this.xMax   = opts.xMax   ?? 1;
    this.yMin   = opts.yMin   ?? 0;
    this.yMax   = opts.yMax   ?? 1;
    this.xLabel = opts.xLabel ?? '';
    this.yLabel = opts.yLabel ?? '';
  }

  // ── Coordinate transforms ────────────────────────────────────────────────

  xc(x: number): number {
    return this.pad.left + (x - this.xMin) / (this.xMax - this.xMin) * this.PW;
  }

  yc(y: number): number {
    return this.pad.top + (1 - (y - this.yMin) / (this.yMax - this.yMin)) * this.PH;
  }

  // ── Theme ────────────────────────────────────────────────────────────────

  isDark(): boolean {
    return document.documentElement.dataset.theme === 'dark';
  }

  theme(): ChartTheme {
    return this.isDark()
      ? { bg: '#1a1c23', grid: '#2e3040', axis: '#555', text: '#999' }
      : { bg: '#ffffff', grid: '#e8e8e8', axis: '#aaa', text: '#666' };
  }

  // ── Drawing primitives ───────────────────────────────────────────────────

  clear(): void {
    this.ctx.fillStyle = this.theme().bg;
    this.ctx.fillRect(0, 0, this.W, this.H);
  }

  /**
   * Draw grid lines, axes, tick labels, and axis labels.
   * @param xTicks  grid lines along x-axis
   * @param yTicks  grid lines along y-axis
   * @param labels  optional subsets to actually label (defaults to full tick arrays)
   */
  drawBackground(
    xTicks:  number[],
    yTicks:  number[],
    labels?: { x?: number[]; y?: number[] },
  ): void {
    const { ctx, pad, W, H } = this;
    const t = this.theme();
    const xLabels = labels?.x ?? xTicks;
    const yLabels = labels?.y ?? yTicks;

    // Grid
    ctx.strokeStyle = t.grid;
    ctx.lineWidth = 1;
    yTicks.forEach(v => {
      ctx.beginPath();
      ctx.moveTo(pad.left, this.yc(v));
      ctx.lineTo(W - pad.right, this.yc(v));
      ctx.stroke();
    });
    xTicks.forEach(v => {
      ctx.beginPath();
      ctx.moveTo(this.xc(v), pad.top);
      ctx.lineTo(this.xc(v), H - pad.bottom);
      ctx.stroke();
    });

    // Axes
    ctx.strokeStyle = t.axis;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top);
    ctx.lineTo(pad.left, H - pad.bottom);
    ctx.lineTo(W - pad.right, H - pad.bottom);
    ctx.stroke();

    // Tick labels
    ctx.fillStyle = t.text;
    ctx.font = '11px system-ui, sans-serif';

    ctx.textAlign = 'center';
    xLabels.forEach(v =>
      ctx.fillText(fmt(v), this.xc(v), H - pad.bottom + 15),
    );
    if (this.xLabel)
      ctx.fillText(this.xLabel, pad.left + this.PW / 2, H - 5);

    ctx.textAlign = 'right';
    yLabels.forEach(v =>
      ctx.fillText(fmt(v), pad.left - 7, this.yc(v) + 4),
    );
    if (this.yLabel) {
      ctx.save();
      ctx.translate(13, pad.top + this.PH / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.textAlign = 'center';
      ctx.fillText(this.yLabel, 0, 0);
      ctx.restore();
    }
  }

  /** Draw a continuous curve: fn(x) → y, sampled pixel-by-pixel over [xMin, xMax]. */
  plotCurve(fn: (x: number) => number, color: string, lineWidth = 2.5): void {
    const { ctx, pad, PW } = this;
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    for (let px = 0; px <= PW; px++) {
      const x  = this.xMin + (px / PW) * (this.xMax - this.xMin);
      const cx = pad.left + px;
      const cy = this.yc(fn(x));
      px === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy);
    }
    ctx.stroke();
  }

  /** Vertical dashed line at x. */
  vLine(x: number, color: string, alpha = 1, dash: number[] = [3, 4]): void {
    const { ctx, pad, H } = this;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.setLineDash(dash);
    ctx.globalAlpha = alpha;
    ctx.beginPath();
    ctx.moveTo(this.xc(x), pad.top);
    ctx.lineTo(this.xc(x), H - pad.bottom);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
  }

  /** Dashed crosshairs from (x, y) down and left to the axes. */
  crosshair(x: number, y: number, color: string, alpha = 0.65, dash: number[] = [4, 3]): void {
    const { ctx, pad, H } = this;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.setLineDash(dash);
    ctx.globalAlpha = alpha;
    ctx.beginPath();
    ctx.moveTo(this.xc(x), this.yc(y));
    ctx.lineTo(this.xc(x), H - pad.bottom);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(pad.left, this.yc(y));
    ctx.lineTo(this.xc(x), this.yc(y));
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
  }

  /** Filled circle at (x, y) in data coordinates. */
  dot(x: number, y: number, color: string, radius = 5): void {
    this.ctx.fillStyle = color;
    this.ctx.beginPath();
    this.ctx.arc(this.xc(x), this.yc(y), radius, 0, 2 * Math.PI);
    this.ctx.fill();
  }

  /**
   * Filled rectangle below the x-axis, spanning [x0, x1] in data coordinates.
   * Useful for stacked contribution bars.
   */
  barSegment(x0: number, x1: number, color: string, yOffset = 5, height = 5): void {
    const w = this.xc(x1) - this.xc(x0);
    if (w <= 0) return;
    this.ctx.fillStyle = color;
    this.ctx.fillRect(this.xc(x0), this.H - this.pad.bottom + yOffset, w, height);
  }

  /**
   * Stacked area chart.
   * `xs` — sorted x values (data coordinates).
   * `series` — array of y-value arrays, one per layer, same length as xs.
   * `colors` — fill color per layer.
   * Layers are drawn bottom-up; each layer starts from the cumulative top of
   * the layers below it.
   */
  stackplot(xs: number[], series: number[][], colors: string[], alpha = 0.85): void {
    if (xs.length < 2 || series.length === 0) return;
    const { ctx } = this;
    const n = xs.length;

    // Cumulative baseline (pixel y) per x index — starts at the x-axis
    const baseline = xs.map((_, i) => this.yc(this.yMin));

    ctx.globalAlpha = alpha;
    for (let l = 0; l < series.length; l++) {
      const ys = series[l];
      ctx.fillStyle = colors[l % colors.length];
      ctx.beginPath();
      // Top edge left → right
      ctx.moveTo(this.xc(xs[0]), baseline[0] - (this.yc(this.yMin) - this.yc(ys[0])));
      for (let i = 0; i < n; i++) {
        const px = this.xc(xs[i]);
        const py = baseline[i] - (this.yc(this.yMin) - this.yc(ys[i]));
        ctx.lineTo(px, py);
      }
      // Bottom edge right → left (baseline)
      for (let i = n - 1; i >= 0; i--) {
        ctx.lineTo(this.xc(xs[i]), baseline[i]);
      }
      ctx.closePath();
      ctx.fill();
      // Advance baseline upward by this layer's height
      for (let i = 0; i < n; i++) {
        baseline[i] -= this.yc(this.yMin) - this.yc(ys[i]);
      }
    }
    ctx.globalAlpha = 1;
  }

  /** Unicode star marker (★) at (x, y) in data coordinates. */
  star(x: number, y: number, color: string, size = 13): void {
    const { ctx } = this;
    ctx.fillStyle = color;
    ctx.font = `${size}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('★', this.xc(x), this.yc(y));
    ctx.textBaseline = 'alphabetic';
  }

  // ── Theme watcher ────────────────────────────────────────────────────────

  /** Re-call `drawFn` whenever the page theme (dark/light) changes. */
  watchTheme(drawFn: () => void): void {
    this._observer?.disconnect();
    this._observer = new MutationObserver(drawFn);
    this._observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    });
  }

  destroy(): void {
    this._observer?.disconnect();
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmt(v: number): string {
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
}
