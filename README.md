<div align="center">

# 🛰️ OpenScout

### Free, open-source B2B lead generator powered by AI

*Tell it a domain. It pulls live company sites, scores them with an LLM, extracts verified contacts, streams everything to your browser — in real time.*

[![Python](https://img.shields.io/badge/python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Groq](https://img.shields.io/badge/Groq-Llama_3.3_70B-F55036?style=for-the-badge&logo=meta&logoColor=white)](https://console.groq.com/)
[![Scrapling](https://img.shields.io/badge/Scrapling-Stealth-8A2BE2?style=for-the-badge)](https://github.com/D4Vinci/Scrapling)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

[![Built by RavenDOS](https://img.shields.io/badge/Built_by-RavenDOS-10b981?style=for-the-badge)](https://ravendos.com)

</div>

---

## 💡 Why this exists

Pay-to-get-leads platforms are mostly recycled junk. OpenScout pulls **live** data from the open web, scores it with a frontier LLM, and gives you contacts that actually exist — for free.

---

## ⚡ Quick start (one command)

```bash
python startup.py
```

That's it. Script installs every Python dep, downloads the Playwright Chromium runtime, copies `.env.example` → `.env` if missing, fires the server, opens your browser.

You only need a **free Groq API key** (see below).

### Manual install

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env       # Windows: copy .env.example .env
python main.py
```

Open 👉 http://127.0.0.1:8000

---

## 🔑 Get a free Groq API key

1. Visit 👉 **https://console.groq.com/keys**
2. Sign up (free, no credit card) and create a key
3. Paste it into `.env` as `GROQ_API_KEY=gsk_...`

> 💚 Groq's free tier is **very generous** — Llama 3.3 70B at blazing speed. You won't hit limits in normal lead-gen use. Don't worry about cost.

---

## 🧱 Stack

| Layer            | Tech                                             |
| ---------------- | ------------------------------------------------ |
| 🕷️ Scraping      | **Scrapling** (stealth + adaptive, Playwright)   |
| 🧠 LLM           | **Groq** Llama 3.3 70B                           |
| ⚡ Backend       | **FastAPI** + Server-Sent Events                 |
| 💾 Storage       | **SQLite** (single `leads.db`)                   |
| 🎨 UI            | Vanilla HTML + Tailwind CDN — no build step      |

---

## 🛠️ How to use

| Tab          | What it does                                                                  |
| ------------ | ----------------------------------------------------------------------------- |
| 🔎 Search    | Domain + country + headcount range + limit. Hit **Start**.                    |
| 📡 Live      | Leads stream in real time. Activity log shows every step.                     |
| 📜 History   | Every past search + leads. Export to CSV.                                     |

---

## 🔁 Pipeline

```
   ┌────────────┐    ┌─────────────┐    ┌──────────┐    ┌────────────┐    ┌────────────┐
   │ LLM expand │ -> │ SERP scrape │ -> │ Dedupe & │ -> │  Stealth   │ -> │  Extract   │
   │   query    │    │  DDG + Bing │    │  Score   │    │   Fetch    │    │  Contacts  │
   └────────────┘    └─────────────┘    └──────────┘    └────────────┘    └─────┬──────┘
                                                                                 │
                                                                       ┌─────────▼─────────┐
                                                                       │  Stream → UI + DB │
                                                                       └───────────────────┘
```

One search at a time. Every session persisted to SQLite — revisit anytime.

---

## ⚙️ Configuration

`.env`:

```dotenv
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile   # or llama-3.1-8b-instant for cheaper/faster
DB_PATH=leads.db
HOST=127.0.0.1
PORT=8000
```

---

## ⚖️ Ethics

- 🤝 Engine rate-limits itself — be a good web citizen.
- 🚫 Don't spam scraped contacts. Cold outreach without consent is illegal in many jurisdictions (GDPR, CAN-SPAM, etc.).
- 🧭 OpenScout finds leads. What you do with them is on you.

---

<div align="center">

##  Need a custom AI / ML solution?

**RavenDOS builds production AI & ML systems** — agentic pipelines, RAG, custom fine-tunes,
multi-source enrichment, computer vision, NLP, forecasting, recommender systems,
end-to-end data + model infrastructure.

If OpenScout is close to what you need but not quite — or you want something far more
ambitious built around your data and workflow — we ship.

### 🛎️ [Fill out the contact form →](https://www.ravendos.com/contact)

Quick questions, doubts, or feedback? DM me on LinkedIn:

### 💬 [linkedin.com/in/rahul-morathoti](https://www.linkedin.com/in/rahul-morathoti-23814522a/)

</div>

---

<div align="center">

### ⭐ If OpenScout saves you time, drop a star — it helps a lot.

**MIT licensed. Use it, fork it, ship it.**

Built with ❤️ by [**RavenDOS**](https://ravendos.com)

</div>
