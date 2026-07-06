from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable, Optional, Tuple

import numpy as np
import pandas as pd

MONTHS_ES = {
    "ene": 1, "enero": 1,
    "feb": 2, "febrero": 2,
    "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4,
    "may": 5, "mayo": 5,
    "jun": 6, "junio": 6,
    "jul": 7, "julio": 7,
    "ago": 8, "agosto": 8,
    "sep": 9, "sept": 9, "septiembre": 9,
    "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12,
}


def _clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _parse_month_year_from_filename(name: str) -> Tuple[Optional[int], Optional[int]]:
    m = re.search(r"(0?[1-9]|1[0-2])[._ -](20\d{2})", name)
    if m:
        return int(m.group(2)), int(m.group(1))
    lower = name.lower()
    for token, month in MONTHS_ES.items():
        m2 = re.search(rf"\b{token}\b.*?(20\d{{2}})", lower)
        if m2:
            return int(m2.group(1)), month
    return None, None


def _parse_month_year_from_cells(raw: pd.DataFrame) -> Tuple[Optional[int], Optional[int]]:
    text = " ".join(_clean_text(x).lower() for x in raw.iloc[:12, :8].to_numpy().ravel())
    for token, month in MONTHS_ES.items():
        m = re.search(rf"\b{token}\b\s*(20\d{{2}})", text)
        if m:
            return int(m.group(1)), month
    y = re.search(r"\b(20\d{2})\b", text)
    return (int(y.group(1)), None) if y else (None, None)


def _find_header_row(raw: pd.DataFrame) -> int:
    for idx in range(min(20, len(raw))):
        vals = [_clean_text(v).lower() for v in raw.iloc[idx].tolist()]
        joined = " | ".join(vals)
        if "nombre 1" in joined and ("texto flejera" in joined or "material sap" in joined):
            return idx
    raise ValueError("No encontré la fila de encabezados del sell out.")


def _find_total_columns(header: list) -> Tuple[Optional[int], Optional[int]]:
    unidad_col, monto_col = None, None
    for i, value in enumerate(header):
        txt = _clean_text(value).lower()
        if "s.o" in txt or "sell out" in txt:
            if "unidad" in txt or "u" in txt:
                unidad_col = i
            if "$" in txt or "monto" in txt or "valor" in txt:
                monto_col = i
    return unidad_col, monto_col


def _numeric_day_columns(header: list, start: int, end: int) -> dict[int, int]:
    result = {}
    for i in range(start, end):
        val = header[i]
        if pd.isna(val):
            continue
        try:
            day = int(float(val))
            if 1 <= day <= 31:
                result[i] = day
        except Exception:
            continue
    return result


def read_sellout_file(file, source_name: str | None = None) -> pd.DataFrame:
    """Read Autoplanet sell-out Excel matrix and return normalized daily rows."""
    source_name = source_name or getattr(file, "name", "sellout.xlsx")
    xls = pd.ExcelFile(file)
    raw = pd.read_excel(xls, sheet_name=xls.sheet_names[0], header=None)
    header_row = _find_header_row(raw)
    header = raw.iloc[header_row].tolist()
    data = raw.iloc[header_row + 1 :].copy()
    data = data.dropna(how="all")

    year, month = _parse_month_year_from_filename(source_name)
    if not (year and month):
        y2, m2 = _parse_month_year_from_cells(raw)
        year = year or y2
        month = month or m2
    if not (year and month):
        raise ValueError(f"No pude detectar mes/año en {source_name}. Usa nombre tipo Sell out 06.2026.xlsx")

    store_col = 2
    category_col = 3
    sku_col = 4
    product_col = 5
    total_units_col, total_sales_col = _find_total_columns(header)

    # Identify day columns. First block units, second block sales.
    if total_units_col is None:
        total_units_col = len(header) - 2
    if total_sales_col is None:
        total_sales_col = len(header) - 1
    all_day_cols = _numeric_day_columns(header, 0, min(total_units_col, len(header)))
    unit_cols = {c: d for c, d in all_day_cols.items() if c > product_col}
    sales_cols = _numeric_day_columns(header, total_units_col + 1 if total_units_col else 0, total_sales_col or len(header))

    records = []
    for _, row in data.iterrows():
        store = _clean_text(row.iloc[store_col] if store_col < len(row) else "")
        product = _clean_text(row.iloc[product_col] if product_col < len(row) else "")
        if not store or not product or store.lower().startswith("total"):
            continue
        category = _clean_text(row.iloc[category_col] if category_col < len(row) else "Sin categoría") or "Sin categoría"
        sku = _clean_text(row.iloc[sku_col] if sku_col < len(row) else "")
        for ucol, day in unit_cols.items():
            try:
                dt = pd.Timestamp(year=year, month=month, day=day)
            except Exception:
                continue
            units = pd.to_numeric(row.iloc[ucol], errors="coerce") if ucol < len(row) else np.nan
            # match sales by same day in sales_cols
            scol = next((c for c, d in sales_cols.items() if d == day), None)
            sales = pd.to_numeric(row.iloc[scol], errors="coerce") if scol is not None and scol < len(row) else np.nan
            if pd.isna(units) and pd.isna(sales):
                continue
            records.append({
                "fecha": dt,
                "mes": dt.strftime("%Y-%m"),
                "dia": int(day),
                "dia_semana": dt.day_name(locale=None),
                "tienda": store,
                "categoria": category,
                "sku": sku,
                "producto": product,
                "unidades": float(units) if not pd.isna(units) else 0.0,
                "venta": float(sales) if not pd.isna(sales) else 0.0,
                "archivo": source_name,
            })
    out = pd.DataFrame(records)
    if out.empty:
        raise ValueError(f"No encontré ventas diarias en {source_name}.")
    out["dia_semana"] = out["fecha"].dt.day_name().map({
        "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles", "Thursday": "Jueves",
        "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo"
    })
    return out


def read_sellout_files(files: Iterable) -> pd.DataFrame:
    frames = []
    errors = []
    for f in files:
        try:
            frames.append(read_sellout_file(f, getattr(f, "name", None)))
        except Exception as exc:
            errors.append(f"{getattr(f, 'name', 'archivo')}: {exc}")
    if not frames:
        raise ValueError("No se pudo leer ningún archivo de sell out. " + " | ".join(errors))
    out = pd.concat(frames, ignore_index=True)
    return out, errors


def read_promoters_file(file) -> pd.DataFrame:
    raw = pd.read_excel(file, header=None)
    # find row with store metadata headers
    header_row = 0
    for i in range(min(10, len(raw))):
        vals = " | ".join(_clean_text(x).lower() for x in raw.iloc[i].tolist())
        if "cod local" in vals and "nombre local" in vals:
            header_row = i
            break
    header = raw.iloc[header_row].tolist()
    data = raw.iloc[header_row + 1:].dropna(how="all").copy()

    # detect metadata columns
    def col_contains(term):
        for idx, val in enumerate(header):
            if term in _clean_text(val).lower():
                return idx
        return None
    code_col = col_contains("cod local") or 0
    store_col = col_contains("nombre local") or 1
    city_col = col_contains("ciudad") or 4
    zone_col = col_contains("zona")
    promoter_col = col_contains("promotor")

    date_cols = []
    for idx, val in enumerate(header):
        if isinstance(val, (pd.Timestamp, datetime)):
            date_cols.append((idx, pd.Timestamp(val).normalize()))
        else:
            txt = _clean_text(val)
            parsed = pd.to_datetime(txt, errors="coerce", dayfirst=True)
            if not pd.isna(parsed) and parsed.year >= 2024:
                date_cols.append((idx, pd.Timestamp(parsed).normalize()))

    records = []
    for _, row in data.iterrows():
        store = _clean_text(row.iloc[store_col] if store_col is not None and store_col < len(row) else "")
        if not store:
            continue
        for col, dt in date_cols:
            marker = _clean_text(row.iloc[col] if col < len(row) else "")
            if marker:
                records.append({
                    "fecha": dt,
                    "mes": dt.strftime("%Y-%m"),
                    "tienda": store,
                    "cod_local": _clean_text(row.iloc[code_col] if code_col is not None and code_col < len(row) else ""),
                    "ciudad": _clean_text(row.iloc[city_col] if city_col is not None and city_col < len(row) else ""),
                    "zona": _clean_text(row.iloc[zone_col] if zone_col is not None and zone_col < len(row) else ""),
                    "promotor": _clean_text(row.iloc[promoter_col] if promoter_col is not None and promoter_col < len(row) else ""),
                    "marca_activacion": marker,
                })
    return pd.DataFrame(records)


def enrich_with_activations(sales: pd.DataFrame, activations: Optional[pd.DataFrame]) -> pd.DataFrame:
    sales = sales.copy()
    sales["tienda_key"] = sales["tienda"].str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
    sales["fecha_key"] = pd.to_datetime(sales["fecha"]).dt.normalize()
    sales["activacion"] = "No"
    if activations is not None and not activations.empty:
        act = activations.copy()
        act["tienda_key"] = act["tienda"].str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
        act["fecha_key"] = pd.to_datetime(act["fecha"]).dt.normalize()
        keys = act[["tienda_key", "fecha_key"]].drop_duplicates()
        sales = sales.merge(keys.assign(_act="Sí"), on=["tienda_key", "fecha_key"], how="left")
        sales["activacion"] = np.where(sales["_act"].eq("Sí"), "Sí", "No")
        sales = sales.drop(columns=["_act"])
    return sales
