from app.services.accounts import (
    apply_account_hierarchy,
    hierarchy_level,
    hierarchy_total,
    matrix_code,
    parent_code,
)


def test_account_hierarchy_structural():
    code = "215-22-03-001-902-000"
    assert matrix_code(code) == "215-22-00-000-000-000"
    assert hierarchy_level(code) == 3
    assert parent_code(code) == "215-22-03-001-000-000"


def test_special_matrix_hierarchy():
    code = "215-31-02-004-902-336"
    assert matrix_code(code) == "215-31-00-000-000-000"
    assert hierarchy_level(code) == 4


def test_requested_22_hierarchy_prevents_double_counting():
    rows = [
        {"code": "215-22-00-000-000-000", "budget": 1_000, "obligated_cas": 100},
        {"code": "215-22-01-000-000-000", "budget": 600, "obligated_cas": 60},
        {"code": "215-22-01-001-000-000", "budget": 250, "obligated_cas": 20},
        {"code": "215-22-01-002-000-000", "budget": 350, "obligated_cas": 40},
        {"code": "215-22-02-000-000-000", "budget": 400, "obligated_cas": 40},
    ]
    resolved = apply_account_hierarchy(rows)
    by_code = {row["code"]: row for row in resolved}

    assert by_code["215-22-00-000-000-000"]["level"] == 0
    assert by_code["215-22-01-000-000-000"]["parent_code"] == "215-22-00-000-000-000"
    assert by_code["215-22-01-000-000-000"]["level"] == 1
    assert by_code["215-22-01-001-000-000"]["parent_code"] == "215-22-01-000-000-000"
    assert by_code["215-22-01-001-000-000"]["level"] == 2
    assert by_code["215-22-01-002-000-000"]["level"] == 2

    # Only the level-0 summary is the budget total, not 1000+600+250+350+400.
    assert sum(row["budget"] for row in resolved if row["level"] == 0) == 1_000
    # CAS repeated at parent and child levels is also counted once.
    assert hierarchy_total(resolved, "obligated_cas") == 100


def test_short_code_hierarchy_is_supported():
    rows = [
        {"code": "22-00-000-000-000", "budget": 1_000},
        {"code": "22-01-000-000-000", "budget": 600},
        {"code": "22-01-001-000-000", "budget": 250},
        {"code": "22-01-002-000-000", "budget": 350},
    ]
    resolved = apply_account_hierarchy(rows)
    by_code = {row["code"]: row for row in resolved}
    assert by_code["22-00-000-000-000"]["level"] == 0
    assert by_code["22-01-000-000-000"]["parent_code"] == "22-00-000-000-000"
    assert by_code["22-01-001-000-000"]["parent_code"] == "22-01-000-000-000"


def test_missing_summary_row_becomes_compatible_root():
    rows = [
        {"code": "215-22-01-000-000-000", "budget": 600},
        {"code": "215-22-01-001-000-000", "budget": 250},
        {"code": "215-22-01-002-000-000", "budget": 350},
    ]
    resolved = apply_account_hierarchy(rows)
    by_code = {row["code"]: row for row in resolved}
    assert by_code["215-22-01-000-000-000"]["level"] == 0
    assert by_code["215-22-01-001-000-000"]["level"] == 1
    assert by_code["215-22-01-001-000-000"]["matrix_code"] == "215-22-01-000-000-000"
