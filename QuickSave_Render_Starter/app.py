import os, sqlite3, secrets, hashlib, hmac, time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

try:
    import psycopg2
    import psycopg2.extras
except ImportError:  # pragma: no cover - installed only in Render deployments
    psycopg2 = None

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
DB_PATH = os.environ.get("DATABASE_PATH", "quicksave.db")
ADMIN_USER = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SITE_NAME = "QuickSave"


def _normalize_query_for_postgres(query):
    return query.replace("?", "%s")


class PostgresConnection:
    def __init__(self, dsn):
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is required when DATABASE_URL points to PostgreSQL.")
        self.conn = psycopg2.connect(dsn, sslmode="require", connect_timeout=15)
        self.conn.autocommit = False
        self.cursor_obj = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def execute(self, query, params=()):
        self.cursor_obj.execute(_normalize_query_for_postgres(query), params)
        return self

    def executemany(self, query, params_seq):
        self.cursor_obj.executemany(_normalize_query_for_postgres(query), params_seq)
        return self

    def fetchone(self):
        return self.cursor_obj.fetchone()

    def fetchall(self):
        return self.cursor_obj.fetchall()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.close()
        return False

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.cursor_obj.close()
        self.conn.close()


def is_postgres_database():
    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    return bool(database_url) and (database_url.startswith("postgres://") or database_url.startswith("postgresql://"))


def enabled_where_clause():
    return "enabled = TRUE" if is_postgres_database() else "enabled = 1"


def enabled_value(value):
    return bool(value) if is_postgres_database() else (1 if value else 0)


LANGUAGE_TRANSLATIONS = {
    "en": {
        "site_name": "QuickSave",
        "site_subtitle": "Video Downloader Directory",
        "footer_label": "QuickSave · Video Downloader Directory",
        "eyebrow": "SAVE WHAT YOU WANT TO WATCH",
        "home_title": "What do you want to download?",
        "home_subtitle": "Choose your platform to find a download tool.",
        "also_available": "Choose a platform above to continue to an external tool.",
        "explore_guides": "Explore platform guides",
        "guide_intro": "Read a short overview of each available tool directory before leaving QuickSave.",
        "simple_use": "Simple and easy to use",
        "simple_use_desc": "Choose a platform, open a recommended external tool, and continue there.",
        "please_note": "Please note:",
        "note_text": "QuickSave is a directory, not a video downloader. External websites are operated independently and may have their own terms and restrictions.",
        "download": "Download",
        "admin": "Admin",
        "find_platform": "Find platform",
    },
    "es": {
        "site_name": "QuickSave",
        "site_subtitle": "Directorio de descargadores",
        "footer_label": "QuickSave · Directorio de descargadores",
        "eyebrow": "GUARDA LO QUE QUIERES VER",
        "home_title": "¿Qué quieres descargar?",
        "home_subtitle": "Elige tu plataforma para encontrar una herramienta de descarga.",
        "also_available": "Elige una plataforma para continuar en una herramienta externa.",
        "explore_guides": "Explora guías de plataformas",
        "guide_intro": "Lee una breve descripción de cada guía antes de salir de QuickSave.",
        "simple_use": "Simple y fácil de usar",
        "simple_use_desc": "Elige una plataforma, abre una herramienta recomendada y continúa allí.",
        "please_note": "Ten en cuenta:",
        "note_text": "QuickSave es un directorio, no un descargador de videos. Los sitios externos se gestionan de forma independiente y pueden tener sus propios términos y restricciones.",
        "download": "Descargar",
        "admin": "Admin",
        "find_platform": "Buscar plataforma",
    },
    "fr": {
        "site_name": "QuickSave",
        "site_subtitle": "Annuaire de téléchargement",
        "footer_label": "QuickSave · Annuaire de téléchargement",
        "eyebrow": "SAUVEGARDEZ CE QUE VOUS VOULEZ REGARDER",
        "home_title": "Que voulez-vous télécharger ?",
        "home_subtitle": "Choisissez votre plateforme pour trouver un outil de téléchargement.",
        "also_available": "Choisissez une plateforme pour continuer vers un outil externe.",
        "explore_guides": "Explorer les guides de plateformes",
        "guide_intro": "Lisez un bref aperçu de chaque guide avant de quitter QuickSave.",
        "simple_use": "Simple et facile à utiliser",
        "simple_use_desc": "Choisissez une plateforme, ouvrez un outil recommandé et continuez dessus.",
        "please_note": "À noter :",
        "note_text": "QuickSave est un annuaire, pas un téléchargeur de vidéos. Les sites externes sont exploités indépendamment et peuvent avoir leurs propres conditions et restrictions.",
        "download": "Télécharger",
        "admin": "Admin",
        "find_platform": "Trouver une plateforme",
    },
    "pt": {
        "site_name": "QuickSave",
        "site_subtitle": "Diretório de download",
        "footer_label": "QuickSave · Diretório de download",
        "eyebrow": "SALVE O QUE VOCÊ QUER ASSISTIR",
        "home_title": "O que você quer baixar?",
        "home_subtitle": "Escolha sua plataforma para encontrar uma ferramenta de download.",
        "also_available": "Escolha uma plataforma acima para continuar em uma ferramenta externa.",
        "explore_guides": "Explorar guias da plataforma",
        "guide_intro": "Leia uma visão geral rápida de cada guia antes de sair do QuickSave.",
        "simple_use": "Simples e fácil de usar",
        "simple_use_desc": "Escolha uma plataforma, abra uma ferramenta recomendada e continue nela.",
        "please_note": "Observe:",
        "note_text": "QuickSave é um diretório, não um downloader de vídeos. Websites externos são operados independentemente e podem ter seus próprios termos e restrições.",
        "download": "Baixar",
        "admin": "Admin",
        "find_platform": "Encontrar plataforma",
    },
}

DEFAULT_LINKS = [
    ("YouTube", "Videos · Shorts", "https://app.ytdown.to/en38/", "youtube"),
    ("Facebook", "Videos · Reels", "https://fdown.net/", "facebook"),
    ("Instagram", "Reels · Posts", "https://snapinst.app/", "instagram"),
    ("TikTok", "Videos · Clips", "https://snaptik.app/", "tiktok"),
    ("X", "Videos · Posts", "https://ssstwitter.com/", "x"),
    ("LinkedIn", "Videos · Posts", "https://publer.io/tools/linkedin-video-downloader", "linkedin"),
]


def detect_locale(accept_language=None, country_code=None):
    if accept_language:
        for entry in accept_language.split(","):
            lang_code = entry.split(";")[0].strip().lower()
            if not lang_code:
                continue
            normalized = lang_code.split("-")[0]
            if normalized in LANGUAGE_TRANSLATIONS:
                return normalized
    country = (country_code or "").upper()
    country_map = {
        "US": "en", "GB": "en", "CA": "en", "AU": "en",
        "ES": "es", "MX": "es", "AR": "es", "CL": "es", "CO": "es",
        "FR": "fr", "BE": "fr", "CA": "fr",
        "BR": "pt", "PT": "pt", "MZ": "pt",
    }
    return country_map.get(country, "en")


def get_translations(locale=None):
    key = (locale or "en").split("-")[0].lower()
    return LANGUAGE_TRANSLATIONS.get(key, LANGUAGE_TRANSLATIONS["en"]).copy()


@app.before_request
def set_request_locale():
    g.locale = detect_locale(request.headers.get("Accept-Language"), request.headers.get("CF-IPCountry"))
    g.i18n = get_translations(g.locale)

def db():
    if is_postgres_database():
        return PostgresConnection(os.environ["DATABASE_URL"])
    db_dir = os.path.dirname(os.path.abspath(DB_PATH))
    os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    return conn

def init_db():
    postgres_mode = is_postgres_database()
    with db() as con:
        if postgres_mode:
            con.execute("""CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS links (
                id BIGSERIAL PRIMARY KEY, platform TEXT UNIQUE NOT NULL,
                subtitle TEXT NOT NULL DEFAULT '', url TEXT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT TRUE, sort_order INTEGER NOT NULL DEFAULT 0
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS visits (
                id BIGSERIAL PRIMARY KEY, created_at TEXT NOT NULL,
                day TEXT NOT NULL, visitor_hash TEXT NOT NULL, path TEXT NOT NULL,
                referrer TEXT NOT NULL DEFAULT '', country TEXT NOT NULL DEFAULT ''
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS clicks (
                id BIGSERIAL PRIMARY KEY, created_at TEXT NOT NULL,
                day TEXT NOT NULL, platform TEXT NOT NULL, visitor_hash TEXT NOT NULL
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS admin_users (
                username TEXT PRIMARY KEY, password_hash TEXT NOT NULL
            )""")
            con.execute("ALTER TABLE links ALTER COLUMN enabled TYPE BOOLEAN USING (enabled::text IN ('1','t','true'))")
            con.execute("ALTER TABLE links ALTER COLUMN enabled SET DEFAULT TRUE")
        else:
            con.execute("""CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT UNIQUE NOT NULL,
                subtitle TEXT NOT NULL DEFAULT '', url TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1, sort_order INTEGER NOT NULL DEFAULT 0
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
                day TEXT NOT NULL, visitor_hash TEXT NOT NULL, path TEXT NOT NULL,
                referrer TEXT NOT NULL DEFAULT '', country TEXT NOT NULL DEFAULT ''
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
                day TEXT NOT NULL, platform TEXT NOT NULL, visitor_hash TEXT NOT NULL
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS admin_users (
                username TEXT PRIMARY KEY, password_hash TEXT NOT NULL
            )""")
        existing = con.execute("SELECT COUNT(*) n FROM links").fetchone()["n"]
        if not existing:
            con.executemany("INSERT INTO links(platform,subtitle,url,enabled,sort_order) VALUES(?,?,?,?,?)",
                            [(p,s,u,enabled_value(True),i) for i,(p,s,u,slug) in enumerate(DEFAULT_LINKS)])
        else:
            con.execute("UPDATE links SET url=? WHERE platform=? AND url!=?", (DEFAULT_LINKS[0][2], "YouTube", DEFAULT_LINKS[0][2]))
        existing_user = con.execute("SELECT username,password_hash FROM admin_users WHERE username=?", (ADMIN_USER,)).fetchone()
        local_fallback_password = "ChangeMeNow-2026!"
        if existing_user and check_password_hash(existing_user["password_hash"], local_fallback_password):
            if postgres_mode and not ADMIN_PASSWORD:
                raise RuntimeError("Set ADMIN_PASSWORD to replace the local fallback before hosting.")
            if ADMIN_PASSWORD:
                con.execute("UPDATE admin_users SET password_hash=? WHERE username=?",
                            (generate_password_hash(ADMIN_PASSWORD), ADMIN_USER))
        elif not existing_user:
            if postgres_mode and not ADMIN_PASSWORD:
                raise RuntimeError("Set ADMIN_PASSWORD before initializing the hosted PostgreSQL database.")
            configured_password = ADMIN_PASSWORD or local_fallback_password
            con.execute("INSERT INTO admin_users(username,password_hash) VALUES(?,?)",
                        (ADMIN_USER, generate_password_hash(configured_password)))
        if ADMIN_PASSWORD:
            con.execute("DELETE FROM admin_users WHERE username != ?", (ADMIN_USER,))
        con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    ("site_subtitle", "Video Downloader Directory"))
        con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    ("announcement", ""))
        con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    ("seo_title", "QuickSave - Video Downloader Directory"))
        con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    ("seo_description", "Find useful external video download tools for YouTube, Facebook, Instagram, TikTok, X and LinkedIn in one simple directory."))
        con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    ("seo_keywords", "video downloader, social media video tools, YouTube video tools, Facebook video tools, Instagram Reels tools, TikTok video tools"))
        con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    ("seo_image_url", ""))
init_db()

def utc_now():
    return datetime.now(timezone.utc)

def visitor_id():
    # A rotating daily salted hash avoids storing raw IP addresses.
    ip = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or "unknown"
    day = utc_now().strftime("%Y-%m-%d")
    salt = os.environ.get("ANALYTICS_SALT", app.secret_key)
    return hashlib.sha256(f"{day}|{salt}|{ip}".encode()).hexdigest()

@app.before_request
def record_visit():
    if request.path.startswith("/admin") or request.path.startswith("/static") or request.path.startswith("/health"):
        return
    if request.path.startswith("/go/"):
        return
    try:
        now = utc_now()
        ref = (request.referrer or "")[:500]
        country = (request.headers.get("CF-IPCountry") or "")[:8]
        with db() as con:
            con.execute("INSERT INTO visits(created_at,day,visitor_hash,path,referrer,country) VALUES(?,?,?,?,?,?)",
                        (now.isoformat(), now.strftime("%Y-%m-%d"), visitor_id(), request.path[:200], ref, country))
    except Exception:
        app.logger.exception("Analytics visit write failed")

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin_user"):
            return redirect(url_for("admin_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped

def get_setting(key, default=""):
    with db() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

def seo_context(title=None, description=None, canonical=None):
    root = request.url_root.rstrip("/")
    default_title = get_setting("seo_title", "QuickSave - Video Downloader Directory")
    default_description = get_setting("seo_description", "Find useful external video download tools for popular social platforms.")
    return {
        "title": (title or default_title)[:160],
        "description": (description or default_description)[:320],
        "keywords": get_setting("seo_keywords", ""),
        "canonical": canonical or request.base_url,
        "og_image": get_setting("seo_image_url", "").strip(),
        "site_url": root,
    }

@app.route("/robots.txt")
def robots_txt():
    from flask import Response
    root = request.url_root.rstrip("/")
    body = f"""User-agent: *
Allow: /
Disallow: /admin
Disallow: /go/
Sitemap: {root}/sitemap.xml
"""
    return Response(body, mimetype="text/plain")

@app.route("/sitemap.xml")
def sitemap_xml():
    from flask import Response
    from xml.sax.saxutils import escape
    root = request.url_root.rstrip("/")
    urls = [(root + "/", "daily", "1.0")]
    with db() as con:
        links = con.execute(f"SELECT platform FROM links WHERE {enabled_where_clause()} ORDER BY sort_order,platform").fetchall()
    for row in links:
        slug = row["platform"].lower().replace(" ", "-")
        urls.append((root + "/tools/" + slug, "weekly", "0.8"))
    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, freq, priority in urls:
        body.append(f"<url><loc>{escape(loc)}</loc><changefreq>{freq}</changefreq><priority>{priority}</priority></url>")
    body.append("</urlset>")
    return Response("\\n".join(body), mimetype="application/xml")

@app.route("/tools/<slug>")
def tool_page(slug):
    with db() as con:
        all_links = con.execute(f"SELECT * FROM links WHERE {enabled_where_clause()} ORDER BY sort_order,platform").fetchall()
    chosen = None
    for link in all_links:
        if link["platform"].lower().replace(" ", "-") == slug.lower():
            chosen = link
            break
    if not chosen:
        abort(404)
    platform = chosen["platform"]
    description = f"Explore QuickSave's directory entry for {platform}. Find the external tool link and review basic guidance before continuing."
    seo = seo_context(
        title=f"{platform} Video Download Tools | QuickSave",
        description=description,
        canonical=request.base_url
    )
    return render_template("tool.html", link=chosen, links=all_links, seo=seo, subtitle=get_setting("site_subtitle", "Video Downloader Directory"))

@app.route("/")
def home():
    with db() as con:
        links = con.execute(f"SELECT * FROM links WHERE {enabled_where_clause()} ORDER BY sort_order, platform").fetchall()
    seo = seo_context()
    ads = []
    for slot in (1, 2):
        url = get_setting(f"ad_slot_{slot}_url", "").strip()
        image = get_setting(f"ad_slot_{slot}_image", "").strip()
        title = get_setting(f"ad_slot_{slot}_title", "Ad").strip() or f"Ad {slot}"
        if url and valid_external_url(url):
            ads.append({"slot": slot, "url": url, "image": image, "title": title})
    return render_template("index.html", links=links, site_name=SITE_NAME,
                           subtitle=get_setting("site_subtitle", "Video Downloader Directory"),
                           announcement=get_setting("announcement", ""), seo=seo, ads=ads)

@app.route("/go/<int:link_id>")
def go(link_id):
    with db() as con:
        link = con.execute(f"SELECT * FROM links WHERE id=? AND {enabled_where_clause()}", (link_id,)).fetchone()
        if not link:
            abort(404)
        now = utc_now()
        con.execute("INSERT INTO clicks(created_at,day,platform,visitor_hash) VALUES(?,?,?,?)",
                    (now.isoformat(), now.strftime("%Y-%m-%d"), link["platform"], visitor_id()))
        target = link["url"]
    return redirect(target, code=302)

@app.route("/health")
def health():
    return jsonify(status="ok", app="QuickSave")

@app.route("/admin")
@admin_required
def admin_dashboard():
    period = request.args.get("period", "7")
    if period not in ("7", "30", "90"):
        period = "7"
    since = (utc_now().date() - timedelta(days=int(period)-1)).isoformat()
    today = utc_now().strftime("%Y-%m-%d")
    with db() as con:
        total_visits = con.execute("SELECT COUNT(*) n FROM visits").fetchone()["n"]
        today_visits = con.execute("SELECT COUNT(*) n FROM visits WHERE day=?", (today,)).fetchone()["n"]
        today_unique = con.execute("SELECT COUNT(DISTINCT visitor_hash) n FROM visits WHERE day=?", (today,)).fetchone()["n"]
        page_views = con.execute("SELECT COUNT(*) n FROM visits WHERE day>=?", (since,)).fetchone()["n"]
        clicks_total = con.execute("SELECT COUNT(*) n FROM clicks").fetchone()["n"]
        link_stats = con.execute("""SELECT l.platform,l.enabled,l.url,
            (SELECT COUNT(*) FROM clicks c WHERE c.platform=l.platform AND c.day=?) today_clicks,
            (SELECT COUNT(*) FROM clicks c WHERE c.platform=l.platform AND c.day>=?) period_clicks
            FROM links l ORDER BY l.sort_order,l.platform""", (today, since)).fetchall()
        daily = con.execute("""SELECT day,COUNT(*) visits,COUNT(DISTINCT visitor_hash) unique_visitors
            FROM visits WHERE day>=? GROUP BY day ORDER BY day""", (since,)).fetchall()
        recent = con.execute("SELECT created_at,path,referrer,country FROM visits ORDER BY id DESC LIMIT 12").fetchall()
        top_refs = con.execute("""SELECT CASE WHEN referrer='' THEN 'Direct / unknown'
            ELSE substr(referrer,1,100) END source,COUNT(*) n FROM visits WHERE day>=?
            GROUP BY source ORDER BY n DESC LIMIT 8""", (since,)).fetchall()
    return render_template("admin.html", total_visits=total_visits, today_visits=today_visits,
        today_unique=today_unique, page_views=page_views, clicks_total=clicks_total,
        link_stats=link_stats, daily=daily, recent=recent, top_refs=top_refs, period=period,
        username=session.get("admin_user"))

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if session.get("admin_user"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        with db() as con:
            row = con.execute("SELECT * FROM admin_users WHERE username=?", (username,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session.clear()
            session["admin_user"] = username
            session.permanent = True
            app.permanent_session_lifetime = timedelta(hours=8)
            return redirect(request.args.get("next") if request.args.get("next","").startswith("/admin") else url_for("admin_dashboard"))
        flash("Incorrect username or password.", "error")
    return render_template("login.html")

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

def valid_external_url(value):
    try:
        parsed = urlparse(value.strip())
        return parsed.scheme in ("https", "http") and bool(parsed.netloc) and "." in parsed.netloc
    except Exception:
        return False

@app.route("/admin/links", methods=["GET","POST"])
@admin_required
def admin_links():
    if request.method == "POST":
        action = request.form.get("action", "save")
        with db() as con:
            if action == "save":
                rows = con.execute("SELECT id FROM links").fetchall()
                for row in rows:
                    lid = row["id"]
                    platform = request.form.get(f"platform_{lid}","").strip()[:40]
                    subtitle = request.form.get(f"subtitle_{lid}","").strip()[:100]
                    url = request.form.get(f"url_{lid}","").strip()
                    enabled = enabled_value(request.form.get(f"enabled_{lid}") == "on")
                    if not platform or not valid_external_url(url):
                        flash(f"Platform #{lid}: enter a name and a valid http/https URL.", "error")
                        return redirect(url_for("admin_links"))
                    con.execute("UPDATE links SET platform=?,subtitle=?,url=?,enabled=? WHERE id=?",
                                    (platform,subtitle,url,enabled,lid))
                flash("Download links saved.", "success")
            elif action == "add":
                platform = request.form.get("new_platform","").strip()[:40]
                subtitle = request.form.get("new_subtitle","").strip()[:100]
                url = request.form.get("new_url","").strip()
                if not platform or not valid_external_url(url):
                    flash("Enter a platform name and a valid http/https URL.", "error")
                else:
                    try:
                        next_order = con.execute("SELECT COALESCE(MAX(sort_order),0)+1 n FROM links").fetchone()["n"]
                        con.execute("INSERT INTO links(platform,subtitle,url,enabled,sort_order) VALUES(?,?,?,?,?)",
                                    (platform,subtitle,url,enabled_value(True),next_order))
                        flash("Platform added.", "success")
                    except sqlite3.IntegrityError:
                        flash("That platform name already exists. Use a unique name.", "error")
        return redirect(url_for("admin_links"))
    with db() as con:
        links = con.execute("SELECT * FROM links ORDER BY sort_order,platform").fetchall()
    return render_template("links.html", links=links)

@app.route("/admin/settings", methods=["GET","POST"])
@admin_required
def admin_settings():
    if request.method == "POST":
        subtitle = request.form.get("subtitle","").strip()[:100]
        announcement = request.form.get("announcement","").strip()[:300]
        seo_title = request.form.get("seo_title","").strip()[:160]
        seo_description = request.form.get("seo_description","").strip()[:320]
        seo_keywords = request.form.get("seo_keywords","").strip()[:500]
        seo_image_url = request.form.get("seo_image_url","").strip()[:500]
        ad_slot_1_title = request.form.get("ad_slot_1_title","").strip()[:80]
        ad_slot_1_url = request.form.get("ad_slot_1_url","").strip()[:500]
        ad_slot_1_image = request.form.get("ad_slot_1_image","").strip()[:500]
        ad_slot_2_title = request.form.get("ad_slot_2_title","").strip()[:80]
        ad_slot_2_url = request.form.get("ad_slot_2_url","").strip()[:500]
        ad_slot_2_image = request.form.get("ad_slot_2_image","").strip()[:500]
        if seo_image_url and not valid_external_url(seo_image_url):
            flash("Social sharing image must be a full http/https URL.", "error")
            return redirect(url_for("admin_settings"))
        for slot_name, slot_url, slot_image in (("ad_slot_1_url", ad_slot_1_url, ad_slot_1_image), ("ad_slot_2_url", ad_slot_2_url, ad_slot_2_image)):
            if slot_url and not valid_external_url(slot_url):
                flash(f"{slot_name.replace('_', ' ').title()} must be a full http/https URL.", "error")
                return redirect(url_for("admin_settings"))
            if slot_image and not valid_external_url(slot_image):
                flash(f"{slot_name.replace('_', ' ').title()} image must be a full http/https URL.", "error")
                return redirect(url_for("admin_settings"))
        with db() as con:
            values = {
                "site_subtitle": subtitle,
                "announcement": announcement,
                "seo_title": seo_title,
                "seo_description": seo_description,
                "seo_keywords": seo_keywords,
                "seo_image_url": seo_image_url,
                "ad_slot_1_title": ad_slot_1_title or "Ad 1",
                "ad_slot_1_url": ad_slot_1_url,
                "ad_slot_1_image": ad_slot_1_image,
                "ad_slot_2_title": ad_slot_2_title or "Ad 2",
                "ad_slot_2_url": ad_slot_2_url,
                "ad_slot_2_image": ad_slot_2_image,
            }
            for key, value in values.items():
                con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key,value))
        flash("Website and SEO settings saved.", "success")
        return redirect(url_for("admin_settings"))
    return render_template("settings.html", subtitle=get_setting("site_subtitle","Video Downloader Directory"),
                           announcement=get_setting("announcement",""),
                           seo_title=get_setting("seo_title","QuickSave - Video Downloader Directory"),
                           seo_description=get_setting("seo_description","Find useful external video download tools for popular social platforms."),
                           seo_keywords=get_setting("seo_keywords","video downloader, social media video tools"),
                           seo_image_url=get_setting("seo_image_url",""),
                           ad_slot_1_title=get_setting("ad_slot_1_title","Ad 1"),
                           ad_slot_1_url=get_setting("ad_slot_1_url",""),
                           ad_slot_1_image=get_setting("ad_slot_1_image",""),
                           ad_slot_2_title=get_setting("ad_slot_2_title","Ad 2"),
                           ad_slot_2_url=get_setting("ad_slot_2_url",""),
                           ad_slot_2_image=get_setting("ad_slot_2_image",""))

@app.route("/admin/password", methods=["GET","POST"])
@admin_required
def admin_password():
    if request.method == "POST":
        current = request.form.get("current_password","")
        new = request.form.get("new_password","")
        confirm = request.form.get("confirm_password","")
        with db() as con:
            row = con.execute("SELECT * FROM admin_users WHERE username=?", (session["admin_user"],)).fetchone()
            if not row or not check_password_hash(row["password_hash"], current):
                flash("Current password is incorrect.", "error")
            elif len(new) < 12:
                flash("Use at least 12 characters for the new password.", "error")
            elif new != confirm:
                flash("The new passwords do not match.", "error")
            else:
                con.execute("UPDATE admin_users SET password_hash=? WHERE username=?",
                            (generate_password_hash(new), session["admin_user"]))
                flash("Password changed successfully.", "success")
                return redirect(url_for("admin_dashboard"))
    return render_template("password.html")

@app.route("/admin/export.csv")
@admin_required
def export_csv():
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date","visits","unique_visitors","download_clicks"])
    with db() as con:
        days = con.execute("""SELECT d.day,COALESCE(v.visits,0),COALESCE(v.unique_visitors,0),COALESCE(c.clicks,0)
          FROM (SELECT day FROM visits UNION SELECT day FROM clicks) d
          LEFT JOIN (SELECT day,COUNT(*) visits,COUNT(DISTINCT visitor_hash) unique_visitors FROM visits GROUP BY day) v ON v.day=d.day
          LEFT JOIN (SELECT day,COUNT(*) clicks FROM clicks GROUP BY day) c ON c.day=d.day
          ORDER BY d.day DESC""").fetchall()
    for row in days:
        writer.writerow(list(row))
    from flask import Response
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":"attachment; filename=quicksave-analytics.csv"})

@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
