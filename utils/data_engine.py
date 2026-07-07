from __future__ import annotations

import re
import unicodedata
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

# Control de calidad solicitado por Magic Shine.
# Solo deben entrar filas de tiendas Autoplanet cuyo campo "Nombre 1" comienza con AP.
# Los totales se recalculan desde las filas filtradas, nunca desde la fila "Total general".
SELL_OUT_CONTROL_TOTALS = {
    "2026-05": {"unidades_total": 4780.0, "venta_total": 10576950.0},
    "2026-06": {"unidades_total": 4715.0, "venta_total": 10604240.0},
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
    # Remove accents while keeping Ñ as N for robust matching: Sebastián -> SEBASTIAN.
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
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

    data_all = raw.iloc[header_row + 1 :].dropna(how="all").copy()

    # Filtro crítico: conservar únicamente tiendas reales Autoplanet.
    # Campo fuente: Nombre 1. Debe comenzar con AP (ej.: AP0001-La Florida).
    # Excluye canales logísticos, externos y subtotales como Total general.
    store_series_all = data_all.iloc[:, store_col].apply(clean_text) if store_col is not None else pd.Series([], dtype="object")
    ap_mask = store_series_all.astype(str).str.strip().str.upper().str.startswith("AP")
    excluded_rows_df = data_all.loc[~ap_mask].copy()
    excluded_store_values = (
        store_series_all.loc[~ap_mask]
        .replace("", np.nan)
        .dropna()
        .drop_duplicates()
        .astype(str)
        .tolist()
    )
    data = data_all.loc[ap_mask].copy()

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

    period = f"{year}-{month:02d}"
    venta_total = float(df["venta"].sum())
    unidades_total = float(df["unidades"].sum())
    control = SELL_OUT_CONTROL_TOTALS.get(period, {})
    control_unidades = control.get("unidades_total")
    control_venta = control.get("venta_total")
    control_ok = "No aplica"
    if control:
        unidades_ok = abs(unidades_total - float(control_unidades)) < 0.01
        venta_ok = abs(venta_total - float(control_venta)) < 0.01
        control_ok = "OK" if unidades_ok and venta_ok else "Revisar"
        if control_ok != "OK":
            issues.append(FileIssue(
                source,
                "Sell Out",
                "Advertencia",
                f"Control {period} no calza tras filtro AP: unidades {unidades_total:,.0f} vs {float(control_unidades):,.0f}; venta ${venta_total:,.0f} vs ${float(control_venta):,.0f}.",
            ))

    report = {
        "archivo": source,
        "tipo": "Sell Out",
        "estado": "OK",
        "filas_excel": int(len(data_all)),
        "filas_tienda_ap": int(len(data)),
        "filas_excluidas_no_ap": int(len(excluded_rows_df)),
        "registros_generados": int(len(df)),
        "mes": period,
        "header_row_excel": int(header_row + 1),
        "dias_unidades": sorted(set(unit_cols.values())),
        "dias_venta": sorted(set(sales_cols.values())),
        "tiendas": int(df["tienda_codigo"].replace("", np.nan).nunique()),
        "skus": int(df["sku"].replace("", np.nan).nunique()),
        "venta_total": venta_total,
        "unidades_total": unidades_total,
        "control_unidades": control_unidades if control_unidades is not None else "",
        "control_venta": control_venta if control_venta is not None else "",
        "control_calidad": control_ok,
        "filas_omitidas": int(skipped_rows),
        "valores_excluidos_nombre_1": ", ".join(excluded_store_values[:25]) + (" …" if len(excluded_store_values) > 25 else ""),
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



def truthy(value: Any, default: bool = False) -> bool:
    text = norm_key(value)
    if not text:
        return default
    return text in {"SI", "S", "YES", "Y", "TRUE", "VERDADERO", "1", "X"}


def normalize_activity_code(value: Any) -> str:
    text = clean_text(value).upper()
    text = text.replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
    return re.sub(r"[^A-Z0-9]", "", text)


def infer_activity_fields(code: str, detalle: str = "", horario: str = "", ejecutor: str = "") -> dict[str, str]:
    code_n = normalize_activity_code(code)
    detail_n = norm_key(detalle)
    ejecutor_clean = clean_text(ejecutor)
    horario_clean = clean_text(horario)

    if "CERR" in code_n or "CERR" in detail_n:
        tipo = "No operativa"
        estado = "Cerrada"
    elif "CANCEL" in code_n or "CANCEL" in detail_n:
        tipo = "Activación"
        estado = "Cancelada"
    elif "VISITA" in detail_n or code_n in {"VC", "VCG", "G"}:
        tipo = "Visita con incentivo" if ("GALLET" in detail_n or code_n in {"VCG", "G"}) else "Visita"
        estado = "Ejecutada"
    elif "ACTIVACION" in detail_n or code_n in {"MS", "MSH", "MSHG", "AM", "PM"}:
        tipo = "Activación con incentivo" if "GALLET" in detail_n or code_n == "MSHG" else "Activación"
        estado = "Ejecutada"
    else:
        tipo = detalle or code_n or "Sin clasificar"
        estado = "Ejecutada"

    if "MEDIO" in detail_n or "MEDIODIA" in detail_n or "14" in horario_clean or code_n in {"MSH", "MSHG", "AM", "PM"}:
        jornada = "Medio día"
    elif "FULL" in detail_n or "10" in horario_clean or code_n == "MS":
        jornada = "Full día"
    else:
        jornada = ""

    ejecutor_n = norm_key(ejecutor_clean)
    cuenta_activacion = "Sí" if tipo.startswith("Activación") and estado == "Ejecutada" else "No"
    kpi_sebastian = "Sí" if "SEBASTIAN" in ejecutor_n and estado == "Ejecutada" and tipo != "No operativa" else "No"
    kpi_agencia = "Sí" if "AGENCIA" in ejecutor_n and cuenta_activacion == "Sí" else "No"
    actividad_valida = "Sí" if estado == "Ejecutada" and tipo != "No operativa" else "No"

    return {
        "codigo": code_n,
        "marca": "MagicShine" if not clean_text(detalle) and code_n in {"MS", "MSC", "MSH", "MSHG", "VC", "VCG"} else "",
        "detalle": clean_text(detalle) or classify_activation(code_n),
        "horario": horario_clean,
        "ejecutor": ejecutor_clean,
        "tipo_actividad": tipo,
        "estado_actividad": estado,
        "cuenta_activacion": cuenta_activacion,
        "kpi_sebastian": kpi_sebastian,
        "kpi_agencia": kpi_agencia,
        "jornada": jornada,
        "actividad_valida": actividad_valida,
    }


def read_activity_dictionary(xls: pd.ExcelFile, source: str) -> tuple[dict[str, dict[str, str]], pd.DataFrame, list[FileIssue]]:
    """Read activity dictionary from Diccionario/Diccionario_Actividades sheet.

    The dictionary makes the dashboard independent from cell colours and allows reliable
    attribution of Agency vs Sebastián activities.
    """
    issues: list[FileIssue] = []
    default_rows = [
        {"codigo": "MS", "marca": "MagicShine", "detalle": "Activación full día", "horario": "10:00 - 18:00", "ejecutor": "Agencia"},
        {"codigo": "MSC", "marca": "MagicShine", "detalle": "Activación full día programada y cancelada", "horario": "10:00 - 18:00", "ejecutor": "Agencia"},
        {"codigo": "MSH", "marca": "MagicShine", "detalle": "Activación de mediodía", "horario": "14:30 - 18:30", "ejecutor": "Sebastián"},
        {"codigo": "MSHG", "marca": "MagicShine", "detalle": "Activación de mediodía + galletas de regalo", "horario": "14:30 - 18:30", "ejecutor": "Sebastián"},
        {"codigo": "VC", "marca": "MagicShine", "detalle": "Visita comercial", "horario": "", "ejecutor": "Sebastián"},
        {"codigo": "VCG", "marca": "MagicShine", "detalle": "Visita comercial + galletas de regalo", "horario": "", "ejecutor": "Sebastián"},
        {"codigo": "CERRADA", "marca": "", "detalle": "Tienda cerrada", "horario": "", "ejecutor": ""},
    ]

    sheet_name = None
    for candidate in xls.sheet_names:
        if norm_key(candidate) in {"DICCIONARIO", "DICCIONARIOACTIVIDADES", "DICCIONARIODEACTIVIDADES"}:
            sheet_name = candidate
            break

    rows: list[dict[str, str]] = []
    if sheet_name is None:
        issues.append(FileIssue(source, "Diccionario", "Advertencia", "No se encontró hoja Diccionario. Se usaron reglas internas de respaldo."))
        rows = default_rows
    else:
        raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        header_row = None
        for idx in range(min(20, len(raw))):
            joined = " | ".join(clean_text(x).lower() for x in raw.iloc[idx].tolist())
            if "abreviatura" in joined and "detalle" in joined and "ejecutor" in joined:
                header_row = idx
                break
        if header_row is None:
            issues.append(FileIssue(source, "Diccionario", "Advertencia", f"La hoja {sheet_name} no tiene encabezado reconocible. Se usaron reglas internas de respaldo."))
            rows = default_rows
        else:
            header = [norm_key(x) for x in raw.iloc[header_row].tolist()]
            def col(names: list[str]) -> int | None:
                targets = {norm_key(n) for n in names}
                for i, h in enumerate(header):
                    if h in targets:
                        return i
                return None
            code_col = col(["Abreviatura", "Codigo", "Código", "Code"])
            marca_col = col(["Marca"])
            detalle_col = col(["Detalle", "Descripcion", "Descripción"])
            horario_col = col(["Horario"])
            ejecutor_col = col(["Ejecutor", "Responsable", "Promotor"])
            tipo_col = col(["Tipo Actividad", "Tipo"])
            estado_col = col(["Estado"])
            cuenta_col = col(["Cuenta Activacion", "Cuenta Activación"])
            kpi_seb_col = col(["KPI Sebastian", "KPI Sebastián", "Cuenta KPI Sebastian", "Cuenta KPI Sebastián"])
            kpi_ag_col = col(["KPI Agencia", "Cuenta KPI Agencia"])
            jornada_col = col(["Jornada"])

            if code_col is None:
                issues.append(FileIssue(source, "Diccionario", "Advertencia", "La hoja Diccionario no tiene columna Abreviatura. Se usaron reglas internas de respaldo."))
                rows = default_rows
            else:
                blank_streak = 0
                for _, row in raw.iloc[header_row + 1:].iterrows():
                    code = normalize_activity_code(row.iloc[code_col] if code_col < len(row) else "")
                    if not code:
                        blank_streak += 1
                        if blank_streak >= 3 and rows:
                            break
                        continue
                    blank_streak = 0
                    detalle = clean_text(row.iloc[detalle_col]) if detalle_col is not None and detalle_col < len(row) else ""
                    horario = clean_text(row.iloc[horario_col]) if horario_col is not None and horario_col < len(row) else ""
                    ejecutor = clean_text(row.iloc[ejecutor_col]) if ejecutor_col is not None and ejecutor_col < len(row) else ""
                    inferred = infer_activity_fields(code, detalle, horario, ejecutor)
                    rec = {
                        **inferred,
                        "codigo": code,
                        "marca": clean_text(row.iloc[marca_col]) if marca_col is not None and marca_col < len(row) else inferred.get("marca", ""),
                        "detalle": detalle or inferred["detalle"],
                        "horario": horario or inferred["horario"],
                        "ejecutor": ejecutor or inferred["ejecutor"],
                    }
                    if tipo_col is not None and tipo_col < len(row) and clean_text(row.iloc[tipo_col]):
                        rec["tipo_actividad"] = clean_text(row.iloc[tipo_col])
                    if estado_col is not None and estado_col < len(row) and clean_text(row.iloc[estado_col]):
                        rec["estado_actividad"] = clean_text(row.iloc[estado_col])
                    if cuenta_col is not None and cuenta_col < len(row):
                        rec["cuenta_activacion"] = "Sí" if truthy(row.iloc[cuenta_col], rec["cuenta_activacion"] == "Sí") else "No"
                    if kpi_seb_col is not None and kpi_seb_col < len(row):
                        rec["kpi_sebastian"] = "Sí" if truthy(row.iloc[kpi_seb_col], rec["kpi_sebastian"] == "Sí") else "No"
                    if kpi_ag_col is not None and kpi_ag_col < len(row):
                        rec["kpi_agencia"] = "Sí" if truthy(row.iloc[kpi_ag_col], rec["kpi_agencia"] == "Sí") else "No"
                    if jornada_col is not None and jornada_col < len(row) and clean_text(row.iloc[jornada_col]):
                        rec["jornada"] = clean_text(row.iloc[jornada_col])
                    rec["actividad_valida"] = "Sí" if rec.get("estado_actividad") == "Ejecutada" and rec.get("tipo_actividad") != "No operativa" else "No"
                    rows.append(rec)

    mapping: dict[str, dict[str, str]] = {}
    clean_rows: list[dict[str, str]] = []
    for row in rows:
        code = normalize_activity_code(row.get("codigo", ""))
        if not code:
            continue
        row = {**infer_activity_fields(code, row.get("detalle", ""), row.get("horario", ""), row.get("ejecutor", "")), **row, "codigo": code}
        if code in mapping:
            issues.append(FileIssue(source, "Diccionario", "Advertencia", f"Código duplicado en diccionario: {code}. Se usó la primera definición."))
            continue
        mapping[code] = row
        clean_rows.append(row)

    dictionary_df = pd.DataFrame(clean_rows)
    return mapping, dictionary_df, issues


def activity_from_code(code: Any, dictionary: dict[str, dict[str, str]] | None = None) -> dict[str, str]:
    code_n = normalize_activity_code(code)
    if dictionary and code_n in dictionary:
        return dictionary[code_n].copy()
    return infer_activity_fields(code_n)

def find_promoters_header_row(raw: pd.DataFrame) -> int:
    for idx in range(min(15, len(raw))):
        joined = " | ".join(clean_text(x).lower() for x in raw.iloc[idx].tolist())
        if "tienda" in joined and "nombre tienda" in joined and "comuna" in joined:
            return idx
    raise ValueError("No encontré la fila de encabezados del archivo de promotores.")


def read_promoters_file(file: Any) -> tuple[pd.DataFrame, dict[str, Any], list[FileIssue]]:
    source = file_name(file)
    issues: list[FileIssue] = []
    xls = pd.ExcelFile(file)
    sheet_name = next((s for s in xls.sheet_names if norm_key(s) == "CONSOLIDADO"), xls.sheet_names[0])
    raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)
    activity_dict, activity_dict_df, dict_issues = read_activity_dictionary(xls, source)
    issues.extend(dict_issues)
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
            activity = activity_from_code(marker, activity_dict)
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
                "activacion_codigo": activity.get("codigo", normalize_activity_code(marker)),
                "activacion_nombre": activity.get("detalle", classify_activation(marker)),
                "tipo_actividad": activity.get("tipo_actividad", "Sin clasificar"),
                "estado_actividad": activity.get("estado_actividad", "Ejecutada"),
                "ejecutor": activity.get("ejecutor", ""),
                "horario": activity.get("horario", horario),
                "jornada": activity.get("jornada", ""),
                "cuenta_activacion": activity.get("cuenta_activacion", "No"),
                "kpi_sebastian": activity.get("kpi_sebastian", "No"),
                "kpi_agencia": activity.get("kpi_agencia", "No"),
                "actividad_valida": activity.get("actividad_valida", "Sí"),
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
        "diccionario_actividades": int(len(activity_dict_df)) if activity_dict_df is not None else 0,
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
    out["actividad_terreno"] = "No"
    out["activacion_codigo"] = ""
    out["activacion_nombre"] = ""
    out["tipo_actividad"] = ""
    out["estado_actividad"] = ""
    out["ejecutor"] = ""
    out["cuenta_activacion"] = "No"
    out["kpi_sebastian"] = "No"
    out["kpi_agencia"] = "No"
    out["actividad_valida"] = "No"
    out["comuna"] = ""
    out["zona"] = ""

    if activations is None or activations.empty:
        return out

    act = activations.copy()
    act["fecha"] = pd.to_datetime(act["fecha"]).dt.normalize()

    # Aggregate per store/date in case multiple activity types exist.
    def join_unique(values):
        return ", ".join(sorted(set(str(v) for v in values if clean_text(v))))

    def any_yes(values):
        return "Sí" if any(clean_text(v).lower() in {"sí", "si", "yes", "true", "1"} for v in values) else "No"

    agg = (
        act.groupby(["tienda_codigo", "fecha"], as_index=False)
        .agg(
            activacion_codigo=("activacion_codigo", join_unique),
            activacion_nombre=("activacion_nombre", join_unique),
            tipo_actividad=("tipo_actividad", join_unique),
            estado_actividad=("estado_actividad", join_unique),
            ejecutor=("ejecutor", join_unique),
            cuenta_activacion=("cuenta_activacion", any_yes),
            kpi_sebastian=("kpi_sebastian", any_yes),
            kpi_agencia=("kpi_agencia", any_yes),
            actividad_valida=("actividad_valida", any_yes),
            comuna=("comuna", "first"),
            zona=("zona", "first"),
        )
    )
    out = out.merge(agg, on=["tienda_codigo", "fecha"], how="left", suffixes=("", "_act"))
    for col in ["activacion_codigo", "activacion_nombre", "tipo_actividad", "estado_actividad", "ejecutor", "cuenta_activacion", "kpi_sebastian", "kpi_agencia", "actividad_valida", "comuna", "zona"]:
        act_col = f"{col}_act"
        if act_col in out.columns:
            out[col] = out[act_col].fillna(out[col] if col in out.columns else "")
    out["activacion"] = np.where(out["cuenta_activacion"].eq("Sí"), "Sí", "No")
    out["actividad_terreno"] = np.where(out["actividad_valida"].eq("Sí"), "Sí", "No")
    out = out.drop(columns=[c for c in out.columns if c.endswith("_act")])
    return out



# -----------------------------
# Fichas de visita y contenido
# -----------------------------

def _read_sheet_with_detected_header(xls: pd.ExcelFile, sheet_name: str, required_terms: list[str], max_rows: int = 15) -> pd.DataFrame:
    raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)
    header_row = None
    targets = [norm_key(t) for t in required_terms]
    for idx in range(min(max_rows, len(raw))):
        row_keys = [norm_key(x) for x in raw.iloc[idx].tolist()]
        joined = "|".join(row_keys)
        if all(t in joined for t in targets):
            header_row = idx
            break
    if header_row is None:
        return pd.DataFrame()
    df = pd.read_excel(xls, sheet_name=sheet_name, header=header_row)
    df.columns = [clean_text(c) for c in df.columns]
    return df.dropna(how="all")


def _find_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    if df is None or df.empty:
        return None
    targets = [norm_key(a) for a in aliases]
    # Primero coincidencia exacta para evitar que "Tienda" tome "Cod Tienda".
    for col in df.columns:
        key = norm_key(col)
        if key in targets:
            return col
    # Luego coincidencia parcial para tolerar variaciones de encabezado.
    for col in df.columns:
        key = norm_key(col)
        if any(t and t in key for t in targets):
            return col
    return None


def _series_text(df: pd.DataFrame, col: str | None) -> pd.Series:
    if col is None or col not in df.columns:
        return pd.Series([""] * len(df), index=df.index, dtype="object")
    return df[col].apply(clean_text)


def _series_num(df: pd.DataFrame, col: str | None) -> pd.Series:
    if col is None or col not in df.columns:
        return pd.Series([0.0] * len(df), index=df.index, dtype="float")
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def _is_yes(value: Any) -> bool:
    return norm_key(value) in {"SI", "S", "YES", "Y", "TRUE", "VERDADERO", "1", "X"}


def _nonempty_count(row: pd.Series, cols: list[str]) -> int:
    count = 0
    for col in cols:
        if col in row.index and clean_text(row[col]):
            count += 1
    return count


def read_visits_file(file: Any | None) -> tuple[pd.DataFrame, dict[str, Any], list[FileIssue]]:
    """Lee la plantilla de visitas de Sebastián.

    Diseñada para la hoja "02. Base de Datos" de la plantilla actual, pero tolera
    cambios menores si mantiene columnas como Fecha, Cod Tienda y Tienda.
    """
    if file is None:
        return pd.DataFrame(), {}, []
    source = file_name(file)
    issues: list[FileIssue] = []
    xls = pd.ExcelFile(file)

    sheet_name = None
    for s in xls.sheet_names:
        key = norm_key(s)
        if "BASEDATOS" in key:
            sheet_name = s
            break
    if sheet_name is None:
        # fallback: first sheet with required headers
        for s in xls.sheet_names:
            candidate = _read_sheet_with_detected_header(xls, s, ["fecha", "tienda"], max_rows=20)
            if not candidate.empty:
                sheet_name = s
                df_raw = candidate
                break
        else:
            issues.append(FileIssue(source, "Ficha visitas", "Error", "No se encontró hoja Base de Datos ni encabezados Fecha/Tienda."))
            return pd.DataFrame(), {}, issues
    else:
        df_raw = _read_sheet_with_detected_header(xls, sheet_name, ["fecha", "tienda"], max_rows=20)
        if df_raw.empty:
            df_raw = pd.read_excel(xls, sheet_name=sheet_name)
            df_raw.columns = [clean_text(c) for c in df_raw.columns]
            df_raw = df_raw.dropna(how="all")

    if df_raw.empty:
        issues.append(FileIssue(source, "Ficha visitas", "Advertencia", "La hoja de visitas está vacía."))
        return pd.DataFrame(), {}, issues

    fecha_col = _find_column(df_raw, ["Fecha"])
    code_col = _find_column(df_raw, ["Cod Tienda", "Código Tienda", "Cod tienda", "Codigo Tienda"])
    tienda_col = _find_column(df_raw, ["Tienda"])
    comuna_col = _find_column(df_raw, ["Comuna"])
    jefe_col = _find_column(df_raw, ["Jefe de Tienda"])
    ejecutivo_col = _find_column(df_raw, ["Ejecutivo"])
    ventas_total_col = _find_column(df_raw, ["Ventas Total Tienda"])
    ventas_pasillo_col = _find_column(df_raw, ["Ventas Pasillo 5"])
    activaciones_col = _find_column(df_raw, ["Activaciones"])
    concursos_col = _find_column(df_raw, ["Concursos"])
    apoyo_col = _find_column(df_raw, ["Apoyo a Vendedores"])
    foto_pasillo_col = _find_column(df_raw, ["Link Foto Pasillo"])
    foto_exhibidor_col = _find_column(df_raw, ["Link Foto Exhibidor"])
    idea_col = _find_column(df_raw, ["Idea Jefe Tienda"])
    notas_col = _find_column(df_raw, ["Notas"])
    pendiente_col = _find_column(df_raw, ["¿Quedó Pendiente?", "Quedó Pendiente", "Quedo Pendiente"])
    detalle_pend_col = _find_column(df_raw, ["Detalle Pendiente"])
    vendedor_col = _find_column(df_raw, ["Vendedor Clave"])
    conoce_col = _find_column(df_raw, ["¿Conoce MagicShine?", "Conoce MagicShine"])
    reposicion_col = _find_column(df_raw, ["Días Reposición", "Dias Reposicion"])
    reposicion_det_col = _find_column(df_raw, ["Reposición Detalle", "Reposicion Detalle"])

    if fecha_col is None or tienda_col is None:
        issues.append(FileIssue(source, "Ficha visitas", "Error", "La ficha debe incluir al menos Fecha y Tienda."))
        return pd.DataFrame(), {}, issues

    out = pd.DataFrame()
    out["fecha"] = pd.to_datetime(df_raw[fecha_col], errors="coerce").dt.normalize()
    out["mes"] = out["fecha"].dt.strftime("%Y-%m")
    out["dia_semana"] = out["fecha"].dt.weekday.map(WEEKDAY_ES)
    out["tienda_codigo"] = _series_text(df_raw, code_col).str.upper()
    out["tienda"] = _series_text(df_raw, tienda_col)
    out["comuna"] = _series_text(df_raw, comuna_col)
    out["jefe_tienda"] = _series_text(df_raw, jefe_col)
    out["ejecutivo"] = _series_text(df_raw, ejecutivo_col)
    out["ventas_total_tienda"] = _series_num(df_raw, ventas_total_col)
    out["ventas_pasillo_5"] = _series_num(df_raw, ventas_pasillo_col)
    out["activaciones_competencia"] = _series_text(df_raw, activaciones_col)
    out["concursos_competencia"] = _series_text(df_raw, concursos_col)
    out["apoyo_vendedores_competencia"] = _series_text(df_raw, apoyo_col)
    out["link_foto_pasillo"] = _series_text(df_raw, foto_pasillo_col)
    out["link_foto_exhibidor"] = _series_text(df_raw, foto_exhibidor_col)
    out["idea_jefe_tienda"] = _series_text(df_raw, idea_col)
    out["notas"] = _series_text(df_raw, notas_col)
    out["pendiente"] = _series_text(df_raw, pendiente_col)
    out["detalle_pendiente"] = _series_text(df_raw, detalle_pend_col)
    out["vendedor_clave"] = _series_text(df_raw, vendedor_col)
    out["conoce_magicshine"] = _series_text(df_raw, conoce_col)
    out["dias_reposicion"] = _series_text(df_raw, reposicion_col)
    out["reposicion_detalle"] = _series_text(df_raw, reposicion_det_col)

    quiebre_cols = [c for c in df_raw.columns if "QUIEBRE" in norm_key(c)]
    riesgo_cols = [c for c in df_raw.columns if "RIESGO" in norm_key(c) and "CANT" not in norm_key(c)]
    sobre_cols = [c for c in df_raw.columns if "SOBRESTOCK" in norm_key(c) or norm_key(c).startswith("SOBRESTOCK") or "SOBRESTOCK" in norm_key(c).replace(" ", "")]
    if not sobre_cols:
        sobre_cols = [c for c in df_raw.columns if norm_key(c).startswith("SOBRESTOCK") or norm_key(c).startswith("SOBRESTOCK") or "SOBRESTOCK" in norm_key(c)]
    # La plantilla usa "Sobre Stock".
    sobre_cols = sorted(set(sobre_cols + [c for c in df_raw.columns if "SOBRESTOCK" in norm_key(c) or "SOBRESTOCK" in norm_key(c).replace(" ", "") or norm_key(c).startswith("SOBRESTOCK") or norm_key(c).startswith("SOBRESTOCK")]))
    sobre_cols = sorted(set(sobre_cols + [c for c in df_raw.columns if norm_key(c).startswith("SOBRESTOCK") or norm_key(c).startswith("SOBRESTOCK") or "SOBRESTOCK" in norm_key(c)]))
    # Fallback explícito para encabezados "Sobre Stock".
    sobre_cols = sorted(set(sobre_cols + [c for c in df_raw.columns if norm_key(c).startswith("SOBRESTOCK") or norm_key(c) in {"SOBRESTOCK1", "SOBRESTOCK2"}]))

    out["quiebres_detectados"] = df_raw.apply(lambda r: _nonempty_count(r, quiebre_cols), axis=1) if quiebre_cols else 0
    out["riesgos_detectados"] = df_raw.apply(lambda r: _nonempty_count(r, riesgo_cols), axis=1) if riesgo_cols else 0
    out["sobrestock_detectado"] = df_raw.apply(lambda r: _nonempty_count(r, sobre_cols), axis=1) if sobre_cols else 0
    out["tiene_pendiente"] = out["pendiente"].apply(_is_yes) | out["detalle_pendiente"].astype(str).str.strip().ne("")
    out["tiene_fotos"] = out["link_foto_pasillo"].astype(str).str.strip().ne("") | out["link_foto_exhibidor"].astype(str).str.strip().ne("")
    out["conoce_magicshine_si"] = out["conoce_magicshine"].apply(_is_yes)
    out["tiene_vendedor_clave"] = out["vendedor_clave"].astype(str).str.strip().ne("")

    critical_cols = [
        "fecha", "tienda", "ejecutivo", "jefe_tienda", "activaciones_competencia",
        "concursos_competencia", "apoyo_vendedores_competencia", "notas", "pendiente",
        "vendedor_clave", "conoce_magicshine", "link_foto_pasillo", "link_foto_exhibidor",
    ]
    present_counts = []
    for _, row in out.iterrows():
        count = 0
        for col in critical_cols:
            if col in out.columns:
                val = row[col]
                if isinstance(val, pd.Timestamp) and not pd.isna(val):
                    count += 1
                elif clean_text(val):
                    count += 1
        present_counts.append(count)
    out["completitud_pct"] = np.array(present_counts) / len(critical_cols) * 100
    out["calidad_ficha"] = np.select(
        [out["completitud_pct"] >= 70, out["completitud_pct"] >= 45],
        ["Alta", "Media"],
        default="Baja",
    )
    out["archivo_origen"] = source
    out = out[out["fecha"].notna() & out["tienda"].astype(str).str.strip().ne("")].copy()

    report = {
        "archivo": source,
        "tipo": "Ficha visitas",
        "estado": "OK",
        "filas_excel": int(len(df_raw)),
        "registros_generados": int(len(out)),
        "hoja": sheet_name,
        "fecha_min": out["fecha"].min().strftime("%Y-%m-%d") if not out.empty else "",
        "fecha_max": out["fecha"].max().strftime("%Y-%m-%d") if not out.empty else "",
        "tiendas": int(out["tienda_codigo"].replace("", np.nan).nunique()) if not out.empty else 0,
    }
    return out.reset_index(drop=True), report, issues


def read_content_file(file: Any | None = None, workbook_file: Any | None = None) -> tuple[pd.DataFrame, dict[str, Any], list[FileIssue]]:
    """Lee una planilla simple de contenido o una hoja Contenido dentro de otro workbook.

    Formato recomendado: Fecha | Tienda | Tipo contenido | Link | Estado | Aprobado
    """
    source_obj = file if file is not None else workbook_file
    if source_obj is None:
        return pd.DataFrame(), {}, []
    source = file_name(source_obj)
    issues: list[FileIssue] = []
    try:
        xls = pd.ExcelFile(source_obj)
    except Exception as exc:
        return pd.DataFrame(), {}, [FileIssue(source, "Contenido", "Error", str(exc))]

    sheet_name = None
    for s in xls.sheet_names:
        key = norm_key(s)
        if "CONTENIDO" in key or "RRSS" in key or "UGC" in key:
            sheet_name = s
            break
    if sheet_name is None and file is not None:
        sheet_name = xls.sheet_names[0]
    if sheet_name is None:
        return pd.DataFrame(), {}, []

    df_raw = _read_sheet_with_detected_header(xls, sheet_name, ["fecha", "tienda"], max_rows=20)
    if df_raw.empty:
        # For optional content, silently return empty if sheet exists but no expected format.
        if file is not None:
            issues.append(FileIssue(source, "Contenido", "Advertencia", "No se reconoció el formato. Usa: Fecha, Tienda, Tipo contenido, Link, Estado, Aprobado."))
        return pd.DataFrame(), {}, issues

    fecha_col = _find_column(df_raw, ["Fecha"])
    tienda_col = _find_column(df_raw, ["Tienda"])
    tipo_col = _find_column(df_raw, ["Tipo contenido", "Tipo", "Contenido"])
    link_col = _find_column(df_raw, ["Link", "URL", "Enlace"])
    estado_col = _find_column(df_raw, ["Estado"])
    aprobado_col = _find_column(df_raw, ["Aprobado", "Aprobada"])
    tienda_codigo_col = _find_column(df_raw, ["Cod Tienda", "Código Tienda", "Codigo Tienda"])

    out = pd.DataFrame()
    out["fecha"] = pd.to_datetime(df_raw[fecha_col], errors="coerce").dt.normalize() if fecha_col else pd.NaT
    out["mes"] = out["fecha"].dt.strftime("%Y-%m")
    out["tienda_codigo"] = _series_text(df_raw, tienda_codigo_col).str.upper()
    out["tienda"] = _series_text(df_raw, tienda_col)
    out["tipo_contenido"] = _series_text(df_raw, tipo_col)
    out["link"] = _series_text(df_raw, link_col)
    out["estado"] = _series_text(df_raw, estado_col)
    out["aprobado"] = _series_text(df_raw, aprobado_col)
    out["aprobado_bool"] = out["aprobado"].apply(_is_yes)
    out["entregado_bool"] = out["estado"].apply(lambda x: norm_key(x) in {"ENTREGADO", "APROBADO", "PUBLICADO", "LISTO"})
    out["archivo_origen"] = source
    out = out[out["fecha"].notna() & out["tienda"].astype(str).str.strip().ne("")].copy()

    report = {
        "archivo": source,
        "tipo": "Contenido terreno",
        "estado": "OK",
        "filas_excel": int(len(df_raw)),
        "registros_generados": int(len(out)),
        "hoja": sheet_name,
        "fecha_min": out["fecha"].min().strftime("%Y-%m-%d") if not out.empty else "",
        "fecha_max": out["fecha"].max().strftime("%Y-%m-%d") if not out.empty else "",
        "tiendas": int(out["tienda"].replace("", np.nan).nunique()) if not out.empty else 0,
    }
    return out.reset_index(drop=True), report, issues

def build_master_dataset(
    sellout_files: Iterable[Any],
    promoter_file: Any | None = None,
    visits_file: Any | None = None,
    content_file: Any | None = None,
) -> dict[str, pd.DataFrame]:
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

    visits = pd.DataFrame()
    visits_report = pd.DataFrame()
    visits_issues = pd.DataFrame()
    if visits_file is not None:
        try:
            visits, report, issues = read_visits_file(visits_file)
            visits_report = pd.DataFrame([report]) if report else pd.DataFrame()
            visits_issues = pd.DataFrame([i.__dict__ for i in issues])
        except Exception as exc:
            visits_issues = pd.DataFrame([FileIssue(file_name(visits_file), "Ficha visitas", "Error", str(exc)).__dict__])

    content = pd.DataFrame()
    content_report = pd.DataFrame()
    content_issues = pd.DataFrame()
    # Permite planilla separada de contenido o una hoja Contenido dentro de la ficha de visitas.
    content_source = content_file if content_file is not None else visits_file
    if content_source is not None:
        try:
            content, report, issues = read_content_file(content_file, visits_file if content_file is None else None)
            content_report = pd.DataFrame([report]) if report else pd.DataFrame()
            content_issues = pd.DataFrame([i.__dict__ for i in issues])
        except Exception as exc:
            content_issues = pd.DataFrame([FileIssue(file_name(content_source), "Contenido", "Error", str(exc)).__dict__])

    master = enrich_sales_with_activations(sales, activations)
    quality = pd.concat([sellout_report, promoter_report, visits_report, content_report], ignore_index=True) if any(not x.empty for x in [sellout_report, promoter_report, visits_report, content_report]) else pd.DataFrame()
    issues = pd.concat([sellout_issues, promoter_issues, visits_issues, content_issues], ignore_index=True) if any(not x.empty for x in [sellout_issues, promoter_issues, visits_issues, content_issues]) else pd.DataFrame(columns=["archivo", "tipo", "estado", "detalle"])

    return {
        "ventas": sales,
        "activaciones": activations,
        "visitas": visits,
        "contenido": content,
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
