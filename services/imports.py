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
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.security import ensure_aware, random_token, token_digest, utcnow
from app.db.models import ImportPreviewCache
from app.services.accounts import (
    apply_account_hierarchy,
    first_order_budget_total,
    hierarchy_order,
    hierarchy_total,
    is_budget_scope_account,
    is_first_order_account,
    normalize_code,
)
from app.services.budgets import active_budget_version, build_replacement_snapshot, create_budget_version

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
        name = str(
            row[columns["name"]]
            if columns["name"] < len(row) and row[columns["name"]] is not None
            else ""
        ).strip()
        budget = _parse_amount(row[columns["budget"]] if columns["budget"] < len(row) else 0)
        new_req = _parse_amount(
            row[columns["new"]]
            if "new" in columns and columns["new"] < len(row)
            else 0
        )
        cas = _parse_amount(
            row[columns["cas"]]
            if "cas" in columns and columns["cas"] < len(row)
            else 0
        )
        if not code and not name and not budget and not new_req and not cas:
            continue

        valid_structure = bool(code and name)
        in_budget_scope = bool(valid_structure and is_budget_scope_account(code))
        item = {
            "code": code,
            "name": name,
            "budget": budget,
            "budget_original": budget,
            "hierarchy_order": hierarchy_order(code) if code else None,
            "first_order": is_first_order_account(code) if code else False,
            "base_new_requirements": new_req,
            "obligated_cas": cas,
            "included": False,
            "calculated_from_children": False,
            "reason": (
                "Pendiente de cálculo jerárquico"
                if in_budget_scope
                else (
                    "Fuera del rango presupuestario: se consideran cuentas desde 215-21 en adelante"
                    if valid_structure
                    else "Fila incompleta"
                )
            ),
        }
        raw_rows.append(item)
        if in_budget_scope:
            unique[code] = item

    if not unique:
        raise AppError(
            "La planilla no contiene cuentas presupuestarias válidas desde 215-21 en adelante."
        )

    # Uploaded values are authoritative for their accounting code. We do not
    # add them to the previous budget and we do not overwrite parent amounts by
    # summing children. The merge with the currently active budget is prepared
    # later, inside save_preview(), where database state is available.
    candidate_accounts = apply_account_hierarchy([
        {
            "code": item["code"],
            "name": item["name"],
            "budget": int(item["budget"]),
            "base_new_requirements": int(item["base_new_requirements"]),
            "base_new_requirements_provided": "new" in columns,
            "obligated_cas": int(item["obligated_cas"]),
            "obligated_cas_provided": "cas" in columns,
        }
        for item in sorted(unique.values(), key=lambda row: row["code"])
    ])
    included_accounts = candidate_accounts

    included_codes = {item["code"] for item in included_accounts}
    for item in raw_rows:
        if item.get("code") in included_codes:
            item["included"] = True
            item["reason"] = "Cuenta incluida en la actualización"
        elif item.get("code") and item.get("name") and is_budget_scope_account(str(item.get("code"))):
            item["reason"] = "Cuenta no incluida"


    return {
        "filename": Path(filename).name[:255],
        "checksum": hashlib.sha256(content).hexdigest(),
        "rows_read": len(raw_rows),
        "valid_rows": len(unique),
        "included_rows": len(included_accounts),
        "excluded_rows": max(0, len(raw_rows) - len(included_accounts)),
        # Preliminary total for the uploaded rows. save_preview() replaces this
        # with the total of the resulting snapshot after merge-by-code.
        "total_budget": first_order_budget_total(included_accounts),
        "first_order_accounts": sum(
            1 for a in included_accounts if is_first_order_account(a["code"])
        ),
        "total_new_requirements": hierarchy_total(
            included_accounts, "base_new_requirements"
        ),
        "total_obligated_cas": hierarchy_total(
            included_accounts, "obligated_cas"
        ),
        "sample": raw_rows[:120],
        "accounts": included_accounts,
    }


def save_preview(db: Session, *, user_id: str, area: str, year: int, parsed: dict) -> tuple[str, dict]:
    db.execute(delete(ImportPreviewCache).where(ImportPreviewCache.expires_at <= utcnow()))

    snapshot = build_replacement_snapshot(
        db,
        area_slug=area,
        year=year,
        uploaded_accounts=parsed["accounts"],
    )
    status_by_code = snapshot.get("uploaded_status", {})
    sample = []
    for row in parsed["sample"]:
        item = dict(row)
        status = status_by_code.get(item.get("code"))
        if status == "new":
            item["reason"] = "Nueva cuenta: se incorporará al presupuesto vigente"
        elif status == "modified":
            item["reason"] = "Cuenta existente: el nuevo valor reemplazará al anterior"
        elif status == "unchanged":
            item["reason"] = "Cuenta existente sin cambios"
        sample.append(item)

    payload = dict(parsed)
    payload.update(
        {
            "accounts": snapshot["accounts"],
            "total_budget": snapshot["total_budget"],
            "previous_total_budget": snapshot["previous_total_budget"],
            "base_version_id": snapshot["base_version_id"],
            "base_version_number": snapshot["base_version_number"],
            "new_accounts": snapshot["new_accounts"],
            "modified_accounts": snapshot["modified_accounts"],
            "unchanged_uploaded_accounts": snapshot["unchanged_uploaded_accounts"],
            "retained_accounts": snapshot["retained_accounts"],
            "removed_accounts": snapshot.get("removed_accounts", 0),
            "first_order_accounts": sum(
                1 for account in snapshot["accounts"] if is_first_order_account(account["code"])
            ),
            "total_new_requirements": hierarchy_total(
                snapshot["accounts"], "base_new_requirements"
            ),
            "total_obligated_cas": hierarchy_total(
                snapshot["accounts"], "obligated_cas"
            ),
            "sample": sample,
        }
    )

    raw_token = random_token(32)
    cache = ImportPreviewCache(
        token_hash=token_digest(raw_token),
        user_id=user_id,
        area_slug=area,
        year=year,
        filename=parsed["filename"],
        checksum=parsed["checksum"],
        payload=payload,
        expires_at=utcnow() + timedelta(minutes=15),
    )
    db.add(cache)
    db.flush()
    response = {key: payload[key] for key in (
        "filename", "rows_read", "valid_rows", "included_rows", "excluded_rows",
        "total_budget", "previous_total_budget", "first_order_accounts",
        "total_new_requirements", "total_obligated_cas", "sample",
        "new_accounts", "modified_accounts", "unchanged_uploaded_accounts", "retained_accounts", "removed_accounts",
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

    expected_base = parsed.get("base_version_id")
    try:
        current = active_budget_version(db, area, year)
        current_id = current.id
    except NotFoundError:
        current_id = None
    if current_id != expected_base:
        raise ConflictError(
            "El presupuesto vigente cambió después de generar la vista previa. "
            "Vuelva a cargar la planilla para evitar sobrescribir cambios de otro usuario."
        )

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

