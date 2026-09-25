from __future__ import annotations

import re
from collections.abc import Iterable

ACCOUNT_PATTERN = re.compile(r"^\d{2,3}(?:-\d{2,3}){2,5}$")


def normalize_code(value: object) -> str:
    text = str(value or "").strip().replace(".", "-").replace("/", "-")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def code_parts(code: str) -> list[str]:
    return normalize_code(code).split("-")


def padded_parts(code: str) -> list[str]:
    """Compatibility helper for the six-segment 215 municipal format."""
    parts = code_parts(code)
    if not parts or parts[0] != "215":
        return parts
    while len(parts) < 6:
        parts.append("000")
    return parts[:6]


def _hierarchy_start(parts: list[str]) -> int:
    """Index where the hierarchy below the expenditure item starts.

    Full municipal codes normally look like 215-22-01-001-000-000.  In that
    representation 215 is the account class and 22 is the item, so the first
    child segment is index 2.  Some uploaded spreadsheets omit 215 and use
    22-01-001-000-000; there the first child segment is index 1.
    """
    return 2 if parts and parts[0] == "215" else 1


def _is_nonzero(segment: str) -> bool:
    try:
        return int(segment or "0") != 0
    except ValueError:
        return bool(segment.strip("0"))


def _zero_like(segment: str) -> str:
    return "0" * max(1, len(segment))


def ancestor_candidates(code: str) -> list[str]:
    """Return structural ancestors from nearest to farthest.

    Example:
      215-22-01-001-000-000
        -> 215-22-01-000-000-000
        -> 215-22-00-000-000-000

    The function intentionally does not assume that every ancestor exists in a
    particular spreadsheet.  The catalog-aware hierarchy resolver below picks
    the nearest ancestor that is actually present.
    """
    parts = code_parts(code)
    if len(parts) < 2:
        return []
    start = _hierarchy_start(parts)
    ancestors: list[str] = []
    for index in range(len(parts) - 1, start - 1, -1):
        if not _is_nonzero(parts[index]):
            continue
        parent = parts.copy()
        for child_index in range(index, len(parent)):
            parent[child_index] = _zero_like(parent[child_index])
        candidate = "-".join(parent)
        if candidate != normalize_code(code) and candidate not in ancestors:
            ancestors.append(candidate)
    return ancestors


def parent_code(code: str) -> str | None:
    """Return the immediate structural parent, whether or not it is present."""
    candidates = ancestor_candidates(code)
    return candidates[0] if candidates else None


def hierarchy_level(code: str) -> int:
    """Structural depth below the item segment.

    This is useful as a fallback.  For imported catalogs use
    ``apply_account_hierarchy`` because it adjusts the level to the ancestors
    that are actually present in the spreadsheet.
    """
    parts = code_parts(code)
    if len(parts) < 2:
        return 0
    start = _hierarchy_start(parts)
    return sum(1 for segment in parts[start:] if _is_nonzero(segment))




def hierarchy_order(code: str) -> int:
    """Return the structural accounting order, independent of uploaded rows.

    Order 1 is the item summary itself, e.g. 215-22-00-000-000-000 or
    22-00-000-000-000. Order 2 is 22-01-000..., order 3 is
    22-01-001..., and so on. Unlike ``apply_account_hierarchy`` this never
    promotes a child just because its parent is absent from the spreadsheet.
    """
    return hierarchy_level(code) + 1


def is_first_order_account(code: str) -> bool:
    """True only for structural first-order accounts such as 22-00-000-000-000."""
    parts = code_parts(code)
    if len(parts) < 2:
        return False
    start = _hierarchy_start(parts)
    return all(not _is_nonzero(segment) for segment in parts[start:])


def first_order_budget_total(accounts: Iterable[dict], value_key: str = "budget") -> int:
    """Sum only structural first-order accounts.

    Child rows and subtotals remain in the catalog but never increase the
    overall budget. This is intentionally stricter than catalog roots.
    """
    return sum(
        max(0, int(item.get(value_key, 0) or 0))
        for item in accounts
        if is_first_order_account(str(item.get("code") or ""))
    )


def first_order_group(code: str) -> str:
    """Return the expenditure item group used to validate first-order coverage."""
    parts = code_parts(code)
    if not parts:
        return ""
    if parts[0] == "215" and len(parts) >= 2:
        return "-".join(parts[:2])
    return parts[0]


def has_complete_first_order_coverage(accounts: Iterable[dict]) -> bool:
    """Whether every expenditure item represented has its order-1 summary row."""
    rows = list(accounts)
    groups = {first_order_group(str(item.get("code") or "")) for item in rows}
    groups.discard("")
    first_groups = {
        first_order_group(str(item.get("code") or ""))
        for item in rows
        if is_first_order_account(str(item.get("code") or ""))
    }
    return bool(groups) and groups.issubset(first_groups)

def matrix_code(code: str) -> str:
    """Return the structural top account below the item.

    Catalogs that do not contain that top account are handled by
    ``apply_account_hierarchy``; this function remains a deterministic fallback.
    """
    candidates = ancestor_candidates(code)
    return candidates[-1] if candidates else normalize_code(code)


def apply_account_hierarchy(accounts: Iterable[dict]) -> list[dict]:
    """Attach parent, level and matrix using only rows present in the catalog.

    This is the key rule that prevents double counting.  Summary rows are kept
    as parents instead of being treated as additional independent budget rows.

    If the uploaded file contains:
      22-00-000-000-000
      22-01-000-000-000
      22-01-001-000-000
      22-01-002-000-000

    the resolved tree is:
      22-00...                level 0 / matrix
        22-01...              level 1
          22-01-001...        level 2
          22-01-002...        level 2

    If a summary row (for example 22-00...) is absent, the nearest existing
    rows become roots.  That keeps older budget files compatible.
    """
    rows = [dict(item) for item in accounts]
    code_set = {normalize_code(item.get("code")) for item in rows if normalize_code(item.get("code"))}

    parent_by_code: dict[str, str | None] = {}
    for code in code_set:
        parent_by_code[code] = next(
            (candidate for candidate in ancestor_candidates(code) if candidate in code_set),
            None,
        )

    root_cache: dict[str, tuple[str, int]] = {}

    def root_and_level(code: str) -> tuple[str, int]:
        if code in root_cache:
            return root_cache[code]
        seen: set[str] = set()
        current = code
        level = 0
        while parent_by_code.get(current):
            if current in seen:  # defensive guard for malformed custom codes
                break
            seen.add(current)
            current = parent_by_code[current]  # type: ignore[index]
            level += 1
        root_cache[code] = (current, level)
        return root_cache[code]

    resolved: list[dict] = []
    for item in rows:
        code = normalize_code(item.get("code"))
        if not code:
            continue
        root, level = root_and_level(code)
        item["code"] = code
        item["parent_code"] = parent_by_code.get(code)
        item["matrix_code"] = root
        item["level"] = level
        resolved.append(item)
    return resolved


def hierarchy_total(accounts: Iterable[dict], value_key: str) -> int:
    """Return a non-duplicated total for a value repeated through a hierarchy.

    A parent row in budget spreadsheets often contains the aggregate amount of
    its children.  We therefore take, for each branch, the greater of the value
    stored at the parent or the sum of its child branches.  This works both when
    only leaf rows have values and when summary rows repeat those totals.
    """
    rows = apply_account_hierarchy(accounts)
    by_code = {item["code"]: item for item in rows}
    children: dict[str, list[str]] = {code: [] for code in by_code}
    for item in rows:
        parent = item.get("parent_code")
        if parent in children:
            children[parent].append(item["code"])

    memo: dict[str, int] = {}

    def branch_total(code: str) -> int:
        if code in memo:
            return memo[code]
        direct = max(0, int(by_code[code].get(value_key, 0) or 0))
        descendants = sum(branch_total(child) for child in children.get(code, []))
        memo[code] = max(direct, descendants)
        return memo[code]

    roots = [code for code, item in by_code.items() if not item.get("parent_code")]
    return sum(branch_total(code) for code in roots)


def is_matrix(code: str) -> bool:
    return normalize_code(code) == matrix_code(code)


def is_direct(code: str) -> bool:
    return hierarchy_level(code) <= 1


def should_include_account(code: str, budget: int) -> bool:
    # Keep every valid positive-budget row. Hierarchy is resolved after the full
    # spreadsheet has been read, so parent rows are not discarded or summed as
    # independent lines.
    if budget <= 0:
        return False
    parts = code_parts(code)
    return len(parts) >= 2 and all(part.isdigit() for part in parts)
