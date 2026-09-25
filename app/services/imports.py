from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.core.security import ensure_aware, random_token, token_digest, utcnow
from app.db.models import ImportPreviewCache
from app.services.accounts import (
    apply_account_hierarchy,
    first_order_budget_total,
    hierarchy_order,
    hierarchy_total,
    has_complete_first_order_coverage,
    is_first_order_account,
    normalize_code,
    should_include_account,
)
from app.services.budgets import create_budget_version

settings = get_settings()

HEADER_ALIASES = {
    "code": {"cuenta", "numero de cuenta", "n° de cuenta", "nº de cuenta", "codigo de cuenta", "codigo cuenta"},
    "name": {"denominacion", "nombre", "nombre de la cuenta", "nombre cuenta"},
    "budget": {"presupuesto vigente", "pto vigente", "presup vigente"},
    "new": {"pre obligado ze compras", "pre obligado de compras", "pre obligado compras", "nuevos requerimientos"},
    "cas": {"obligado cas", "obligado c.a.s", "cas obligado"},
}


def _normalize_header(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    text = re.sub(r"\s+", " ", text)
    return text


def _parse_amount(value: object) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(round(value)))
    text = str(value).strip().replace("$", "").replace(" ", "")
    if not text:
        return 0
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        last = text.split(",")[-1]
        text = text.replace(",", ".") if len(last) <= 2 else text.replace(",", "")
    elif "." in text:
        last = text.split(".")[-1]
        if len(last) == 3:
            text = text.replace(".", "")
    try:
        return max(0, int(round(float(text))))
    except ValueError:
        return 0


def _read_rows(filename: str, content: bytes) -> list[list[Any]]:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv", ".txt"}:
        raise AppError("Formato no permitido. Utilice .xlsx, .xls o .csv.", 415, "unsupported_file")
    if len(content) > settings.upload_max_bytes:
        raise AppError("La planilla supera el tamaño máximo permitido.", 413, "file_too_large")
    if suffix in {".csv", ".txt"}:
        decoded = None
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                decoded = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            raise AppError("No fue posible leer el archivo CSV.")
        dialect = csv.Sniffer().sniff(decoded[:4096], delimiters=",;\t|")
        return [row for row in csv.reader(io.StringIO(decoded), dialect)]
    if suffix == ".xlsx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                members = archive.infolist()
                expanded = sum(member.file_size for member in members)
                if len(members) > 2_000 or expanded > settings.xlsx_max_uncompressed_bytes:
                    raise AppError(
                        "La planilla Excel excede los límites seguros de procesamiento.",
                        413,
                        "xlsx_expansion_limit",
                    )
        except zipfile.BadZipFile as exc:
            raise AppError("El archivo .xlsx no es válido.") from exc
    engine = "openpyxl" if suffix == ".xlsx" else "xlrd"
    try:
        workbook = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None, engine=engine)
    except ImportError as exc:
        raise AppError("El servidor no tiene instalado el lector requerido para archivos .xls.") from exc
    except Exception as exc:
        raise AppError("La planilla Excel no pudo ser procesada.") from exc
    best: list[list[Any]] = []
    for dataframe in workbook.values():
        if dataframe.shape[0] > settings.import_max_rows or dataframe.shape[1] > settings.import_max_columns:
            raise AppError(
                "La planilla excede el máximo de filas o columnas permitido.",
                413,
                "spreadsheet_dimensions_limit",
            )
        rows = dataframe.where(pd.notna(dataframe), None).values.tolist()
        if len(rows) > len(best):
            best = rows
    return best


def _find_columns(rows: list[list[Any]]) -> tuple[int, dict[str, int]]:
    for row_index, row in enumerate(rows[:100]):
        normalized = [_normalize_header(cell) for cell in row]
        mapping: dict[str, int] = {}
        for field, aliases in HEADER_ALIASES.items():
            for index, value in enumerate(normalized):
                if value in aliases or any(alias in value for alias in aliases if len(alias) > 8):
                    mapping[field] = index
                    break
        if {"code", "name", "budget"}.issubset(mapping):
            return row_index, mapping
    raise AppError("No se encontraron las columnas CUENTA, DENOMINACIÓN y PRESUPUESTO VIGENTE.")


def parse_budget_file(filename: str, content: bytes) -> dict:
    rows = _read_rows(filename, content)
    header_row, columns = _find_columns(rows)
    raw_rows: list[dict] = []
    unique: dict[str, dict] = {}
    for row in rows[header_row + 1 :]:
        code = normalize_code(row[columns["code"]] if columns["code"] < len(row) else "")
        name = str(row[columns["name"]] if columns["name"] < len(row) and row[columns["name"]] is not None else "").strip()
        budget = _parse_amount(row[columns["budget"]] if columns["budget"] < len(row) else 0)
        new_req = _parse_amount(row[columns["new"]] if "new" in columns and columns["new"] < len(row) else 0)
        cas = _parse_amount(row[columns["cas"]] if "cas" in columns and columns["cas"] < len(row) else 0)
        if not code and not name and not budget and not new_req and not cas:
            continue
        valid = bool(code and name)
        included = valid and should_include_account(code, budget)
        reason = "Se incluirá" if included else ("Sin presupuesto vigente" if valid else "Fila incompleta")
        item = {
            "code": code,
            "name": name,
            "budget": budget,
            "hierarchy_order": hierarchy_order(code) if code else None,
            "first_order": is_first_order_account(code) if code else False,
            "base_new_requirements": new_req,
            "obligated_cas": cas,
            "included": included,
            "reason": reason,
        }
        raw_rows.append(item)
        if valid:
            unique[code] = item
    included_accounts = []
    for item in sorted(unique.values(), key=lambda row: row["code"]):
        if not item["included"]:
            continue
        included_accounts.append(
            {
                "code": item["code"],
                "name": item["name"],
                "budget": item["budget"],
                "base_new_requirements": item["base_new_requirements"],
                "obligated_cas": item["obligated_cas"],
                # If the spreadsheet omits OBLIGADO CAS, preserve the value from
                # the current budget version for the same account when applying.
                "obligated_cas_provided": "cas" in columns,
            }
        )
    if not included_accounts:
        raise AppError("La planilla no contiene cuentas con presupuesto vigente mayor a cero.")

    # The total budget is defined only by structural first-order accounts.
    # Validate against all valid rows (including zero-budget summaries) so a
    # missing order-1 row cannot silently promote a lower-order subtotal.
    valid_hierarchy_rows = [
        {"code": item["code"], "budget": item["budget"]}
        for item in unique.values()
        if item.get("code") and item.get("name")
    ]
    if not has_complete_first_order_coverage(valid_hierarchy_rows):
        raise AppError(
            "La planilla no contiene todas las cuentas de primer orden necesarias para calcular el presupuesto total. "
            "Incluya las cuentas resumen, por ejemplo 215-22-00-000-000-000 (o 22-00-000-000-000).",
            422,
            "missing_first_order_accounts",
        )

    # Resolve the hierarchy only after all rows are known. This allows a parent
    # such as 22-00-000-000-000 to contain 22-01..., which in turn contains
    # 22-01-001... and 22-01-002..., without adding every level to the total.
    included_accounts = apply_account_hierarchy(included_accounts)
    return {
        "filename": Path(filename).name[:255],
        "checksum": hashlib.sha256(content).hexdigest(),
        "rows_read": len(raw_rows),
        "valid_rows": len(unique),
        "included_rows": len(included_accounts),
        "excluded_rows": max(0, len(raw_rows) - len(included_accounts)),
        # The overall budget is strictly the sum of structural first-order
        # accounts (e.g. 215-22-00-000-000-000). Children are displayed but
        # never promoted into the total when a parent is absent.
        "total_budget": first_order_budget_total(included_accounts),
        "first_order_accounts": sum(1 for a in valid_hierarchy_rows if is_first_order_account(a["code"])),
        # These two columns can also be repeated at parent/child levels in source
        # spreadsheets, so calculate them without double counting branches.
        "total_new_requirements": hierarchy_total(included_accounts, "base_new_requirements"),
        "total_obligated_cas": hierarchy_total(included_accounts, "obligated_cas"),
        "sample": raw_rows[:120],
        "accounts": included_accounts,
    }


def save_preview(db: Session, *, user_id: str, area: str, year: int, parsed: dict) -> tuple[str, dict]:
    db.execute(delete(ImportPreviewCache).where(ImportPreviewCache.expires_at <= utcnow()))
    raw_token = random_token(32)
    cache = ImportPreviewCache(
        token_hash=token_digest(raw_token),
        user_id=user_id,
        area_slug=area,
        year=year,
        filename=parsed["filename"],
        checksum=parsed["checksum"],
        payload=parsed,
        expires_at=utcnow() + timedelta(minutes=15),
    )
    db.add(cache)
    db.flush()
    response = {key: parsed[key] for key in (
        "filename", "rows_read", "valid_rows", "included_rows", "excluded_rows",
        "total_budget", "first_order_accounts", "total_new_requirements", "total_obligated_cas", "sample"
    )}
    response.update({"token": raw_token, "area": area, "year": year})
    return raw_token, response


def apply_preview(db: Session, *, token: str, user_id: str, area: str, year: int):
    cache = db.get(ImportPreviewCache, token_digest(token))
    if not cache or ensure_aware(cache.expires_at) <= utcnow():
        raise NotFoundError("La vista previa expiró. Cargue nuevamente la planilla.")
    if cache.user_id != user_id or cache.area_slug != area or cache.year != year:
        raise AppError("La vista previa no corresponde al usuario, área o año seleccionados.", 403, "preview_mismatch")
    parsed = cache.payload
    version = create_budget_version(
        db,
        area_slug=area,
        year=year,
        source_name=cache.filename,
        source_checksum=cache.checksum,
        accounts=parsed["accounts"],
        user_id=user_id,
    )
    db.delete(cache)
    db.flush()
    return version
