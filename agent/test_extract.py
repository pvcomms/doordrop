"""Tests for the part that decides what a stranger at the door gets to read.

The messages below are paraphrases of the shapes Indian delivery and
banking SMS actually take. No real codes, senders, or account details.
"""

from __future__ import annotations

import pytest

from extract import extract


# --- the codes we want ---------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("Your Swiggy delivery OTP is 4821. Share with the delivery partner.", "4821"),
        ("Zomato: use code 7391 to collect your order.", "7391"),
        ("Blinkit verification code: 552104", "552104"),
        ("8823 is your Zepto delivery PIN", "8823"),
        ("Amazon: OTP 9017 for your shipment", "9017"),
        ("Delhivery - your parcel PIN is 3345.", "3345"),
    ],
)
def test_extracts_delivery_codes(text, expected):
    result = extract(text, "TX-SWIGGY")
    assert result.code == expected
    assert result.displayable


def test_labels_the_brand():
    assert extract("Your Swiggy OTP is 4821", "TX-SWGY").label == "Swiggy"
    assert extract("Zomato code 1234", "VM-ZOMATO").label == "Zomato"


# --- the bug that started this ------------------------------------------

def test_does_not_mistake_an_order_number_for_a_code():
    # The original regex took the first 4-8 digit run and put 1140377 on
    # the display. There is no code in this message at all.
    r = extract("Your Amazon order 1140377 is arriving today", "AMAZON")
    assert r.code is None
    assert "no code cue" in r.reason


def test_prefers_the_code_over_an_order_number_in_the_same_message():
    r = extract(
        "Amazon order 1140377 out for delivery. Share OTP 6642 with the agent.",
        "AMAZON",
    )
    assert r.code == "6642"


def test_ignores_amounts():
    r = extract("Swiggy: your order of Rs 1450 is on the way", "SWIGGY")
    assert r.code is None


def test_ignores_tracking_numbers():
    r = extract("BlueDart tracking 78451236 dispatched", "BLUEDART")
    assert r.code is None


# --- the codes that must never reach a door-facing screen ----------------

@pytest.mark.parametrize(
    "text,handle",
    [
        ("Your bank OTP is 4821. Do not share with anyone.", "HDFCBK"),
        ("OTP 5567 for your UPI transaction", "ICICIB"),
        ("112233 is your WhatsApp code", "WHATSAPP"),
        ("Your Google verification code is 447291", "GOOGLE"),
        ("Use 9981 to sign in to your account", "MSFT"),
        ("Your debit card OTP is 3321", "VM-AXISBK"),
        ("Aadhaar OTP 778812", "UIDAI"),
    ],
)
def test_never_displays_financial_or_account_codes(text, handle):
    # These are exactly the messages the first version would have shown,
    # to whoever was standing at the door.
    r = extract(text, handle, delivery_only=False)
    assert r.code is None
    assert "never-display" in r.reason


def test_the_deny_list_is_not_optional():
    # delivery_only=False widens what counts as a sender. It must not
    # widen the financial deny-list.
    r = extract("Your bank OTP is 4821", "HDFCBK", delivery_only=False)
    assert r.code is None


def test_deny_list_wins_even_when_the_sender_looks_like_delivery():
    r = extract("Amazon Pay UPI OTP 4821", "AMAZON")
    assert r.code is None


def test_reason_does_not_leak_the_code_it_refused():
    r = extract("Your bank OTP is 481922", "HDFCBK")
    assert "481922" not in r.reason


# --- sender filtering ----------------------------------------------------

def test_delivery_only_rejects_unknown_senders_by_default():
    r = extract("Your OTP is 4821", "+919876500000")
    assert r.code is None
    assert "not a recognised delivery sender" in r.reason


def test_widening_accepts_an_unknown_sender_with_a_cue():
    r = extract("Your OTP is 4821", "+919876500000", delivery_only=False)
    assert r.code == "4821"
    assert r.label == "+919876500000"


# --- edges ---------------------------------------------------------------

@pytest.mark.parametrize("text", ["", "   ", "no digits here at all"])
def test_handles_messages_with_nothing_in_them(text):
    assert extract(text, "SWIGGY").code is None


def test_rejects_codes_that_are_too_short_or_too_long():
    assert extract("Swiggy OTP is 123", "SWIGGY").code is None
    assert extract("Swiggy OTP is 1234567890", "SWIGGY").code is None


def test_is_case_insensitive():
    assert extract("SWIGGY OTP IS 4821", "SWIGGY").code == "4821"
    assert extract("swiggy otp is 4821", "swiggy").code == "4821"


def test_handles_punctuation_between_cue_and_code():
    for sep in (": ", " - ", " = ", ". ", " is ", ""):
        assert extract(f"Swiggy code{sep}4821", "SWIGGY").code == "4821"


def test_never_returns_a_displayable_extraction_without_a_code():
    for text in ("Your bank OTP is 4821", "Amazon order 1140377", ""):
        r = extract(text, "X")
        assert r.displayable == (r.code is not None)
