"""How-to-cancel guides for common merchants.

Kept as an in-code registry (rather than a seeded DB table) because the data is
static and small; this avoids a seed migration. Expand over time, ideally driven
by the merchants your users actually have.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.detection import normalize_merchant


@dataclass
class CancelGuide:
    merchant_key: str
    name: str
    url: str
    difficulty: str  # 'easy' | 'medium' | 'hard'
    steps: list[str]
    known: bool = True


# Map normalized variants onto a canonical key.
_ALIASES = {
    "googleone": "google",
    "youtube": "google",
    "primevideo": "amazon",
    "amazonprime": "amazon",
    "prime": "amazon",
    "hotstar": "disney",
    "jiohotstar": "disney",
    "disneyplus": "disney",
    "chatgpt": "openai",
    "itunes": "apple",
    "icloud": "apple",
}

_GUIDES: dict[str, CancelGuide] = {
    "netflix": CancelGuide(
        "netflix", "Netflix", "https://www.netflix.com/cancelplan", "easy",
        [
            "Sign in to netflix.com from a browser.",
            "Open Account from the profile menu.",
            "Under Membership, click Cancel Membership.",
            "Confirm. You keep access until the end of the billing period.",
        ],
    ),
    "spotify": CancelGuide(
        "spotify", "Spotify", "https://www.spotify.com/account/subscription/", "easy",
        [
            "Go to your account page on spotify.com.",
            "Under Your plan, select Change plan.",
            "Scroll to Cancel Spotify and click Cancel Premium.",
            "Confirm. Premium stays active until the next billing date.",
        ],
    ),
    "google": CancelGuide(
        "google", "Google (One / YouTube)", "https://play.google.com/store/account/subscriptions", "easy",
        [
            "Open play.google.com/store/account/subscriptions (or Google One settings).",
            "Select the subscription you want to cancel.",
            "Click Cancel subscription and follow the prompts.",
        ],
    ),
    "amazon": CancelGuide(
        "amazon", "Amazon Prime", "https://www.amazon.in/gp/primecentral", "medium",
        [
            "Go to Amazon Account > Prime Membership.",
            "Select Manage Membership > End Membership.",
            "Confirm; Amazon may offer to remind you before renewal instead.",
        ],
    ),
    "disney": CancelGuide(
        "disney", "Disney+ Hotstar", "https://www.hotstar.com/subscribe/my-account", "medium",
        [
            "Open My Account on Hotstar (web).",
            "Select your plan and choose Cancel Subscription.",
            "If billed via an app store or telecom partner, cancel there instead.",
        ],
    ),
    "adobe": CancelGuide(
        "adobe", "Adobe", "https://account.adobe.com/plans", "hard",
        [
            "Sign in at account.adobe.com and open Plans.",
            "Click Manage plan > Cancel your plan.",
            "Note: cancelling an annual plan early may incur an early-termination fee.",
        ],
    ),
    "notion": CancelGuide(
        "notion", "Notion", "https://www.notion.so/my-account", "easy",
        [
            "Open Settings & members > Plans in Notion.",
            "Choose Change plan and downgrade to Free.",
        ],
    ),
    "openai": CancelGuide(
        "openai", "OpenAI / ChatGPT", "https://chat.openai.com/#settings", "easy",
        [
            "Open ChatGPT > Settings > Subscription (Manage).",
            "Click Cancel plan. Access continues until the period ends.",
        ],
    ),
    "apple": CancelGuide(
        "apple", "Apple (iCloud / App Store)", "https://apps.apple.com/account/subscriptions", "medium",
        [
            "On iPhone: Settings > your name > Subscriptions.",
            "On Mac: App Store > your name > Account Settings.",
            "Select the subscription and choose Cancel Subscription.",
        ],
    ),
    "linkedin": CancelGuide(
        "linkedin", "LinkedIn Premium", "https://www.linkedin.com/premium/manage/", "medium",
        [
            "Click your photo > Access My Premium.",
            "Under Manage Premium account, select Cancel subscription.",
            "Follow the prompts to confirm.",
        ],
    ),
    "github": CancelGuide(
        "github", "GitHub", "https://github.com/settings/billing", "easy",
        [
            "Go to Settings > Billing and plans.",
            "Downgrade your plan to Free or cancel the paid feature.",
        ],
    ),
}

_GENERIC_STEPS = [
    "Open the service's website or app and sign in.",
    "Find Account, Settings, or Billing / Subscription.",
    "Look for Cancel, Manage plan, or Downgrade.",
    "If you were billed through Google Play, the App Store, or a telecom "
    "partner, cancel from there instead.",
]


def lookup(merchant: str) -> CancelGuide:
    """Resolve a merchant name/key to a cancel guide, falling back to generic
    steps (known=False) when the merchant is not in the registry."""
    key = normalize_merchant(merchant)
    key = _ALIASES.get(key, key)
    guide = _GUIDES.get(key)
    if guide is not None:
        return guide
    return CancelGuide(
        merchant_key=key,
        name=merchant,
        url="",
        difficulty="medium",
        steps=list(_GENERIC_STEPS),
        known=False,
    )
