# OpenScout

Free, open-source B2B lead generator. Give it a domain ("fintech startups", "bakeries in Austin") plus an optional country/headcount range — it pulls live company sites, scores them with an LLM, extracts verified contacts, and streams everything to your browser in real time.

Built because pay-to-get-leads platforms are mostly recycled junk.

Built by [RavenDOS](https://ravendos.com).

---

## Stack

- **Scrapling** — stealth + adaptive web scraping (Playwright under the hood)
- **Groq** (Llama 3.3 70B) — query expansion, lead scoring, contact extraction
- **FastAPI + SSE** — backend + live streaming
- **SQLite** — single `leads.db` file, all sessions stored
- **Vanilla HTML + Tailwind CDN** — no build step

---

## Quick start (one command)

```bash
python startup.py
```

This installs all Python deps, installs the Playwright Chromium runtime, copies `.env.example` to `.env` if missing, launches the server, and opens your browser.

You still need a Groq API key (see below).

## Manual install

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env       # Windows: copy .env.example .env
python main.py
```

Open http://127.0.0.1:8000

---

## Get a free Groq API key

1. Visit https://console.groq.com/keys
2. Sign up (free) and create a key
3. Paste it into `.env` as `GROQ_API_KEY=gsk_...`

Groq's free tier is **very** generous — Llama 3.3 70B at fast speeds, more than enough for normal lead-gen use. No credit card required. You won't hit limits in casual use.

---

## Use

1. **Search tab** — enter domain, country (optional), headcount range (optional), limit. Hit Start.
2. **Live tab** — leads stream in as the engine finds them. Activity log shows what's happening.
3. **History tab** — every past search and its leads. Export any session to CSV.

## Pipeline

```
LLM expands query  →  SERP scrape (DDG + Bing fallback)  →  dedupe domains
   →  LLM scores each candidate  →  stealth-fetch top sites
   →  regex + LLM extract contacts  →  stream to UI + DB
```

One search at a time. SQLite stores every session so you can revisit later.

---

## Configuration

`.env`:

```
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile   # or llama-3.1-8b-instant for cheaper/faster
DB_PATH=leads.db
HOST=127.0.0.1
PORT=8000
```

---

## Ethics

- Respect target sites — engine rate-limits itself.
- Don't spam scraped contacts. Cold outreach without consent is illegal in many jurisdictions (GDPR, CAN-SPAM).
- This tool finds leads. What you do with them is on you.

---

## Need a custom build?

If you want a customised lead-gen system, CRM integration, multi-source enrichment, outreach automation, or anything else built on top of this — reach out via the RavenDOS contact form: **https://www.ravendos.com/contact**

Questions, doubts, or feedback? Message me directly on LinkedIn: **https://www.linkedin.com/in/rahul-morathoti-23814522a/**

---

## License

MIT. Use it, fork it, ship it.
