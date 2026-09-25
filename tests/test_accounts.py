from app.services.accounts import hierarchy_level, matrix_code, parent_code


def test_account_hierarchy():
    code = "215-22-03-001-902-000"
    assert matrix_code(code) == "215-22-03-000-000-000"
    assert hierarchy_level(code) == 2
    assert parent_code(code) == "215-22-03-001-000-000"


def test_special_matrix_hierarchy():
    code = "215-31-02-004-902-336"
    assert matrix_code(code) == "215-31-00-000-000-000"
    assert hierarchy_level(code) == 4
