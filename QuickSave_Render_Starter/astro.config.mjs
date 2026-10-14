import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  output: 'static',
  site: process.env.SITE_URL || 'https://example.com',
  integrations: [tailwind()],
});
