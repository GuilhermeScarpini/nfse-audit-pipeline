import random

import pytest

from nfse_audit.domain.cnpj import compute_check_digits, format_cnpj, normalize_cnpj

# No hardcoded numeric CNPJ: any valid one may belong to a real company. Numeric cases
# are built at test time from random bases; the only literal is the official RFB example.
_rng = random.Random(2026)
NUMERIC_BASES = ["".join(_rng.choices("0123456789", k=12)) for _ in range(50)]
NUMERIC_CNPJ = NUMERIC_BASES[0] + compute_check_digits(NUMERIC_BASES[0])


def _classic_numeric_check_digits(base: str) -> str:
    """Independent reference: the pre-2026 algorithm, defined only for digits."""
    digits = [int(char) for char in base]
    for weights in ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)):
        remainder = sum(d * w for d, w in zip(digits, weights, strict=True)) % 11
        digits.append(0 if remainder < 2 else 11 - remainder)
    return f"{digits[-2]}{digits[-1]}"


@pytest.mark.parametrize("base", NUMERIC_BASES)
def test_numeric_check_digits_match_the_classic_algorithm(base):
    assert compute_check_digits(base) == _classic_numeric_check_digits(base)


def test_alphanumeric_check_digits_match_the_official_example():
    assert compute_check_digits("12ABC34501DE") == "35"  # published by the Receita Federal


@pytest.mark.parametrize(
    "raw",
    [NUMERIC_CNPJ, format_cnpj(NUMERIC_CNPJ), "12.abc.345/01de-35", " 12ABC34501DE35 "],
)
def test_normalize_accepts_formatted_and_lowercase(raw):
    assert normalize_cnpj(raw) in {NUMERIC_CNPJ, "12ABC34501DE35"}


def _wrong_check_digit(cnpj: str) -> str:
    return cnpj[:13] + str((int(cnpj[13]) + 1) % 10)


@pytest.mark.parametrize(
    "raw",
    [
        _wrong_check_digit(NUMERIC_CNPJ),
        NUMERIC_CNPJ[:13],  # too short
        "12ABC34501DE3A",  # letters are not allowed in the check digits
        "00000000000000",  # passes modulo 11, but is a known invalid placeholder
        "",
    ],
)
def test_normalize_rejects_invalid(raw):
    with pytest.raises(ValueError):
        normalize_cnpj(raw)


def test_format_cnpj():
    assert format_cnpj("12ABC34501DE35") == "12.ABC.345/01DE-35"
