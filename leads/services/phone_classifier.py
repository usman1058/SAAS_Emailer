"""
Phone Number Classifier Service

Uses libphonenumber to classify phone numbers as mobile or landline
and generate WhatsApp wa.me links.
"""
import logging
from typing import Optional

import phonenumbers
from phonenumbers import PhoneNumberType, NumberParseException

logger = logging.getLogger(__name__)


def classify_phone(raw_phone: str, region: Optional[str] = None) -> dict:
    """
    Classify a phone number and generate WhatsApp info.

    Args:
        raw_phone: Raw phone number string
        region: ISO country code (e.g., 'DE', 'GB', 'US') for parsing

    Returns:
        dict with keys: whatsapp_status, whatsapp_check_link, formatted_number
    """
    if not raw_phone:
        return {
            "whatsapp_status": "No phone listed",
            "whatsapp_check_link": "",
            "formatted_number": "",
        }

    try:
        parsed = phonenumbers.parse(raw_phone, region or None)
    except NumberParseException:
        return {
            "whatsapp_status": "Unrecognized format",
            "whatsapp_check_link": "",
            "formatted_number": raw_phone,
        }

    if not phonenumbers.is_valid_number(parsed):
        return {
            "whatsapp_status": "Unrecognized format",
            "whatsapp_check_link": "",
            "formatted_number": raw_phone,
        }

    formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    num_type = phonenumbers.number_type(parsed)

    if num_type in (PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE):
        wa_link = f"https://wa.me/{e164.lstrip('+')}"
        return {
            "whatsapp_status": "Mobile — check via wa.me link",
            "whatsapp_check_link": wa_link,
            "formatted_number": formatted,
        }
    else:
        return {
            "whatsapp_status": "Landline — WhatsApp unlikely",
            "whatsapp_check_link": "",
            "formatted_number": formatted,
        }


def get_region_for_country(country: str) -> Optional[str]:
    """Get ISO region code for a country name."""
    if not country:
        return None
    return COUNTRY_TO_REGION.get(country.strip().lower())


# Re-export the mapping for convenience
COUNTRY_TO_REGION = {
    "germany": "DE", "deutschland": "DE", "de": "DE",
    "uk": "GB", "united kingdom": "GB", "england": "GB",
    "scotland": "GB", "wales": "GB", "northern ireland": "GB", "gb": "GB",
    "australia": "AU", "au": "AU",
    "usa": "US", "united states": "US", "us": "US",
    "canada": "CA", "ca": "CA",
    "france": "FR", "fr": "FR",
    "spain": "ES", "es": "ES",
    "italy": "IT", "it": "IT",
    "netherlands": "NL", "nl": "NL",
    "belgium": "BE", "be": "BE",
    "switzerland": "CH", "ch": "CH",
    "austria": "AT", "at": "AT",
    "poland": "PL", "pl": "PL",
    "sweden": "SE", "se": "SE",
    "norway": "NO", "no": "NO",
    "denmark": "DK", "dk": "DK",
    "finland": "FI", "fi": "FI",
    "ireland": "IE", "ie": "IE",
    "portugal": "PT", "pt": "PT",
    "greece": "GR", "gr": "GR",
    "japan": "JP", "jp": "JP",
    "singapore": "SG", "sg": "SG",
    "hong kong": "HK", "hk": "HK",
    "new zealand": "NZ", "nz": "NZ",
}