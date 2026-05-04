"""Lead-gen pipeline: LLM query expand -> SERP -> score -> site extract -> stream."""

import asyncio
import re
from typing import AsyncIterator
from urllib.parse import urlparse, urlencode, unquote

from scrapling.fetchers import FetcherSession, AsyncStealthySession

from llm.groq_client import expand_queries, score_lead, extract_contacts


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{8,}\d")
NON_EMAIL_TLDS = {"jpg", "jpeg", "png", "gif", "webp", "svg", "ico", "bmp",
                  "css", "js", "woff", "woff2", "ttf", "otf",
                  "mp4", "mp3", "webm", "pdf", "zip", "json", "xml", "html"}
LOW_VALUE_URL_PATTERNS = re.compile(
    r"/(blog|article|articles|news|press|posts?|magazine|insights?|guides?|"
    r"tutorials?|listicle|reviews?|categor(y|ies)|tag|tags|wiki|"
    r"compare|vs|alternatives?|directory|listings?|search|results?)(/|$)",
    re.IGNORECASE,
)
LISTICLE_RE = re.compile(
    r"^(\s*\d{1,3}\s*(?:\+|best|top|great|amazing|essential|must[- ]have)|"
    r"^(?:top|best|the\s+\d+)\s+\d+|"
    r"^how\s+to\b)",
    re.IGNORECASE,
)
SKIP_DOMAINS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
    "youtube.com", "tiktok.com", "pinterest.com", "wikipedia.org", "wikidata.org",
    "amazon.com", "ebay.com", "yelp.com", "tripadvisor.com", "indeed.com",
    "glassdoor.com", "crunchbase.com", "bloomberg.com", "reuters.com", "forbes.com",
    "g2.com", "capterra.com", "trustpilot.com", "bbb.org", "yellowpages.com",
    "google.com", "bing.com", "duckduckgo.com", "yahoo.com", "github.com",
    "medium.com", "substack.com", "wordpress.com", "blogspot.com", "quora.com",
}
GENERIC_EMAIL_PREFIX = {"noreply", "no-reply", "donotreply", "mailer-daemon", "postmaster", "example"}


def _root_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _is_skippable(url: str) -> bool:
    host = _root_domain(url)
    if not host:
        return True
    if any(host == s or host.endswith("." + s) for s in SKIP_DOMAINS):
        return True
    try:
        path = urlparse(url).path or ""
    except Exception:
        path = ""
    if LOW_VALUE_URL_PATTERNS.search(path):
        return True
    return False


def _clean_company_name(title: str, host: str) -> str:
    raw = (title or "").strip()
    looks_listicle = bool(LISTICLE_RE.match(raw))
    cleaned = re.sub(r"\s*[|\-—–·•]\s*.+$", "", raw).strip()
    if looks_listicle or not cleaned or len(cleaned) > 80:
        if host:
            return host.split(".")[0].replace("-", " ").title()
        return "Unknown"
    return cleaned


def _valid_email(e: str) -> bool:
    if "@" not in e:
        return False
    local, _, dom = e.partition("@")
    if not local or not dom or "." not in dom:
        return False
    tld = dom.rsplit(".", 1)[-1].lower()
    if tld in NON_EMAIL_TLDS:
        return False
    if any(c in local for c in ["/", "\\", "@"]):
        return False
    if len(e) > 100 or len(local) < 2:
        return False
    return True


def _ddg_search_sync(serp_session, query: str, max_results: int = 15) -> list[dict]:
    url = "https://html.duckduckgo.com/html/?" + urlencode({"q": query})
    try:
        page = serp_session.get(url, timeout=20)
    except Exception:
        return []
    results = []
    for row in page.css("div.result")[:max_results]:
        href = row.css("a.result__a::attr(href)").get() or ""
        if not href:
            continue
        m = re.search(r"uddg=([^&]+)", href)
        real = unquote(m.group(1)) if m else href
        title = row.css("a.result__a::text").get() or ""
        snippet = row.css("a.result__snippet::text").get() or ""
        if not snippet:
            snippet = " ".join(row.css("a.result__snippet *::text").getall())
        results.append({"title": str(title).strip(), "url": real, "snippet": str(snippet).strip()})
    return results


def _bing_search_sync(serp_session, query: str, max_results: int = 15) -> list[dict]:
    url = "https://www.bing.com/search?" + urlencode({"q": query})
    try:
        page = serp_session.get(url, timeout=20)
    except Exception:
        return []
    results = []
    for row in page.css("li.b_algo")[:max_results]:
        href = row.css("h2 a::attr(href)").get() or ""
        if not href:
            continue
        title = " ".join(t.strip() for t in row.css("h2 a *::text").getall() if t.strip())
        if not title:
            title = row.css("h2 a::text").get() or ""
        snippet = " ".join(t.strip() for t in row.css(".b_caption p *::text").getall() if t.strip())
        if not snippet:
            snippet = row.css(".b_caption p::text").get() or ""
        results.append({"title": str(title).strip(), "url": href, "snippet": str(snippet).strip()})
    return results


def _serp_run(query: str) -> list[dict]:
    """Sync helper run inside to_thread — opens its own short FetcherSession."""
    with FetcherSession(impersonate="chrome131") as s:
        results = _ddg_search_sync(s, query)
        if not results:
            results = _bing_search_sync(s, query)
    return results


async def _fetch_site_text(stealth_session, base_url: str, max_len: int = 8000) -> tuple[str, str]:
    text_chunks = []
    raw_html = ""
    for path in ["", "/contact", "/contact-us", "/about"]:
        target = base_url.rstrip("/") + path if path else base_url
        try:
            page = await stealth_session.fetch(target, timeout=20000)
            txt = page.text or ""
            if txt:
                text_chunks.append(txt[: max_len // 2])
            if not raw_html:
                raw_html = page.html_content or ""
            if path == "" and len("\n".join(text_chunks)) > max_len:
                break
        except Exception:
            continue
    return "\n".join(text_chunks)[:max_len], raw_html


def _regex_contacts(text: str, html: str, host: str) -> tuple[list[str], list[str]]:
    blob = (text or "") + "\n" + (html or "")
    emails = []
    seen = set()
    for m in EMAIL_RE.finditer(blob):
        e = m.group(0).lower().rstrip(".,;:")
        if not _valid_email(e):
            continue
        prefix = e.split("@", 1)[0]
        if prefix in GENERIC_EMAIL_PREFIX:
            continue
        if e in seen:
            continue
        seen.add(e)
        emails.append(e)
    if host:
        host_root = host.split(".")[0]
        same_dom = [e for e in emails if host_root in e.split("@", 1)[1]]
        others = [e for e in emails if e not in same_dom]
        emails = (same_dom + others)[:5]

    phones = []
    pseen = set()
    for m in PHONE_RE.finditer(text or ""):
        p = re.sub(r"\s+", " ", m.group(0)).strip()
        digits = re.sub(r"\D", "", p)
        if len(digits) < 9 or len(digits) > 15:
            continue
        if p in pseen:
            continue
        pseen.add(p)
        phones.append(p)
    return emails, phones[:3]


MAX_LIMIT = 25
MAX_ROUNDS = 5
SCORE_THRESHOLD = 30


async def run_search(
    domain: str,
    country: str,
    min_emp: int,
    max_emp: int,
    limit: int,
    notes: str = "",
    log_cb=None,
) -> AsyncIterator[dict]:

    async def log(msg: str):
        if log_cb:
            await log_cb(msg)

    target = max(1, min(limit, MAX_LIMIT))
    yielded = 0
    seen_hosts: set[str] = set()
    used_queries: list[str] = []

    sem = asyncio.Semaphore(5)

    async def _score(c):
        host = _root_domain(c["url"])
        try:
            s = await score_lead(_clean_company_name(c["title"], host),
                                 c["url"], c["snippet"], domain, country, notes=notes)
        except Exception:
            s = {"score": 0.0, "reason": ""}
        c["score"] = s["score"]
        c["reason"] = s["reason"]
        return c

    async def _bounded(c):
        async with sem:
            return await _score(c)

    async with AsyncStealthySession(headless=True, block_images=True) as site_session:
        for round_num in range(1, MAX_ROUNDS + 1):
            if yielded >= target:
                break
            need = target - yielded
            await log(f"── round {round_num}/{MAX_ROUNDS} · need {need} more lead(s) ──")

            try:
                queries = await expand_queries(
                    domain, country, min_emp, max_emp,
                    limit=10 if round_num == 1 else 8,
                    previous=used_queries or None,
                )
            except Exception as e:
                await log(f"LLM expand failed: {e}")
                queries = [f"{domain} companies {country}".strip()]

            new_queries = [q for q in queries if q not in used_queries]
            if not new_queries:
                await log("No fresh queries returned — stopping retries.")
                break
            used_queries.extend(new_queries)
            await log(f"Got {len(new_queries)} new queries")

            candidates: list[dict] = []
            for q in new_queries:
                await log(f"SERP: {q}")
                try:
                    results = await asyncio.to_thread(_serp_run, q)
                except Exception as e:
                    await log(f"  SERP error: {e}")
                    results = []
                for r in results:
                    host = _root_domain(r["url"])
                    if not host or host in seen_hosts or _is_skippable(r["url"]):
                        continue
                    seen_hosts.add(host)
                    candidates.append(r)
                await asyncio.sleep(0.6)

            if not candidates:
                await log("No new domains this round.")
                continue

            await log(f"{len(candidates)} new unique domains. Scoring with Groq...")
            scored = await asyncio.gather(*(_bounded(c) for c in candidates))
            scored = [c for c in scored if c["score"] >= SCORE_THRESHOLD]
            scored.sort(key=lambda x: x["score"], reverse=True)
            await log(f"{len(scored)} passed score threshold (>={SCORE_THRESHOLD})")

            for c in scored:
                if yielded >= target:
                    break
                host = _root_domain(c["url"])
                company = _clean_company_name(c["title"], host)
                await log(f"Extracting [{c['score']:.0f}]: {company} ({host})")

                text, html = "", ""
                try:
                    text, html = await _fetch_site_text(site_session, f"https://{host}")
                except Exception as e:
                    await log(f"  fetch failed: {e}")

                emails, phones = _regex_contacts(text, html, host)

                llm_data = {"emails": [], "phones": [], "contact_person": "",
                            "contact_title": "", "employee_count": "", "description": ""}
                if text:
                    try:
                        llm_data = await extract_contacts(company, text)
                    except Exception:
                        pass

                merged_emails = list(dict.fromkeys(emails + llm_data["emails"]))[:3]
                merged_phones = list(dict.fromkeys(phones + llm_data["phones"]))[:2]

                lead = {
                    "company": company,
                    "website": f"https://{host}",
                    "email": merged_emails[0] if merged_emails else "",
                    "phone": merged_phones[0] if merged_phones else "",
                    "contact_person": llm_data["contact_person"],
                    "contact_title": llm_data["contact_title"],
                    "employee_count": llm_data["employee_count"],
                    "country": country,
                    "description": (llm_data["description"] if len(llm_data["description"]) > 25
                                    else c["snippet"][:300]),
                    "relevance_score": c["score"],
                    "relevance_reason": c["reason"],
                    "source_url": c["url"],
                }
                yielded += 1
                yield lead
                await asyncio.sleep(0.4)

    if yielded < target:
        await log(
            f"⚠ Max threshold reached: only {yielded}/{target} high-quality leads after "
            f"{MAX_ROUNDS} rounds. Try broader notes, looser headcount, or different domain."
        )
    else:
        await log(f"✓ Done. {yielded} leads yielded.")
