import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

export const collections = {
  docs: defineCollection({
    loader: glob({ base: './src/content/docs', pattern: '**/*.{md,mdx}' }),
    schema: docsSchema({
      extend: z.object({
        status: z.enum(['open', 'in-progress', 'closed']).optional(),
      }),
    }),
  }),
};
