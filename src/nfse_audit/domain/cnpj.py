"""CNPJ check digit algorithm, supporting both numeric and alphanumeric CNPJs.

Since July 2026 (IN RFB 2.229/2024) the first 12 positions of a CNPJ may contain
letters A-Z. The check digit algorithm is the same modulo-11 for both formats:
each character is worth its ASCII code minus 48 ("0" -> 0, "A" -> 17).
"""

import re

_WEIGHTS_DV1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_WEIGHTS_DV2 = (6, *_WEIGHTS_DV1)

_BASE_PATTERN = re.compile(r"^[0-9A-Z]{12}$")
_CNPJ_PATTERN = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")
_FORMATTING_CHARS = re.compile(r"[./\-\s]")


def _check_digit(chars: str, weights: tuple[int, ...]) -> int:
    total = sum((ord(char) - 48) * weight for char, weight in zip(chars, weights, strict=True))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def compute_check_digits(base: str) -> str:
    """Return the two check digits for a 12-character CNPJ base."""
    if not _BASE_PATTERN.match(base):
        raise ValueError(f"CNPJ base must be 12 characters [0-9A-Z], got {base!r}")
    dv1 = _check_digit(base, _WEIGHTS_DV1)
    dv2 = _check_digit(base + str(dv1), _WEIGHTS_DV2)
    return f"{dv1}{dv2}"


def normalize_cnpj(value: str) -> str:
    """Strip formatting, uppercase and validate. Returns the 14-character CNPJ."""
    cnpj = _FORMATTING_CHARS.sub("", value).upper()
    if not _CNPJ_PATTERN.match(cnpj):
        raise ValueError(f"CNPJ must have 12 characters [0-9A-Z] plus 2 check digits: {value!r}")
    if len(set(cnpj)) == 1:
        raise ValueError(f"CNPJ with all repeated characters is invalid: {value!r}")
    if compute_check_digits(cnpj[:12]) != cnpj[12:]:
        raise ValueError(f"CNPJ check digits do not match: {value!r}")
    return cnpj


def format_cnpj(cnpj: str) -> str:
    """Format as XX.XXX.XXX/XXXX-XX."""
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
