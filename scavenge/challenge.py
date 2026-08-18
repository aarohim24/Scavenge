"""Detect that a rendered page is a block or challenge rather than the target.

Detection only. Nothing here bypasses, solves or evades anything — it exists so the engine
says "I was shown a challenge" instead of silently treating an interstitial as the page.

Deliberately high precision: a named marker must appear. Page size, response codes and
"the page looked odd" are not sufficient on their own, because a false positive would
discard real evidence, which is worse than missing a block.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

# Vendor tokens. These live in markup and script source, so the whole document is scanned.
_TOKENS: tuple[tuple[str, str], ...] = (
    ("cf-browser-verification", "Cloudflare browser verification"),
    ("cf_chl_opt", "Cloudflare challenge script"),
    ("__cf_chl_", "Cloudflare challenge token"),
    ("_incapsula_resource", "Imperva/Incapsula resource"),
    ("px-captcha", "PerimeterX captcha"),
    ("_pxhd", "PerimeterX challenge cookie"),
    ("datadome", "DataDome"),
)
# Interstitial wording. Matched in **visible text only**: a page whose script happens to
# contain the string "just a moment" is not a challenge, and scanning script source for
# human phrases cost precision the moment it was tried.
_PHRASES: tuple[tuple[str, str], ...] = (
    ("just a moment", "'Just a moment...' interstitial"),
    ("checking your browser before", "'Checking your browser' interstitial"),
    ("attention required! | cloudflare", "Cloudflare 'Attention Required'"),
    ("pardon our interruption", "Distil/Imperva 'Pardon Our Interruption'"),
    ("verify you are human", "human-verification prompt"),
    ("enable javascript and cookies to continue", "JS/cookies challenge prompt"),
    ("access denied", "explicit access denial"),
    ("robot or human?", "bot-check prompt"),
    ("are you a human", "'Are you a human?' bot check"),
    ("please verify you are a human", "human-verification prompt"),
    ("request unsuccessful. incapsula", "Imperva 'Request unsuccessful'"),
)
_CAPTCHA = re.compile(r"\bg-recaptcha\b|\bh-captcha\b|recaptcha/api\.js|hcaptcha\.com", re.I)


def detect(html: str) -> str | None:
    """The signal that identifies this page as a challenge, or None.

    Returns the reason so a report can say *why* — an unexplained classification is not
    evidence.
    """
    if not html:
        return None
    lowered = html.lower()
    for token, reason in _TOKENS:
        if token in lowered:
            return f"{reason} (matched {token!r})"
    tree = HTMLParser(html)
    for tag in ("script", "style", "noscript"):
        for node in tree.css(tag):
            node.decompose()
    visible = " ".join(tree.text().lower().split())
    for phrase, reason in _PHRASES:
        if phrase in visible:
            return f"{reason} (matched {phrase!r})"
    if _CAPTCHA.search(html) and _is_thin(html):
        return "captcha widget on a page with almost no other content"
    return None


def _is_thin(html: str) -> bool:
    """A captcha alone is not a block — checkout pages carry them. A captcha on a page with
    essentially no text is."""
    max_text = 400
    return len(HTMLParser(html).text().strip()) < max_text
