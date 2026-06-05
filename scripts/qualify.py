"""Phase 1 — the qualify gate.

Deterministic, no LLM, no research: a signup whose email is on a free/consumer
mailbox or a common/shared domain (.edu et al.) is an automatic out, as is one
whose "company" is really just the person's own name. Only a company-specific
domain passes. (Hook left for richer qualification later.)
"""
from __future__ import annotations

from scripts.company_blocklist import BLOCKED_COMPANY_NAMES, normalize_company

# Free/consumer mailbox providers — automatic out.
FREE_MAILBOX_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "ymail.com",
    "hotmail.com", "hotmail.co.uk", "outlook.com", "live.com", "msn.com",
    "icloud.com", "me.com", "mac.com", "aol.com", "proton.me", "protonmail.com",
    "gmx.com", "gmx.de", "mail.com", "zoho.com", "yandex.com", "pm.me",
    "fastmail.com", "hey.com", "qq.com", "163.com", "126.com",
}

# Common/shared top-level suffixes — not "trash" but not a company domain
# (e.g. .edu is every university / every student). Automatic out.
COMMON_DOMAIN_SUFFIXES = (
    ".edu", ".edu.au", ".edu.in", ".ac.uk", ".ac.in", ".edu.cn",
    ".k12.us", ".sch.uk", ".gov", ".mil",
)


def domain_of(email: str) -> str:
    return email.split("@", 1)[1].strip().lower() if "@" in email else ""


def _norm(name: str) -> str:
    """Lowercase and collapse whitespace for name comparison."""
    return " ".join((name or "").lower().split())


def _name_is_person(company_name: str, recipient_name: str) -> bool:
    """True when the company name is really just the person's name.

    A signup where the "company" equals the person's full name, or their first
    or last name alone, is an individual, not a company — an automatic out.
    """
    org = _norm(company_name)
    person = _norm(recipient_name)
    if not org or not person:
        return False
    if org == person:
        return True
    parts = person.split(" ")
    return org == parts[0] or org == parts[-1]


def qualify(email: str, company_name: str = "", recipient_name: str = "") -> tuple[bool, str]:
    """Return (passes, reason). reason is the skip reason when it fails."""
    domain = domain_of(email)
    if not domain:
        return False, "no email domain"
    if domain in FREE_MAILBOX_DOMAINS:
        return False, f"free mailbox ({domain})"
    if domain.endswith(COMMON_DOMAIN_SUFFIXES):
        return False, f"common/shared domain ({domain})"
    if _name_is_person(company_name, recipient_name):
        return False, f"company name is the person's name ({company_name})"
    if normalize_company(company_name) in BLOCKED_COMPANY_NAMES:
        return False, f"blocklisted company name ({company_name})"
    return True, ""
