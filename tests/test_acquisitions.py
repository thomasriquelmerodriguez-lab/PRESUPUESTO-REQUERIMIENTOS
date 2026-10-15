from datetime import date

from tests.conftest import login


def _csrf_headers(token):
    return {"origin": "http://testserver", "x-csrf-token": token}


def test_purchase_order_closure_releases_difference_and_reconciliation_avoids_double_discount(client):
    csrf = login(client)
    catalog = client.get('/api/budgets/municipal/2026/catalog').json()
    account = next(item for item in catalog['accounts'] if item['level'] > 0 and item['available'] > 12_000_000)
    initial_available = account['available']

    created = client.post(
        '/api/requirements',
        json={
            'area': 'municipal',
            'budget_year': 2026,
            'request_date': date.today().isoformat(),
            'expedient': 'TEST-OC-10M',
            'subject': 'Licitación de pelotas',
            'amount': 10_000_000,
            'department': 'Deportes',
            'management_area': 'Gestión interna',
            'notes': '',
            'account_code': account['code'],
            'allow_over_budget': False,
            'over_budget_reason': '',
        },
        headers=_csrf_headers(csrf),
    )
    assert created.status_code == 201, created.text
    requirement_id = created.json()['id']

    after_request = client.get('/api/budgets/municipal/2026/catalog').json()
    after_request_account = next(item for item in after_request['accounts'] if item['code'] == account['code'])
    assert after_request_account['available'] == initial_available - 10_000_000

    order_response = client.post(
        f'/api/acquisitions/{requirement_id}/orders',
        params={'area': 'municipal'},
        json={
            'order_number': 'OC-7000',
            'order_date': date.today().isoformat(),
            'supplier': 'Empresa de prueba',
            'amount': 7_000_000,
            'tender_reference': 'LIC-PEL-001',
            'notes': '',
            'close_requirement': False,
        },
        headers=_csrf_headers(csrf),
    )
    assert order_response.status_code == 201, order_response.text
    detail = order_response.json()
    assert detail['orders_total'] == 7_000_000
    assert detail['reservation_pending'] == 3_000_000
    assert detail['effective_commitment'] == 10_000_000

    closed_response = client.patch(
        f'/api/acquisitions/{requirement_id}/status',
        params={'area': 'municipal'},
        json={'status': 'CERRADO', 'closed': True},
        headers=_csrf_headers(csrf),
    )
    assert closed_response.status_code == 200, closed_response.text
    closed = closed_response.json()
    assert closed['released_amount'] == 3_000_000
    assert closed['reservation_pending'] == 0
    assert closed['effective_commitment'] == 7_000_000

    after_close = client.get('/api/budgets/municipal/2026/catalog').json()
    after_close_account = next(item for item in after_close['accounts'] if item['code'] == account['code'])
    assert after_close_account['available'] == initial_available - 7_000_000

    order = closed['orders'][0]
    reconciled_response = client.patch(
        f'/api/acquisitions/{requirement_id}/orders/{order["id"]}/cas',
        params={'area': 'municipal'},
        json={'reconciled': True, 'version': order['version']},
        headers=_csrf_headers(csrf),
    )
    assert reconciled_response.status_code == 200, reconciled_response.text
    reconciled = reconciled_response.json()
    assert reconciled['orders_reconciled_cas'] == 7_000_000
    assert reconciled['orders_pending_cas'] == 0
    assert reconciled['effective_commitment'] == 0

    # Once reconciled, the OC is expected to be represented by Obligado CAS and
    # therefore is no longer deducted a second time as a requirement/OC commitment.
    after_reconcile = client.get('/api/budgets/municipal/2026/catalog').json()
    after_reconcile_account = next(item for item in after_reconcile['accounts'] if item['code'] == account['code'])
    assert after_reconcile_account['available'] == initial_available

    current_req = client.get(f'/api/requirements/{requirement_id}', params={'area': 'municipal'}).json()
    deleted = client.delete(
        f'/api/requirements/{requirement_id}',
        params={'area': 'municipal', 'version': current_req['version']},
        headers=_csrf_headers(csrf),
    )
    assert deleted.status_code == 200, deleted.text
