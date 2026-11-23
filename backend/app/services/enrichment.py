"""Merchant enrichment: turn a messy merchant key/name into a clean display
name, category, and logo.

Strategy: known lookup table first, then (optionally) an LLM, then a rule-based
fallback. Results are cached in-process so the LLM is called at most once per
unique merchant. The product works fully without an LLM key.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings

# Seed table of common merchants (expand over time / via corrections in Phase 2).
_KNOWN: dict[str, tuple[str, str]] = {
    "netflix": ("Netflix", "Entertainment"),
    "spotify": ("Spotify", "Music"),
    "youtube": ("YouTube Premium", "Entertainment"),
    "google": ("Google", "Software"),
    "googleone": ("Google One", "Cloud Storage"),
    "amazonprime": ("Amazon Prime", "Shopping"),
    "amazon": ("Amazon", "Shopping"),
    "primevideo": ("Prime Video", "Entertainment"),
    "hotstar": ("Disney+ Hotstar", "Entertainment"),
    "jiohotstar": ("JioHotstar", "Entertainment"),
    "adobe": ("Adobe", "Software"),
    "notion": ("Notion", "Productivity"),
    "chatgpt": ("ChatGPT", "Software"),
    "openai": ("OpenAI", "Software"),
    "icloud": ("iCloud", "Cloud Storage"),
    "apple": ("Apple", "Software"),
    "swiggy": ("Swiggy One", "Food"),
    "zomato": ("Zomato", "Food"),
    "linkedin": ("LinkedIn Premium", "Productivity"),
    "github": ("GitHub", "Software"),
}

_cache: dict[str, "Enrichment"] = {}


@dataclass
class Enrichment:
    merchant_name: str
    category: str | None
    logo_url: str | None


def _logo_for(name: str) -> str:
    """Derive a logo URL using a public favicon service as a cheap default."""
    slug = name.lower().replace(" ", "").replace("+", "")
    return f"https://logo.clearbit.com/{slug}.com"


def _rule_based(merchant_key: str, raw_merchant: str) -> Enrichment:
    name = raw_merchant.strip().title() if raw_merchant else merchant_key.title()
    return Enrichment(merchant_name=name, category=None, logo_url=_logo_for(name))


_ENRICH_SYSTEM = (
    "You normalize payment merchant strings. Given a raw merchant string, return "
    "JSON with keys name (clean brand name) and category (one of: Entertainment, "
    "Music, Software, Productivity, Cloud Storage, Shopping, Food, Fitness, News, "
    "Other)."
)


def _llm_enrich(raw_merchant: str) -> Enrichment | None:
    """Ask the LLM to normalize a merchant string. Returns None on any failure."""
    if not settings.openai_api_key:
        return None
    try:
        from app.services import llm

        data = llm.chat_json(
            _ENRICH_SYSTEM, f'Merchant string: "{raw_merchant}". Return only JSON.'
        )
        name = data.get("name") or raw_merchant.title()
        return Enrichment(
            merchant_name=name,
            category=data.get("category"),
            logo_url=_logo_for(name),
        )
    except Exception:
        return None


def enrich(merchant_key: str, raw_merchant: str) -> Enrichment:
    if merchant_key in _cache:
        return _cache[merchant_key]

    if merchant_key in _KNOWN:
        name, category = _KNOWN[merchant_key]
        result = Enrichment(merchant_name=name, category=category, logo_url=_logo_for(name))
    else:
        result = _llm_enrich(raw_merchant) or _rule_based(merchant_key, raw_merchant)

    _cache[merchant_key] = result
    return result
