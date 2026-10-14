import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const downloaders = defineCollection({
  loader: glob({ base: './src/content/downloaders', pattern: '**/*.md' }),
  schema: z.object({
    title: z.string(),
    platform: z.enum(['YouTube', 'TikTok', 'Instagram', 'Facebook', 'X', 'LinkedIn', 'Social media', 'Local video files']),
    description: z.string().max(159),
    keywords: z.array(z.string()),
  }),
});

export const collections = { downloaders };
