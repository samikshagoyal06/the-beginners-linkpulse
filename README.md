# LinkPulse: URL Shortener & Analytics Platform

**Team: The Beginners** | Tech Geeks Hackathon, Round 2 (Implementation)
Graphic Era Hill University, Haldwani | BCA (AI & Data Science), 1st Year

**Live link:** https://REPLACE-WITH-YOUR-LIVE-LINK

> Note: the live app runs on a free host. If it was idle, the first page load can take about a minute while it wakes up. Demo data is added automatically when the database is empty.

**Team members:** Samiksha, Savhi Singh Koranga, Swastika Pandey, Sakshi Dobal

## Problem Statement
A short link is useful, but small teams (college clubs, event organizers, student projects, creators, small businesses) also need a simple way to see whether people open it, keep links organized, and stop a link when it should no longer work. Many basic shorteners only map a code to a URL, with little control and little useful data.

## Solution
LinkPulse manages the full life of a short link: **create, protect with rules, redirect, track clicks, analyze, and disable**. Every redirect is driven by data in the database, and expired or disabled links keep their click history.

**Edge case handled first:** if someone opens a code that does not exist, LinkPulse shows a clear error page instead of crashing or redirecting wrongly.

## Features
| Feature | Details |
|---|---|
| Create short links | Automatic 6-character code or a custom alias |
| Validation before saving | Invalid URL, duplicate alias, reserved words, past expiry date, bad click limit, `http` warning |
| Rules | Optional expiry date and click limit |
| Redirect engine | Checks: link exists, not disabled, not expired, under click limit |
| Click tracking | Time, referrer, browser, device; bot visits are saved but not counted |
| Dashboard | Total links, real clicks, bot clicks, clicks per day (last 7 days), browsers, devices, all links |
| Admin controls | Disable / enable a link; its analytics stay |
| QR codes | Generated for every short link |
| Clear error pages | Unknown code, expired, disabled, limit reached |

## Tech Stack
| Part | Technology |
|---|---|
| Backend | Python, Flask |
| Database | SQLite |
| Frontend | HTML, CSS (Jinja templates) |
| Libraries | qrcode (QR codes), gunicorn (production server) |
| Hosting | Render (free) |

## How a click is handled
1. Visitor opens `/<code>`.
2. The app looks up the code in SQLite. Not found: error page (404).
3. Rules are checked in order: disabled, expired, click limit. If one fails: error page (410).
4. The click is saved (time, referrer, browser, device, bot flag). Real clicks increase the click count.
5. The visitor is redirected to the original website.

## Screenshots
| Home page | Short link created |
|---|---|
| ![Home](screenshots/home.png) | ![Created](screenshots/short-link-created.png) |

| Dashboard | Error page (unknown code) |
|---|---|
| ![Dashboard](screenshots/dashboard.png) | ![Error](screenshots/error-page.png) |

## Setup Instructions (run on your own computer)
1. Install Python 3 from python.org (tick "Add Python to PATH").
2. Download or clone this repository and open the folder in a terminal.
3. Create a virtual environment and install the requirements:
```
python -m venv venv
venv\Scripts\activate          (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
```
4. Start the app:
```
python app.py
```
5. Open http://127.0.0.1:5000 in your browser.

Optional: `python seed.py` adds sample links and clicks. Sample data is also added automatically when the database is empty (set `SEED_DEMO_DATA=0` to turn this off).

## Deploy (Render)
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`

## Project Structure
```
app.py            all the logic (routes, rules, click tracking)
seed.py           adds sample data
templates/        HTML pages
static/style.css  design
requirements.txt  Python packages
```

## Future Work
Login for each user, password-protected links, CSV bulk import, campaigns and tags, rate limiting on link creation, location tracking, custom domains, public API.

## Limitations (honest notes)
- No login yet: anyone can open the dashboard and disable links.
- Free hosting can erase the SQLite file when the app restarts, so links created online may disappear. Demo data is re-added automatically.
