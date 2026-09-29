from app.services.accounts import is_first_order_account
from tests.conftest import login


def test_decision_dashboard_uses_non_duplicated_budget_totals(client):
    login(client)
    dashboard = client.get('/api/budgets/municipal/2026/decision-dashboard')
    assert dashboard.status_code == 200, dashboard.text
    data = dashboard.json()
    catalog = client.get('/api/budgets/municipal/2026/catalog').json()

    assert data['total_budget'] == catalog['total_budget']
    assert data['total_requirements'] == catalog['total_new_requirements']
    assert data['total_obligated_cas'] == catalog['total_obligated_cas']
    assert data['total_available'] == (
        data['total_budget'] - data['total_requirements'] - data['total_obligated_cas']
    )
    assert len(data['monthly']) == 12
    assert sum(item['requirements_amount'] for item in data['monthly']) == data['total_requirements']
    assert data['breakdown']
    assert all(is_first_order_account(item['code']) for item in data['breakdown'])


def test_decision_dashboard_can_drill_into_first_order_account(client):
    login(client)
    overview = client.get('/api/budgets/municipal/2026/decision-dashboard').json()
    root = overview['breakdown'][0]
    response = client.get(
        '/api/budgets/municipal/2026/decision-dashboard',
        params={'matrix': root['code']},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['scope_code'] == root['code']
    assert data['total_budget'] == root['budget']
    assert data['total_requirements'] == root['requirements']
    assert data['total_available'] == (
        data['total_budget'] - data['total_requirements'] - data['total_obligated_cas']
    )


def test_dashboard_report_is_available_for_manager(client):
    login(client)
    response = client.get('/api/reports/dashboard', params={'area': 'municipal', 'year': 2026})
    assert response.status_code == 200, response.text
    assert 'Dashboard de gestión presupuestaria' in response.text
