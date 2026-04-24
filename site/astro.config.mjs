import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://bdewitte.github.io',
  base: '/EvoSeerEngine',
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
