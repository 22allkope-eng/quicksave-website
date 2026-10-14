# QuickSave Astro

A static Astro website built from a 100-page Markdown collection. The home page groups seven guides under each of six platforms. Each guide includes practical steps, a tool table, FAQ structured data, an official platform link, and four related guides from the same collection platform.

## Requirements

- Node.js 20 or newer
- npm

## Local development

```bash
npm install
npm run dev
```

## Production build

```bash
npm run build
npm run preview
```

Astro outputs the static site to `dist/`. The downloader source files are in `src/content/downloaders/`; the schema is `src/content/config.ts`. Route files are `src/pages/index.astro` and `src/pages/download/[slug].astro`.

## Cloudflare Pages

The project uses `wrangler.toml` with `dist/` as the Pages build output. In Cloudflare Pages, connect this repository and set:

- Build command: `npm run build`
- Build output directory: `dist`

Or deploy from a terminal:

```bash
npm install
npm run deploy
```

`npm run deploy` builds the site and publishes `dist/` with Wrangler. No Flask service, Python runtime, database, or server-side secrets are required for this static frontend.
