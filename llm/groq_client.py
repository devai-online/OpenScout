import json
import re
from typing import Optional

from groq import Groq, AsyncGroq
from config import GROQ_API_KEY, GROQ_MODEL


_client: Optional[AsyncGroq] = None


def client() -> AsyncGroq:
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY missing in .env")
        _client = AsyncGroq(api_key=GROQ_API_KEY)
    return _client


def _extract_json(text: str):
    """Pull first JSON object/array from a possibly-noisy LLM response."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    for opener, closer in [("[", "]"), ("{", "}")]:
        i = text.find(opener)
        if i == -1:
            continue
        depth = 0
        for j in range(i, len(text)):
            if text[j] == opener:
                depth += 1
            elif text[j] == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[i:j + 1])
                    except json.JSONDecodeError:
                        break
    return None


async def _chat(system: str, user: str, temperature: float = 0.2, max_tokens: int = 1024) -> str:
    resp = await client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


async def expand_queries(domain: str, country: str, min_emp: int, max_emp: int,
                         limit: int = 8, previous: list[str] | None = None) -> list[str]:
    """Generate search engine queries. Avoids duplicates when `previous` supplied."""
    size_hint = ""
    if min_emp or max_emp:
        size_hint = f" Headcount target: {min_emp or 1}-{max_emp or 500} employees."
    avoid = ""
    temp = 0.4
    if previous:
        avoid = "\n\nAvoid these previously used queries (use different angles, sub-niches, cities, modifiers):\n- " + "\n- ".join(previous[-30:])
        temp = 0.7
    system = (
        "You are a B2B lead-gen query writer. Output JSON array of search engine queries "
        "that will surface real operating company websites (not directories, not blogs). "
        "Mix industry terms, locations, sub-niches, and headcount qualifiers. "
        "Avoid generic words like 'best' or 'top'."
    )
    user = (
        f"Domain/industry: {domain}\n"
        f"Country: {country or 'any'}\n"
        f"{size_hint}{avoid}\n"
        f"Return {limit} diverse queries as a JSON array of strings. JSON only."
    )
    raw = await _chat(system, user, temperature=temp, max_tokens=900)
    parsed = _extract_json(raw)
    if isinstance(parsed, list):
        return [str(q).strip() for q in parsed if str(q).strip()][:limit]
    return [f"{domain} companies {country}".strip()]


async def score_lead(company: str, website: str, snippet: str, domain: str, country: str,
                     notes: str = "") -> dict:
    """Return relevance score 0-100 + short reason. Buyer-intent framing."""
    system = (
        "You score B2B sales leads. The user runs a vendor business and is looking for "
        "POTENTIAL CUSTOMERS — companies that would BUY the user's offering. "
        "DO NOT score competitors (other vendors selling the same thing) highly. "
        "DO NOT score blog posts, articles, listicles, directories, marketplaces, or news. "
        "DO score real operating businesses in the target industry/country whose own "
        "operations would benefit from the user's offering. "
        "Return JSON: {\"score\": 0-100, \"reason\": \"<=100 chars\"}. "
        "Scoring rubric: "
        "90-100 = clear buyer-fit operating business with own website; "
        "60-80 = plausible buyer but uncertain; "
        "30-50 = adjacent or unclear; "
        "0-20 = competitor/blog/directory/news/listicle/irrelevant."
    )
    extras = f"User notes: {notes}\n" if notes else ""
    user = (
        f"User offering / target industry: {domain}\n"
        f"Target country: {country or 'any'}\n{extras}\n"
        f"Candidate company: {company}\nCandidate URL: {website}\n"
        f"Search snippet: {snippet[:500]}\n\n"
        "Is this candidate a likely BUYER of the user's offering, or is it a competitor / "
        "content page / directory? Score accordingly."
    )
    raw = await _chat(system, user, temperature=0.1, max_tokens=200)
    parsed = _extract_json(raw)
    if isinstance(parsed, dict) and "score" in parsed:
        try:
            score = float(parsed["score"])
        except (TypeError, ValueError):
            score = 0.0
        return {"score": max(0.0, min(100.0, score)), "reason": str(parsed.get("reason", ""))[:500]}
    return {"score": 0.0, "reason": ""}


async def extract_contacts(company: str, page_text: str) -> dict:
    """Pull contact info + headcount hints from a company page text dump."""
    system = (
        "Extract structured contact info from a company webpage. "
        "Return JSON: {\"emails\": [str], \"phones\": [str], "
        "\"contact_person\": str, \"contact_title\": str, "
        "\"employee_count\": str, \"description\": str}. "
        "Empty string if unknown. Description = 1 sentence about what the company does."
    )
    user = f"Company: {company}\n\nPage content (truncated):\n{page_text[:6000]}"
    raw = await _chat(system, user, temperature=0.0, max_tokens=500)
    parsed = _extract_json(raw)
    if isinstance(parsed, dict):
        return {
            "emails": [e for e in parsed.get("emails", []) if isinstance(e, str)],
            "phones": [p for p in parsed.get("phones", []) if isinstance(p, str)],
            "contact_person": str(parsed.get("contact_person", "") or ""),
            "contact_title": str(parsed.get("contact_title", "") or ""),
            "employee_count": str(parsed.get("employee_count", "") or ""),
            "description": str(parsed.get("description", "") or "")[:500],
        }
    return {"emails": [], "phones": [], "contact_person": "", "contact_title": "",
            "employee_count": "", "description": ""}
