from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.deps import CurrentUser, DbDep, require_area, require_permission
from app.core.config import BASE_DIR
from app.services.budgets import catalog, decision_dashboard
from app.services.requirements import list_requirements

router = APIRouter(prefix="/reports", tags=["reports"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@router.get("/requirements", response_class=HTMLResponse)
def requirements_report(
    request: Request,
    db: DbDep,
    user: CurrentUser,
    area: str = Query(...),
    year: int = Query(..., ge=2020, le=2100),
    matrix: str = Query(..., max_length=40),
    account: str | None = Query(default=None, max_length=40),
    q: str | None = Query(default=None, max_length=120),
):
    require_area(user, area)
    require_permission(user, "reports.generate")
    records = list_requirements(
        db,
        area_slug=area,
        year=year,
        matrix=matrix,
        account_code=account,
        search_text=q,
        page=1,
        page_size=100_000,
    )
    budget = catalog(db, area, year, matrix=matrix)
    account_lookup = {item["code"]: item for item in budget["accounts"]}
    summary: dict[str, dict] = defaultdict(lambda: {"count": 0, "amount": 0, "name": ""})
    for item in records["items"]:
        bucket = summary[item["account_code"]]
        bucket["count"] += 1
        bucket["amount"] += item["amount"]
        bucket["name"] = item.get("account_name") or account_lookup.get(item["account_code"], {}).get("name", "")
    matrix_name = account_lookup.get(matrix, {}).get("name") or next(
        (item["name"] for item in budget["accounts"] if item["matrix_code"] == matrix and item["level"] == 0),
        matrix,
    )
    return templates.TemplateResponse(
        request=request,
        name="report.html",
        context={
            "area": area.capitalize(),
            "year": year,
            "matrix": matrix,
            "matrix_name": matrix_name,
            "account": account,
            "records": records["items"],
            "total": records["total"],
            "total_amount": records["total_amount"],
            "summary": sorted(summary.items()),
            "generated_at": datetime.now().strftime("%d-%m-%Y %H:%M"),
            "generated_by": user["display_name"],
        },
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_report(
    request: Request,
    db: DbDep,
    user: CurrentUser,
    area: str = Query(...),
    year: int = Query(..., ge=2020, le=2100),
    matrix: str | None = Query(default=None, max_length=40),
    account: str | None = Query(default=None, max_length=40),
):
    require_area(user, area)
    require_permission(user, "reports.generate")
    data = decision_dashboard(
        db, area, year, matrix=matrix, account_code=account
    )
    max_month = max((item["requirements_amount"] for item in data["monthly"]), default=0) or 1
    max_breakdown = max((item["budget"] for item in data["breakdown"]), default=0) or 1
    return templates.TemplateResponse(
        request=request,
        name="dashboard_report.html",
        context={
            "area": area.capitalize(),
            "year": year,
            "data": data,
            "max_month": max_month,
            "max_breakdown": max_breakdown,
            "generated_at": datetime.now().strftime("%d-%m-%Y %H:%M"),
            "generated_by": user["display_name"],
        },
    )
