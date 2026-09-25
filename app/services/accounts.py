from __future__ import annotations

import re

ACCOUNT_PATTERN = re.compile(r"^\d{3}(?:-\d{2,3}){2,5}$")


def normalize_code(value: object) -> str:
    text = str(value or "").strip().replace(".", "-").replace("/", "-")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def code_parts(code: str) -> list[str]:
    return normalize_code(code).split("-")


def padded_parts(code: str) -> list[str]:
    parts = code_parts(code)
    if not parts or parts[0] != "215":
        return parts
    while len(parts) < 6:
        parts.append("000")
    return parts[:6]


def matrix_code(code: str) -> str:
    p = padded_parts(code)
    if len(p) < 3:
        return normalize_code(code)
    if p[1] in {"24", "31"}:
        return "-".join([p[0], p[1], "00", "000", "000", "000"])
    return "-".join([p[0], p[1], p[2], "000", "000", "000"])


def hierarchy_level(code: str) -> int:
    p = padded_parts(code)
    if len(p) < 3:
        return 0
    start = 2 if p[1] in {"24", "31"} else 3
    return sum(1 for segment in p[start:] if int(segment or "0") != 0)


def parent_code(code: str) -> str | None:
    p = padded_parts(code)
    if len(p) < 3:
        return None
    start = 2 if p[1] in {"24", "31"} else 3
    non_zero = [i for i in range(start, len(p)) if int(p[i] or "0") != 0]
    if not non_zero:
        return None
    last = non_zero[-1]
    for i in range(last, len(p)):
        p[i] = "000" if i >= 3 else "00"
    return "-".join(p)


def is_matrix(code: str) -> bool:
    return normalize_code(code) == matrix_code(code)


def is_direct(code: str) -> bool:
    return hierarchy_level(code) <= 1


def should_include_account(code: str, budget: int) -> bool:
    if budget <= 0:
        return False
    p = padded_parts(code)
    if len(p) < 2:
        return False
    if p[1] in {"22", "24", "31"}:
        return True
    return is_matrix(code) or is_direct(code)
