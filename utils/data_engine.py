from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Any

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

WEEKDAY_ES = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}


@dataclass
class FileIssue:
    archivo: str
    tipo: str
    estado: str
    detalle: str


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    return re.sub(r"\s+", " ", text)


def norm_key(value: Any) -> str:
    text = clean_text(value).upper()
    text = text.replace("Ñ", "N")
    return re.sub(r"[^A-Z0-9]", "", text)


def file_name(file: Any) -> str:
    return getattr(file, "name", str(file))


def parse_month_year_from_filename(name: str) -> tuple[int | None, int | None]:
    lower = name.lower()
    match = re.search(r"(?:^|[^0-9])(0?[1-9]|1[0-2])[._\-\s]+(20\d{2})(?:[^0-9]|$)", lower)
    if match:
        return int(match.group(2)), int(match.group(1))

    for token, month in MONTHS_ES.items():
        match = re.search(rf"\b{token}\w*\b.*?(20\d{{2}})", lower)
        if match:
            return int(match.group(1)), month
    return None, None


def parse_month_year_from_cells(raw: pd.DataFrame) -> tuple[int | None, int | None]:
    scan = raw.iloc[:20, :12].copy()
    tokens = []
    for value in scan.to_numpy().ravel():
        text = clean_text(value).lower()
        if text:
            tokens.append(text)
    joined = " | ".join(tokens)

    # Patterns such as "Mes Año | may 2026" or "junio 2026"
    for token, month in MONTHS_ES.items():
        match = re.search(rf"\b{token}\w*\b\s+(20\d{{2}})", joined)
        if match:
            return int(match.group(1)), month

    # Adjacent cells may contain label/value pairs.
    for r in range(min(20, len(raw))):
        row = [clean_text(x).lower() for x in raw.iloc[r, :12].tolist()]
        for i, val in enumerate(row):
            if "mes" in val and i + 1 < len(row):
                nxt = row[i + 1]
                for token, month in MONTHS_ES.items():
                    if token in nxt:
                        y = re.search(r"20\d{2}", nxt)
                        return int(y.group(0)) if y else None, month
    return None, None


def read_raw_excel(file: Any) -> pd.DataFrame:
    xls = pd.ExcelFile(file)
    # Use first visible sheet. Autoplanet files usually use one sheet.
    return pd.read_excel(xls, sheet_name=xls.sheet_names[0], header=None)


def find_sellout_header_row(raw: pd.DataFrame) -> int:
    for idx in range(min(40, len(raw))):
        vals = [clean_text(v).lower() for v in raw.iloc[idx].tolist()]
        joined = " | ".join(vals)
        if "nombre 1" in joined and "texto flejera" in joined:
            return idx
        if "material sap" in joined and "texto flejera" in joined:
            return idx
    raise ValueError("No encontré la fila de encabezados del Sell Out Autoplanet.")


def header_column_index(header: list[Any], aliases: list[str]) -> int | None:
    aliases_norm = [a.lower() for a in aliases]
    for idx, value in enumerate(header):
        text = clean_text(value).lower()
        if any(a in text for a in aliases_norm):
            return idx
    return None


def parse_day(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not re.fullmatch(r"\d{1,2}(\.0)?", value):
            return None
    try:
        day = int(float(value))
    except Exception:
        return None
    return day if 1 <= day <= 31 else None


def detect_day_blocks(raw: pd.DataFrame, header_row: int, product_col: int) -> tuple[dict[int, int], dict[int, int]]:
    """Return dicts {column_index: day} for unit and sales blocks.

    The row above the header normally contains block labels such as
    SELL OUT UNIDADES and SELL OUT $. If this row is missing, the function
    falls back to identifying the two repeated sequences of day columns.
    """
    header = raw.iloc[header_row].tolist()
    marker_row = raw.iloc[header_row - 1].tolist() if header_row > 0 else [None] * len(header)

    unit_start = None
    sales_start = None
    for idx, marker in enumerate(marker_row):
        text = clean_text(marker).lower()
        if not text:
            continue
        if ("unidad" in text or "u´" in text or "s.o. unidades" in text) and idx > product_col and unit_start is None:
            unit_start = idx
        if ("$" in text or "venta" in text or "monto" in text) and idx > product_col and sales_start is None:
            sales_start = idx

    # Stop before totals at the end.
    last_daily_candidate = len(header)
    for idx in range(len(header) - 1, product_col, -1):
        text = clean_text(marker_row[idx]).lower()
        if "s.o" in text or "sell out" in text:
            last_daily_candidate = idx
    if last_daily_candidate <= product_col:
        last_daily_candidate = len(header)

    if unit_start is not None and sales_start is not None:
        unit_cols = {
            idx: day for idx in range(unit_start, min(sales_start, len(header)))
            if (day := parse_day(header[idx])) is not None
        }
        sales_cols = {
            idx: day for idx in range(sales_start, min(last_daily_candidate, len(header)))
            if (day := parse_day(header[idx])) is not None
        }
        if unit_cols and sales_cols:
            return unit_cols, sales_cols

    # Fallback: split all day columns after product into first and second repeated sequence.
    day_cols = [(idx, parse_day(value)) for idx, value in enumerate(header) if idx > product_col and parse_day(value) is not None]
    if not day_cols:
        return {}, {}
    split_at = None
    seen = set()
    for pos, (_, day) in enumerate(day_cols):
        if day in seen:
            split_at = pos
            break
        seen.add(day)
    if split_at is None:
        return dict(day_cols), {}
    return dict(day_cols[:split_at]), dict(day_cols[split_at:])


def split_store(value: Any) -> tuple[str, str]:
    text = clean_text(value)
    match = re.match(r"^(AP\d{4})\s*[-–]\s*(.+)$", text, flags=re.IGNORECASE)
    if match:
        code = match.group(1).upper()
        name = clean_text(match.group(2)).title()
        return code, name
    match = re.search(r"\b(AP\d{4})\b", text, flags=re.IGNORECASE)
    code = match.group(1).upper() if match else ""
    return code, text


def read_sellout_file(file: Any) -> tuple[pd.DataFrame, dict[str, Any], list[FileIssue]]:
    source = file_name(file)
    issues: list[FileIssue] = []
    raw = read_raw_excel(file)
    header_row = find_sellout_header_row(raw)
    header = raw.iloc[header_row].tolist()

    year, month = parse_month_year_from_filename(source)
    if not (year and month):
        cell_year, cell_month = parse_month_year_from_cells(raw)
        year = year or cell_year
        month = month or cell_month
    if not (year and month):
        raise ValueError(f"No pude detectar mes/año en {source}. Usa un nombre tipo Sell out 06.2026.xlsx.")

    store_col = header_column_index(header, ["nombre 1", "tienda", "local"])
    category_col = header_column_index(header, ["subagrupacion", "subagrupación", "categoria", "categoría"])
    sku_col = header_column_index(header, ["material sap"])
    product_col = header_column_index(header, ["texto flejera", "producto"])

    missing = []
    for label, col in {"tienda": store_col, "categoría": category_col, "sku": sku_col, "producto": product_col}.items():
        if col is None:
            missing.append(label)
    if missing:
        raise ValueError(f"Faltan columnas clave en {source}: {', '.join(missing)}.")

    unit_cols, sales_cols = detect_day_blocks(raw, header_row, int(product_col))
    if not unit_cols:
        raise ValueError(f"No encontré columnas diarias de unidades en {source}.")
    if not sales_cols:
        issues.append(FileIssue(source, "Sell Out", "Advertencia", "No se detectaron columnas diarias de venta $, se dejarán ventas en cero."))

    data = raw.iloc[header_row + 1 :].dropna(how="all").copy()
    records: list[dict[str, Any]] = []
    skipped_rows = 0

    for _, row in data.iterrows():
        store_raw = clean_text(row.iloc[store_col]) if store_col < len(row) else ""
        product = clean_text(row.iloc[product_col]) if product_col < len(row) else ""
        if not store_raw or not product:
            skipped_rows += 1
            continue
        if store_raw.lower().startswith("total") or product.lower().startswith("total"):
            skipped_rows += 1
            continue

        store_code, store_name = split_store(store_raw)
        category = clean_text(row.iloc[category_col]) if category_col < len(row) else "Sin categoría"
        sku_raw = row.iloc[sku_col] if sku_col < len(row) else ""
        sku = clean_text(sku_raw)

        for unit_col, day in unit_cols.items():
            try:
                dt = pd.Timestamp(year=int(year), month=int(month), day=int(day))
            except Exception:
                continue
            units = pd.to_numeric(row.iloc[unit_col] if unit_col < len(row) else np.nan, errors="coerce")
            sale_col = next((col for col, sale_day in sales_cols.items() if sale_day == day), None)
            sales = pd.to_numeric(row.iloc[sale_col] if sale_col is not None and sale_col < len(row) else np.nan, errors="coerce")
            units = 0.0 if pd.isna(units) else float(units)
            sales = 0.0 if pd.isna(sales) else float(sales)
            if units == 0 and sales == 0:
                continue
            records.append({
                "fecha": dt,
                "anio": int(year),
                "mes_num": int(month),
                "mes": dt.strftime("%Y-%m"),
                "dia": int(day),
                "dia_semana": WEEKDAY_ES[dt.weekday()],
                "tienda_codigo": store_code,
                "tienda": store_name,
                "tienda_original": store_raw,
                "categoria": category or "Sin categoría",
                "sku": sku,
                "producto": product,
                "unidades": units,
                "venta": sales,
                "archivo_origen": source,
            })

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError(f"No se generaron registros de sell out desde {source}.")

    # Stable column order.
    ordered = [
        "fecha", "anio", "mes_num", "mes", "dia", "dia_semana",
        "tienda_codigo", "tienda", "tienda_original", "categoria", "sku", "producto",
        "unidades", "venta", "archivo_origen",
    ]
    df = df[ordered]

    report = {
        "archivo": source,
        "tipo": "Sell Out",
        "estado": "OK",
        "filas_excel": int(len(data)),
        "registros_generados": int(len(df)),
        "mes": f"{year}-{month:02d}",
        "header_row_excel": int(header_row + 1),
        "dias_unidades": sorted(set(unit_cols.values())),
        "dias_venta": sorted(set(sales_cols.values())),
        "tiendas": int(df["tienda_codigo"].replace("", np.nan).nunique()),
        "skus": int(df["sku"].replace("", np.nan).nunique()),
        "venta_total": float(df["venta"].sum()),
        "unidades_total": float(df["unidades"].sum()),
        "filas_omitidas": int(skipped_rows),
    }
    return df, report, issues


def read_sellout_files(files: Iterable[Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    reports: list[dict[str, Any]] = []
    issues: list[FileIssue] = []
    for file in files:
        try:
            df, report, file_issues = read_sellout_file(file)
            frames.append(df)
            reports.append(report)
            issues.extend(file_issues)
        except Exception as exc:
            issues.append(FileIssue(file_name(file), "Sell Out", "Error", str(exc)))
    if not frames:
        return pd.DataFrame(), pd.DataFrame(reports), pd.DataFrame([i.__dict__ for i in issues])
    sales = pd.concat(frames, ignore_index=True)
    sales = sales.sort_values(["fecha", "tienda_codigo", "sku"]).reset_index(drop=True)
    return sales, pd.DataFrame(reports), pd.DataFrame([i.__dict__ for i in issues])


def find_promoters_header_row(raw: pd.DataFrame) -> int:
    for idx in range(min(15, len(raw))):
        joined = " | ".join(clean_text(x).lower() for x in raw.iloc[idx].tolist())
        if "tienda" in joined and "nombre tienda" in joined and "comuna" in joined:
            return idx
    raise ValueError("No encontré la fila de encabezados del archivo de promotores.")


def read_promoters_file(file: Any) -> tuple[pd.DataFrame, dict[str, Any], list[FileIssue]]:
    source = file_name(file)
    issues: list[FileIssue] = []
    raw = read_raw_excel(file)
    header_row = find_promoters_header_row(raw)
    header = raw.iloc[header_row].tolist()
    data = raw.iloc[header_row + 1 :].dropna(how="all").copy()

    def find_col(aliases: list[str]) -> int | None:
        return header_column_index(header, aliases)

    code_col = find_col(["tienda"])
    local_col = find_col(["local"])
    store_col = find_col(["nombre tienda"])
    address_col = find_col(["direccion", "dirección"])
    comuna_col = find_col(["comuna"])
    zona_col = find_col(["zona"])
    tipo_evento_col = find_col(["tipo de evento"])
    detalle_col = find_col(["detalle"])
    horario_col = find_col(["horario"])
    marca_col = find_col(["marca"])

    if code_col is None or store_col is None:
        raise ValueError("El archivo de promotores debe tener columnas TIENDA y NOMBRE TIENDA.")

    date_cols: list[tuple[int, pd.Timestamp]] = []
    for idx, value in enumerate(header):
        if isinstance(value, (datetime, pd.Timestamp)):
            dt = pd.Timestamp(value).normalize()
        else:
            dt = pd.to_datetime(clean_text(value), errors="coerce", dayfirst=True)
            if not pd.isna(dt):
                dt = pd.Timestamp(dt).normalize()
        if not pd.isna(dt) and 2024 <= dt.year <= 2035:
            date_cols.append((idx, dt))

    records: list[dict[str, Any]] = []
    for _, row in data.iterrows():
        store_code = clean_text(row.iloc[code_col]) if code_col < len(row) else ""
        store_code = store_code.upper()
        store_name = clean_text(row.iloc[store_col]) if store_col < len(row) else ""
        local = clean_text(row.iloc[local_col]) if local_col is not None and local_col < len(row) else ""
        comuna = clean_text(row.iloc[comuna_col]) if comuna_col is not None and comuna_col < len(row) else ""
        zona = clean_text(row.iloc[zona_col]) if zona_col is not None and zona_col < len(row) else ""
        direccion = clean_text(row.iloc[address_col]) if address_col is not None and address_col < len(row) else ""
        tipo_evento = clean_text(row.iloc[tipo_evento_col]) if tipo_evento_col is not None and tipo_evento_col < len(row) else ""
        detalle = clean_text(row.iloc[detalle_col]) if detalle_col is not None and detalle_col < len(row) else ""
        horario = clean_text(row.iloc[horario_col]) if horario_col is not None and horario_col < len(row) else ""
        marca = clean_text(row.iloc[marca_col]) if marca_col is not None and marca_col < len(row) else ""

        if not store_code and not store_name:
            continue
        for col, dt in date_cols:
            marker = clean_text(row.iloc[col]) if col < len(row) else ""
            if not marker:
                continue
            records.append({
                "fecha": dt,
                "anio": int(dt.year),
                "mes_num": int(dt.month),
                "mes": dt.strftime("%Y-%m"),
                "dia": int(dt.day),
                "dia_semana": WEEKDAY_ES[dt.weekday()],
                "tienda_codigo": store_code,
                "tienda_promotores": store_name,
                "local": local,
                "comuna": comuna,
                "zona": zona,
                "direccion": direccion,
                "tipo_evento": tipo_evento,
                "marca_archivo": marca,
                "detalle_archivo": detalle,
                "horario_archivo": horario,
                "activacion_codigo": marker.upper(),
                "activacion_nombre": classify_activation(marker),
                "archivo_origen": source,
            })
    activations = pd.DataFrame(records)
    if activations.empty:
        issues.append(FileIssue(source, "Promotores", "Advertencia", "No se encontraron activaciones con marcas en fechas."))
    else:
        activations = activations.sort_values(["fecha", "tienda_codigo"]).reset_index(drop=True)

    report = {
        "archivo": source,
        "tipo": "Promotores",
        "estado": "OK",
        "filas_excel": int(len(data)),
        "registros_generados": int(len(activations)),
        "header_row_excel": int(header_row + 1),
        "fecha_min": activations["fecha"].min().strftime("%Y-%m-%d") if not activations.empty else "",
        "fecha_max": activations["fecha"].max().strftime("%Y-%m-%d") if not activations.empty else "",
        "tiendas": int(activations["tienda_codigo"].replace("", np.nan).nunique()) if not activations.empty else 0,
    }
    return activations, report, issues


def classify_activation(marker: Any) -> str:
    code = clean_text(marker).upper()
    if code == "MS":
        return "Activación Magic Shine"
    if code == "VC":
        return "Visita comercial"
    if code in {"AM", "PM"}:
        return f"Media jornada {code}"
    if code in {"G", "VCG"}:
        return "Gestión / visita"
    if "CERR" in code:
        return "Tienda cerrada"
    return code or "Sin clasificar"


def enrich_sales_with_activations(sales: pd.DataFrame, activations: pd.DataFrame | None) -> pd.DataFrame:
    if sales.empty:
        return sales.copy()
    out = sales.copy()
    out["fecha"] = pd.to_datetime(out["fecha"]).dt.normalize()
    out["activacion"] = "No"
    out["activacion_codigo"] = ""
    out["activacion_nombre"] = ""
    out["comuna"] = ""
    out["zona"] = ""

    if activations is None or activations.empty:
        return out

    act = activations.copy()
    act["fecha"] = pd.to_datetime(act["fecha"]).dt.normalize()

    # Aggregate per store/date in case multiple activity types exist.
    agg = (
        act.groupby(["tienda_codigo", "fecha"], as_index=False)
        .agg(
            activacion_codigo=("activacion_codigo", lambda x: ", ".join(sorted(set(filter(None, x))))),
            activacion_nombre=("activacion_nombre", lambda x: ", ".join(sorted(set(filter(None, x))))),
            comuna=("comuna", "first"),
            zona=("zona", "first"),
        )
    )
    out = out.merge(agg, on=["tienda_codigo", "fecha"], how="left", suffixes=("", "_act"))
    out["activacion_codigo"] = out["activacion_codigo_act"].fillna("")
    out["activacion_nombre"] = out["activacion_nombre_act"].fillna("")
    out["comuna"] = out["comuna_act"].fillna("")
    out["zona"] = out["zona_act"].fillna("")
    out["activacion"] = np.where(out["activacion_codigo"].ne(""), "Sí", "No")
    out = out.drop(columns=[c for c in out.columns if c.endswith("_act")])
    return out


def build_master_dataset(sellout_files: Iterable[Any], promoter_file: Any | None = None) -> dict[str, pd.DataFrame]:
    sales, sellout_report, sellout_issues = read_sellout_files(sellout_files)

    activations = pd.DataFrame()
    promoter_report = pd.DataFrame()
    promoter_issues = pd.DataFrame()
    if promoter_file is not None:
        try:
            activations, report, issues = read_promoters_file(promoter_file)
            promoter_report = pd.DataFrame([report])
            promoter_issues = pd.DataFrame([i.__dict__ for i in issues])
        except Exception as exc:
            promoter_issues = pd.DataFrame([FileIssue(file_name(promoter_file), "Promotores", "Error", str(exc)).__dict__])

    master = enrich_sales_with_activations(sales, activations)
    quality = pd.concat([sellout_report, promoter_report], ignore_index=True) if not sellout_report.empty or not promoter_report.empty else pd.DataFrame()
    issues = pd.concat([sellout_issues, promoter_issues], ignore_index=True) if not sellout_issues.empty or not promoter_issues.empty else pd.DataFrame(columns=["archivo", "tipo", "estado", "detalle"])

    return {
        "ventas": sales,
        "activaciones": activations,
        "master": master,
        "calidad": quality,
        "issues": issues,
    }


def kpi_summary(df: pd.DataFrame) -> dict[str, float | int]:
    if df is None or df.empty:
        return {"venta": 0, "unidades": 0, "tiendas": 0, "skus": 0, "dias": 0, "ticket": 0}
    venta = float(df["venta"].sum())
    unidades = float(df["unidades"].sum())
    return {
        "venta": venta,
        "unidades": unidades,
        "tiendas": int(df["tienda_codigo"].replace("", np.nan).nunique()),
        "skus": int(df["sku"].replace("", np.nan).nunique()),
        "dias": int(df["fecha"].nunique()),
        "ticket": float(venta / unidades) if unidades else 0,
    }
