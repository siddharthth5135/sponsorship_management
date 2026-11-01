from app.services.bounces import _extract_failed_addresses, _extract_reason


SAMPLE = """
Address not found
Your message wasn't delivered to info@waytocode.com because the domain waytocode.com couldn't be found.
Check for typos or unnecessary spaces and try again.
"""


def test_extract_failed_address_from_gmail_bounce():
    assert _extract_failed_addresses(SAMPLE) == ["info@waytocode.com"]


def test_extract_reason():
    reason = _extract_reason(SAMPLE)
    assert "Address not found" in reason or "couldn't be found" in reason.lower()
