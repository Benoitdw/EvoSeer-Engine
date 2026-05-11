import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

export default defineConfig({
  site: 'https://benoitdw.github.io',
  base: '/EvoSeer-Engine',
  markdown: {
    remarkPlugins: [remarkMath],
    rehypePlugins: [rehypeKatex],
  },
  integrations: [
    starlight({
      title: 'EvoSeer Engine',
      customCss: ['./node_modules/katex/dist/katex.min.css'],
      description: 'Biologically-informed stochastic evolutionary simulator',
      social: {
        github: 'https://github.com/bdewitte/EvoSeerEngine',
      },
      components: {
        SocialIcons: './src/components/VisualizerNavButton.astro',
      },
      sidebar: [
        {
          label: 'Getting Started',
          items: [
            { label: 'Introduction', slug: 'introduction' },
            { label: 'Installation', slug: 'installation' },
            { label: 'Quick Start', slug: 'quickstart' },
          ],
        },
        {
          label: 'Architecture',
          items: [
            { label: 'Overview', slug: 'architecture/overview' },
            { label: 'Mutation Pipeline', slug: 'architecture/mutation-pipeline' },
            {
              label: 'Layers',
              collapsed: false,
              items: [
                { label: 'Layer 1 — Data & State', slug: 'architecture/layers/data-state' },
                { label: 'Layer 2 — Feature Plugins', slug: 'architecture/layers/plugins' },
                { label: 'Layer 3 — Rate Functions', slug: 'architecture/layers/rate-functions' },
                { label: 'Layer 4 — Services', slug: 'architecture/layers/services' },
                { label: 'Layer 5 — Engine', slug: 'architecture/layers/engine' },
                { label: 'Layer 6 — Recording', slug: 'architecture/layers/recording' },
              ],
            },
          ],
        },
        {
          label: 'Plugins',
          items: [
            {
              label: 'Pathways',
              items: [
                { label: 'Pathway Plugin', slug: 'plugins/pathway' },
                { label: 'OIS Plugin', slug: 'plugins/ois' },
              ],
            },
          ],
        },
        {
          label: 'Notebooks',
          items: [
            { label: 'Birth-Death Model', slug: 'notebooks/birth-death' },
            { label: 'ABC — Samples per Simulation', slug: 'notebooks/abc-samples' },
          ],
        },
        {
          label: 'Calibration',
          items: [
            { label: 'ABC Calibration', slug: 'calibration/overview' },
          ],
        },
        {
          label: 'Tools',
          items: [
            { label: 'Visualizer', slug: 'visualizer' },
          ],
        },
        {
          label: 'Research Notes',
          items: [
            { label: 'Index', slug: 'research-notes' },
          ],
        },
      ],
    }),
  ],
});
