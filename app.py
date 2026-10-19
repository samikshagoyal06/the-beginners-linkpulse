"""LinkPulse - a beginner-friendly URL shortener with click tracking.
Built with Python + Flask + SQLite + HTML/CSS.

How to read this file (top to bottom):
  1. Settings and the database tables
  2. Small helper functions (check URL, make code, read browser)
  3. Pages: create link (/), redirect (/<code>), dashboard, QR, disable/enable
"""
import os
import random
import re
import sqlite3
import string
from datetime import datetime, timezone, timedelta
from io import BytesIO
from urllib.parse import urlparse

import qrcode
from flask import Flask, render_template, request, redirect, g, send_file

app = Flask(__name__)

# ---------- 1. Settings and database ----------
BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("LINKPULSE_DB", os.path.join(BASE_FOLDER, "linkpulse.db"))

# Words that cannot be used as a custom alias (they are real pages of our app)
RESERVED = {"dashboard", "qr", "disable", "enable", "static", "admin", "api"}
ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,30}$")
# If the browser name contains one of these words, we treat the visit as a bot
BOT_WORDS = ["bot", "spider", "crawl", "curl", "wget", "python-requests", "preview"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,          -- the short code, e.g. abc123
    destination_url TEXT NOT NULL,      -- the original long URL
    created_at TEXT NOT NULL,
    expires_on TEXT,                    -- optional, format YYYY-MM-DD
    click_limit INTEGER,                -- optional maximum number of clicks
    click_count INTEGER NOT NULL DEFAULT 0,   -- real (non-bot) clicks
    is_active INTEGER NOT NULL DEFAULT 1      -- 0 means disabled
);
CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id INTEGER NOT NULL,
    clicked_at TEXT NOT NULL,
    referrer TEXT,
    browser TEXT,
    device TEXT,
    is_bot INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (link_id) REFERENCES links (id)
);
"""


def now_utc():
    return datetime.now(timezone.utc)


def get_db():
    """Open the database once per request."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row  # lets us write row["code"]
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    db.commit()
    db.close()


def seed_demo_data():
    """Adds sample links and clicks so the dashboard is not empty (used by seed.py and on first start)."""
    db = sqlite3.connect(DB_PATH)
    now = now_utc()
    yesterday = (now - timedelta(days=1)).date().isoformat()
    # (code, destination, expires_on)
    samples = [
        ("python", "https://www.python.org", None),
        ("flask", "https://flask.palletsprojects.com", None),
        ("github", "https://github.com", None),
        ("wiki", "https://www.wikipedia.org", None),
        ("club-event", "https://www.example.com/college-club-event", None),
        ("old-offer", "https://www.example.com/old-offer", yesterday),  # an expired link
    ]
    browsers = ["Chrome", "Chrome", "Chrome", "Edge", "Firefox", "Safari"]
    devices = ["Mobile", "Mobile", "Desktop"]
    referrers = ["Direct", "https://www.instagram.com/", "https://web.whatsapp.com/", "https://www.google.com/"]
    for code, url, expires in samples:
        cur = db.execute("INSERT OR IGNORE INTO links (code, destination_url, created_at, expires_on) "
                         "VALUES (?, ?, ?, ?)", (code, url, (now - timedelta(days=7)).isoformat(), expires))
        if cur.rowcount == 0:
            continue  # already there
        real = 0
        for _ in range(random.randint(5, 30)):
            when = now - timedelta(days=random.randint(0, 6), hours=random.randint(0, 23))
            is_bot = 1 if random.random() < 0.1 else 0
            db.execute("INSERT INTO clicks (link_id, clicked_at, referrer, browser, device, is_bot) "
                       "VALUES (?, ?, ?, ?, ?, ?)",
                       (cur.lastrowid, when.isoformat(), random.choice(referrers), random.choice(browsers),
                        random.choice(devices), is_bot))
            real += 1 - is_bot
        db.execute("UPDATE links SET click_count = ? WHERE id = ?", (real, cur.lastrowid))
    db.commit()
    db.close()


init_db()
# Free hosting can erase the database file when the app restarts, so we add demo data
# automatically when the database is empty. Set SEED_DEMO_DATA=0 to turn this off.
if os.environ.get("SEED_DEMO_DATA", "1") == "1":
    _check = sqlite3.connect(DB_PATH)
    _empty = _check.execute("SELECT COUNT(*) FROM links").fetchone()[0] == 0
    _check.close()
    if _empty:
        seed_demo_data()


# ---------- 2. Helper functions ----------
def clean_url(raw):
    """Return (url, error). Adds https:// if the user forgot it."""
    raw = raw.strip()
    if not raw:
        return None, "Please enter a URL."
    if "://" not in raw:
        raw = "https://" + raw
    parts = urlparse(raw)
    if parts.scheme not in ("http", "https"):
        return None, "URL must start with http:// or https://"
    if not parts.netloc or "." not in parts.netloc:
        return None, "That does not look like a valid website address."
    return raw, None


def make_code(db):
    """Make a random 6-character code that is not already used."""
    letters = string.ascii_letters + string.digits
    while True:
        code = "".join(random.choices(letters, k=6))
        taken = db.execute("SELECT 1 FROM links WHERE code = ?", (code,)).fetchone()
        if not taken:
            return code


def read_user_agent(text):
    """Find out browser, device and whether it is a bot from the browser text."""
    low = text.lower()
    is_bot = any(word in low for word in BOT_WORDS)
    if "edg/" in low:
        browser = "Edge"
    elif "opr/" in low or "opera" in low:
        browser = "Opera"
    elif "chrome" in low or "crios" in low:
        browser = "Chrome"
    elif "firefox" in low or "fxios" in low:
        browser = "Firefox"
    elif "safari" in low:
        browser = "Safari"
    else:
        browser = "Other"
    device = "Mobile" if ("mobi" in low or "android" in low or "iphone" in low) else "Desktop"
    return browser, device, is_bot


def link_problem(link):
    """The RULES. Returns (status, message) if the link must NOT redirect, else (None, None).
    Order: disabled -> expired -> click limit."""
    if not link["is_active"]:
        return "disabled", "This link has been disabled by an admin."
    if link["expires_on"] and now_utc().date().isoformat() > link["expires_on"]:
        return "expired", "This link has expired."
    if link["click_limit"] is not None and link["click_count"] >= link["click_limit"]:
        return "limit reached", "This link has reached its click limit."
    return None, None


# ---------- 3. Pages ----------
@app.route("/", methods=["GET", "POST"])
def index():
    errors, warnings = [], []
    short_url = code = None
    if request.method == "POST":
        db = get_db()

        # Step 1: check the destination URL
        url, problem = clean_url(request.form.get("url", ""))
        if problem:
            errors.append(problem)
        elif urlparse(url).netloc == request.host:
            errors.append("You cannot shorten a LinkPulse link.")
        elif url.startswith("http://"):
            warnings.append("This website uses http (not https). It is allowed, but it is less secure.")

        # Step 2: check the custom alias (optional)
        alias = request.form.get("alias", "").strip()
        if alias:
            if not ALIAS_PATTERN.match(alias):
                errors.append("Alias must be 3-30 characters: letters, numbers, - or _ only.")
            elif alias.lower() in RESERVED:
                errors.append("'" + alias + "' is reserved. Please choose another alias.")
            elif db.execute("SELECT 1 FROM links WHERE code = ?", (alias,)).fetchone():
                errors.append("The alias '" + alias + "' is already taken.")

        # Step 3: check the rules (optional)
        expires_on = request.form.get("expires_on", "").strip() or None
        if expires_on:
            try:
                chosen = datetime.strptime(expires_on, "%Y-%m-%d").date()
                if chosen < now_utc().date():
                    errors.append("Expiry date cannot be in the past.")
            except ValueError:
                errors.append("Expiry date is not valid.")
        click_limit = request.form.get("click_limit", "").strip() or None
        if click_limit:
            if click_limit.isdigit() and int(click_limit) > 0:
                click_limit = int(click_limit)
            else:
                errors.append("Click limit must be a whole number above 0.")

        # Step 4: if everything is fine, save the link
        if not errors:
            code = alias or make_code(db)
            db.execute(
                "INSERT INTO links (code, destination_url, created_at, expires_on, click_limit) "
                "VALUES (?, ?, ?, ?, ?)",
                (code, url, now_utc().isoformat(), expires_on, click_limit),
            )
            db.commit()
            short_url = request.host_url + code
    return render_template("index.html", errors=errors, warnings=warnings,
                           short_url=short_url, code=code, form=request.form)


@app.route("/<code>")
def go(code):
    """The redirect engine: check the link, log the click, then redirect."""
    db = get_db()
    link = db.execute("SELECT * FROM links WHERE code = ?", (code,)).fetchone()

    # Edge case: the code does not exist -> clear error, no crash
    if link is None:
        return render_template("error.html", title="Link not found",
                               message="This short link does not exist. Please check the code and try again."), 404

    status, message = link_problem(link)
    if status:
        return render_template("error.html", title="Link unavailable (" + status + ")", message=message), 410

    # Log the click (bots are saved but flagged, and not counted)
    browser, device, is_bot = read_user_agent(request.headers.get("User-Agent", ""))
    db.execute(
        "INSERT INTO clicks (link_id, clicked_at, referrer, browser, device, is_bot) VALUES (?, ?, ?, ?, ?, ?)",
        (link["id"], now_utc().isoformat(), request.referrer or "Direct", browser, device, int(is_bot)),
    )
    if not is_bot:
        db.execute("UPDATE links SET click_count = click_count + 1 WHERE id = ?", (link["id"],))
    db.commit()
    return redirect(link["destination_url"], code=302)


@app.route("/dashboard")
def dashboard():
    db = get_db()
    links = db.execute("SELECT * FROM links ORDER BY click_count DESC, created_at DESC").fetchall()
    rows = []
    for link in links:
        status, _ = link_problem(link)
        rows.append({"link": link, "status": status or "active"})

    total_clicks = sum(link["click_count"] for link in links)
    bot_clicks = db.execute("SELECT COUNT(*) FROM clicks WHERE is_bot = 1").fetchone()[0]
    browsers = db.execute("SELECT browser, COUNT(*) AS n FROM clicks WHERE is_bot = 0 "
                          "GROUP BY browser ORDER BY n DESC").fetchall()
    devices = db.execute("SELECT device, COUNT(*) AS n FROM clicks WHERE is_bot = 0 "
                         "GROUP BY device ORDER BY n DESC").fetchall()

    # Clicks per day for the last 7 days
    today = now_utc().date()
    days = []
    for i in range(6, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        n = db.execute("SELECT COUNT(*) FROM clicks WHERE is_bot = 0 AND substr(clicked_at, 1, 10) = ?",
                       (day,)).fetchone()[0]
        days.append({"day": day, "count": n})
    biggest = max([d["count"] for d in days] + [1])
    for d in days:
        d["percent"] = int(d["count"] * 100 / biggest)

    return render_template("dashboard.html", rows=rows, total_links=len(links),
                           total_clicks=total_clicks, bot_clicks=bot_clicks,
                           browsers=browsers, devices=devices, days=days,
                           base=request.host_url)


@app.route("/disable/<code>", methods=["POST"])
def disable(code):
    db = get_db()
    db.execute("UPDATE links SET is_active = 0 WHERE code = ?", (code,))
    db.commit()
    return redirect("/dashboard")


@app.route("/enable/<code>", methods=["POST"])
def enable(code):
    db = get_db()
    db.execute("UPDATE links SET is_active = 1 WHERE code = ?", (code,))
    db.commit()
    return redirect("/dashboard")


@app.route("/qr/<code>.png")
def qr(code):
    db = get_db()
    link = db.execute("SELECT 1 FROM links WHERE code = ?", (code,)).fetchone()
    if link is None:
        return render_template("error.html", title="Link not found", message="No QR code for this link."), 404
    image = qrcode.make(request.host_url + code)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", title="Page not found",
                           message="This page does not exist."), 404


if __name__ == "__main__":
    app.run(debug=True)
