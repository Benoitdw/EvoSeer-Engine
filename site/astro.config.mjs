import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://benoitdw.github.io',
  base: '/EvoSeer-Engine',
  integrations: [
    starlight({
      title: 'EvoSeer Engine',
      description: 'Biologically-informed stochastic evolutionary simulator',
      social: {
        github: 'https://github.com/bdewitte/EvoSeerEngine',
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
          label: 'Notebooks',
          items: [
            { label: 'Birth-Death Model', slug: 'notebooks/birth-death' },
          ],
        },
        {
          label: 'Tools',
          items: [
            { label: 'Visualizer', slug: 'visualizer' },
          ],
        },
      ],
    }),
  ],
});
