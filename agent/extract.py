"""Deciding what counts as a delivery code, and what must never reach the screen.

Kept separate from the watcher because this is the part with opinions in
it, and opinions want tests. The watcher does I/O; this module is pure.

The first version of this was one line:

    re.compile(r"\\b(\\d{4,8})\\b").search(text)

which returns the first four-to-eight digit run anywhere in the message.
"Your Amazon order 1140377 is arriving today" put the order number on the
display. Worse, with no sender filter it also put bank one-time passwords
on a screen mounted by the front door, where the person the code is
protecting you from is standing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Words that appear next to a code someone is meant to read aloud.
_CODE_CUE = r"(?:otp|code|pin|password|passcode|verification|verify)"

# A code with a cue word before it: "OTP is 4821", "code: 4821".
_CUE_THEN_DIGITS = re.compile(
    rf"\b{_CODE_CUE}[^0-9]{{0,32}}?(\d{{4,8}})\b",
    re.IGNORECASE,
)

# A code with the cue word after it: "4821 is your OTP".
_DIGITS_THEN_CUE = re.compile(
    rf"\b(\d{{4,8}})\b[^0-9]{{0,32}}?\b{_CODE_CUE}",
    re.IGNORECASE,
)

# Things that look like codes but are not.
_NOT_A_CODE = re.compile(
    r"\b(?:order|invoice|ref(?:erence)?|tracking|awb|ticket|inr|rs\.?|"
    r"amount|bill|acc(?:ount)?|card|txn|transaction)\b[^0-9]{0,12}\d{4,}",
    re.IGNORECASE,
)

# Senders whose codes must never be displayed, however they are worded.
# This is a deny-list of *categories*, matched against sender and body,
# because the sender id for a bank SMS is rarely the bank's name.
_NEVER_DISPLAY = re.compile(
    r"\b(?:bank|hdfc|icici|axis|sbi|kotak|paytm|phonepe|gpay|"
    r"upi|netbanking|debit|credit|atm|"
    r"aadhaar|pan\b|income.?tax|"
    r"whatsapp|telegram|signal|google|apple|microsoft|facebook|instagram|"
    r"two.?factor|2fa|login|sign.?in|authenticat)",
    re.IGNORECASE,
)

DELIVERY_BRANDS = {
    "swiggy": "Swiggy",
    "zomato": "Zomato",
    "dunzo": "Dunzo",
    "blinkit": "Blinkit",
    "zepto": "Zepto",
    "amazon": "Amazon",
    "flipkart": "Flipkart",
    "delhivery": "Delhivery",
    "bluedart": "BlueDart",
    "dtdc": "DTDC",
    "ecom": "ECom Express",
    "ekart": "Ekart",
    "shadowfax": "Shadowfax",
    "porter": "Porter",
    "rapido": "Rapido",
    "uber": "Uber",
    "ola": "Ola",
}


@dataclass(frozen=True)
class Extraction:
    code: str | None
    label: str
    reason: str
    """Why this decision was made -- logged, so a miss can be diagnosed."""

    @property
    def displayable(self) -> bool:
        return self.code is not None


def extract(text: str, handle: str = "", *, delivery_only: bool = True) -> Extraction:
    """Decide whether a message carries a code that belongs on the display.

    `delivery_only` is the safe default: only codes from recognised
    delivery senders are shown. Turning it off widens the net to any
    message with a code cue, and the financial and account deny-list
    still applies -- that one is not optional.
    """
    if not text:
        return Extraction(None, "", "empty message")

    haystack = f"{text} {handle}"

    if _NEVER_DISPLAY.search(haystack):
        # Deliberately does not log the code, or the matched term. A door
        # display's log is not a place to accumulate banking messages.
        return Extraction(None, "", "sender or body is in the never-display set")

    brand = _brand(haystack)
    if delivery_only and brand is None:
        return Extraction(None, "", "not a recognised delivery sender")

    code = _find_code(text)
    if code is None:
        return Extraction(None, brand or "", "no code cue found near any digits")

    return Extraction(code, brand or _fallback_label(handle), "ok")


def _find_code(text: str) -> str | None:
    """Pull the code, requiring a cue word rather than trusting any digit run."""
    for pattern in (_CUE_THEN_DIGITS, _DIGITS_THEN_CUE):
        for match in pattern.finditer(text):
            candidate = match.group(1)
            if _is_decoy(text, match.start(1)):
                continue
            return candidate
    return None


def _is_decoy(text: str, at: int) -> bool:
    """True if the digits at this offset are an order or amount, not a code."""
    window = text[max(0, at - 40) : at + 10]
    return bool(_NOT_A_CODE.search(window))


def _brand(haystack: str) -> str | None:
    lowered = haystack.lower()
    for key, label in DELIVERY_BRANDS.items():
        if key in lowered:
            return label
    return None


def _fallback_label(handle: str) -> str:
    return handle.strip() or "Delivery"
