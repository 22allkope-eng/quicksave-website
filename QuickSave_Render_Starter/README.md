# QuickSave — Render-ready website

A responsive video-download directory (not a download engine) with an admin dashboard, editable external links, visit/click analytics, site settings, password changes, and CSV analytics export.

## SEO features added
- Editable homepage SEO title, meta description, keywords, and social-sharing image URL in Admin → Website & SEO.
- Canonical URL, Open Graph, and Twitter/X sharing metadata.
- `robots.txt` and dynamically generated `sitemap.xml`.
- Dedicated informational guide pages for each enabled platform, linked from the homepage.
- Admin and redirect routes marked `noindex,nofollow`.
- SVG favicon.
- Basic structured crawl paths and mobile-friendly metadata.

SEO note: meta keywords are included as optional metadata but Google does not use the keywords meta tag for ranking. Helpful original content, a custom domain, Search Console setup, backlinks, and performance are still important. No SEO package can guarantee rankings.

## Features
- Mobile-friendly QuickSave homepage inspired by the supplied screenshot.
- Platform cards for YouTube, Facebook, Instagram, TikTok, X, LinkedIn.
- Every card routes through `/go/<id>` so click counts are saved before redirecting.
- Admin dashboard: visit counts, daily unique visitor estimates, page views, click counts, date charts, referral sources, recent visits.
- Edit URLs, descriptions, display names, and enable/disable platforms; add additional platforms.
- Change homepage subtitle and optional announcement.
- Change admin password; export daily analytics to CSV.
- Analytics uses a daily salted hash of the visitor IP and does not store raw IP addresses.

## Run locally
Requires Python 3.10+.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Set environment variables before starting. At minimum, set a unique `SECRET_KEY` and `ADMIN_PASSWORD` (12+ characters). Then:

```bash
python app.py
```

Open `http://127.0.0.1:5000`. Admin login: `/admin/login`. Check `http://127.0.0.1:5000/robots.txt` and `http://127.0.0.1:5000/sitemap.xml` to verify SEO endpoints.

If you run without setting `ADMIN_PASSWORD`, the first-run local testing fallback password is `ChangeMeNow-2026!`. Change it immediately in Admin → Change password. **Do not deploy with this fallback.**

## Deploy on Render
1. Extract the ZIP.
2. Put the files into a new GitHub repository (Render connects to a Git repository for this workflow).
3. In Render, choose **New → Blueprint** and select the repository containing `render.yaml`, or create a Web Service manually.
4. For manual setup use:
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
   - Health check path: `/health`
5. Set environment variables:
   - `SECRET_KEY`: long random secret
   - `ADMIN_USERNAME`: e.g. `admin`
   - `ADMIN_PASSWORD`: unique password of at least 12 characters
   - `ANALYTICS_SALT`: long random secret, different from `SECRET_KEY`
   - `DATABASE_PATH`: `/var/data/quicksave.db` if a disk is mounted at `/var/data`
6. **Persistence warning:** Render's default filesystem is ephemeral. For data to survive restarts/redeploys with this SQLite setup, add a persistent disk mounted at `/var/data`. Render currently limits persistent disks to paid web services. If you deploy on a free instance without persistent storage, link changes, password changes, and analytics may be lost when the instance restarts/redeploys. For a durable free-tier alternative, use a managed external database (e.g. PostgreSQL) and adapt the database configuration before launch.
7. Render provides an `onrender.com` URL, so you can test before buying a custom domain.

## Important notes
- The default external downloader URLs are examples. Before launch, test each link and replace broken/unwanted services in Admin → Manage links. Third-party websites can change their URLs, availability, terms, or advertising at any time.
- This directory does not download or host videos. It redirects users to external websites.
- Only use external tools and content in ways permitted by the relevant platform terms and copyright law.
- Visitor counts are estimates: visitors who block cookies/proxy headers or share networks may be difficult to distinguish. Country reporting is shown only when the hosting proxy provides a country header.
- Do not expose `/admin` credentials. Use HTTPS (Render provides it on the public service URL).
- Consider adding Privacy Policy and Terms pages before public promotion or ad monetization.
