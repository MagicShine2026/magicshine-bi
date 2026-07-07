from __future__ import annotations

import numpy as np
import pandas as pd

WEEKDAY_ORDER = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
WEEKDAY_MAP = {day: i for i, day in enumerate(WEEKDAY_ORDER)}

FIELD_VISIT_CODES = {"VC", "VCG", "G"}
ACTIVATION_CODES = {"MS", "MSH", "MSHG", "AM", "PM"}
SATURDAY_CODES = {"MS"}


def money(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        value = 0
    return f"${float(value):,.0f}".replace(",", ".")


def integer(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        value = 0
    return f"{float(value):,.0f}".replace(",", ".")


def pct(value: float | int | None) -> str:
    if value is None or pd.isna(value) or np.isinf(value):
        return "0,0%"
    return f"{float(value):,.1f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def safe_div(num: float, den: float) -> float:
    return float(num / den) if den not in (0, None) and not pd.isna(den) else 0.0


def add_variation(current: float, previous: float) -> tuple[float, float]:
    diff = float(current - previous)
    rate = safe_div(diff, previous) * 100 if previous else 0.0
    return diff, rate


def kpi_summary(df: pd.DataFrame) -> dict[str, float | int]:
    if df is None or df.empty:
        return {"venta": 0, "unidades": 0, "tiendas": 0, "skus": 0, "dias": 0, "venta_unidad": 0}
    venta = float(df["venta"].sum())
    unidades = float(df["unidades"].sum())
    return {
        "venta": venta,
        "unidades": unidades,
        "tiendas": int(df["tienda_codigo"].replace("", np.nan).nunique()),
        "skus": int(df["sku"].replace("", np.nan).nunique()),
        "dias": int(df["fecha"].nunique()),
        "venta_unidad": safe_div(venta, unidades),
    }


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["mes", "venta", "unidades", "tiendas", "skus", "venta_unidad"])
    out = (
        df.groupby("mes", as_index=False)
        .agg(
            venta=("venta", "sum"),
            unidades=("unidades", "sum"),
            tiendas=("tienda_codigo", "nunique"),
            skus=("sku", "nunique"),
            dias=("fecha", "nunique"),
        )
        .sort_values("mes")
    )
    out["venta_unidad"] = out["venta"] / out["unidades"].replace(0, np.nan)
    out["venta_unidad"] = out["venta_unidad"].fillna(0)
    out["var_venta"] = out["venta"].diff().fillna(0)
    out["var_venta_pct"] = out["venta"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0) * 100
    out["var_unidades"] = out["unidades"].diff().fillna(0)
    out["var_unidades_pct"] = out["unidades"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0) * 100
    return out


def latest_month_comparison(df: pd.DataFrame) -> dict[str, float | str]:
    ms = monthly_summary(df)
    if ms.empty:
        return {"mes_actual": "", "mes_anterior": "", "venta_actual": 0, "venta_anterior": 0, "var_venta": 0, "var_venta_pct": 0}
    current = ms.iloc[-1]
    previous = ms.iloc[-2] if len(ms) >= 2 else None
    return {
        "mes_actual": current["mes"],
        "mes_anterior": previous["mes"] if previous is not None else "",
        "venta_actual": float(current["venta"]),
        "venta_anterior": float(previous["venta"]) if previous is not None else 0,
        "var_venta": float(current["var_venta"]),
        "var_venta_pct": float(current["var_venta_pct"]),
        "unidades_actual": float(current["unidades"]),
        "unidades_anterior": float(previous["unidades"]) if previous is not None else 0,
        "var_unidades": float(current["var_unidades"]),
        "var_unidades_pct": float(current["var_unidades_pct"]),
    }


def store_ranking(df: pd.DataFrame, ascending: bool = False, n: int = 10) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby(["tienda_codigo", "tienda"], as_index=False)
        .agg(venta=("venta", "sum"), unidades=("unidades", "sum"), skus=("sku", "nunique"), dias=("fecha", "nunique"))
        .assign(venta_unidad=lambda x: x["venta"] / x["unidades"].replace(0, np.nan))
        .fillna({"venta_unidad": 0})
        .sort_values("venta", ascending=ascending)
        .head(n)
    )


def product_ranking(df: pd.DataFrame, ascending: bool = False, n: int = 10) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby(["sku", "producto", "categoria"], as_index=False)
        .agg(venta=("venta", "sum"), unidades=("unidades", "sum"), tiendas=("tienda_codigo", "nunique"))
        .assign(venta_unidad=lambda x: x["venta"] / x["unidades"].replace(0, np.nan))
        .fillna({"venta_unidad": 0})
        .sort_values("venta", ascending=ascending)
        .head(n)
    )


def weekday_ranking(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    out = (
        df.groupby("dia_semana", as_index=False)
        .agg(venta=("venta", "sum"), unidades=("unidades", "sum"), dias=("fecha", "nunique"))
    )
    out["orden"] = out["dia_semana"].map(WEEKDAY_MAP)
    out["venta_promedio_dia"] = out["venta"] / out["dias"].replace(0, np.nan)
    return out.sort_values("orden").drop(columns="orden").fillna(0)


def daily_sales(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["fecha", "venta", "unidades", "tiendas"])
    return (
        df.groupby("fecha", as_index=False)
        .agg(venta=("venta", "sum"), unidades=("unidades", "sum"), tiendas=("tienda_codigo", "nunique"))
        .sort_values("fecha")
    )


def category_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby("categoria", as_index=False)
        .agg(venta=("venta", "sum"), unidades=("unidades", "sum"), skus=("sku", "nunique"))
        .sort_values("venta", ascending=False)
    )


def growth_by_store(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or df["mes"].nunique() < 2:
        return pd.DataFrame()
    months = sorted(df["mes"].dropna().unique())[-2:]
    prev_month, curr_month = months[0], months[1]
    base = (
        df[df["mes"].isin(months)]
        .groupby(["tienda_codigo", "tienda", "mes"], as_index=False)
        .agg(venta=("venta", "sum"), unidades=("unidades", "sum"))
    )
    piv = base.pivot_table(index=["tienda_codigo", "tienda"], columns="mes", values=["venta", "unidades"], fill_value=0)
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    piv = piv.reset_index()
    piv["venta_anterior"] = piv.get(f"venta_{prev_month}", 0)
    piv["venta_actual"] = piv.get(f"venta_{curr_month}", 0)
    piv["unidades_anterior"] = piv.get(f"unidades_{prev_month}", 0)
    piv["unidades_actual"] = piv.get(f"unidades_{curr_month}", 0)
    piv["var_venta"] = piv["venta_actual"] - piv["venta_anterior"]
    piv["var_venta_pct"] = np.where(piv["venta_anterior"] > 0, piv["var_venta"] / piv["venta_anterior"] * 100, 0)
    piv["var_unidades"] = piv["unidades_actual"] - piv["unidades_anterior"]
    piv["periodo"] = f"{prev_month} → {curr_month}"
    return piv[["tienda_codigo", "tienda", "periodo", "venta_anterior", "venta_actual", "var_venta", "var_venta_pct", "unidades_anterior", "unidades_actual", "var_unidades"]]


def activation_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "activacion" not in df.columns:
        return pd.DataFrame()
    out = (
        df.groupby("activacion", as_index=False)
        .agg(venta=("venta", "sum"), unidades=("unidades", "sum"), registros=("sku", "count"), dias=("fecha", "nunique"), tiendas=("tienda_codigo", "nunique"))
    )
    out["venta_promedio_dia"] = out["venta"] / out["dias"].replace(0, np.nan)
    out["venta_unidad"] = out["venta"] / out["unidades"].replace(0, np.nan)
    return out.fillna(0)


def activation_impact_monthly(df: pd.DataFrame, activations: pd.DataFrame) -> pd.DataFrame:
    if df.empty or activations.empty or df["mes"].nunique() < 2:
        return pd.DataFrame()
    months = sorted(df["mes"].dropna().unique())[-2:]
    prev_month, curr_month = months[0], months[1]
    act_valid = valid_activities(activations)
    active_stores = set(act_valid[act_valid["mes"].eq(curr_month)]["tienda_codigo"].dropna().unique())
    base = df[df["mes"].isin(months)].copy()
    base["grupo"] = np.where(base["tienda_codigo"].isin(active_stores), "Tiendas con activación/visita", "Tiendas sin activación/visita")
    out = (
        base.groupby(["grupo", "mes"], as_index=False)
        .agg(venta=("venta", "sum"), unidades=("unidades", "sum"), tiendas=("tienda_codigo", "nunique"))
    )
    piv = out.pivot_table(index="grupo", columns="mes", values=["venta", "unidades", "tiendas"], fill_value=0)
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    piv = piv.reset_index()
    piv["venta_anterior"] = piv.get(f"venta_{prev_month}", 0)
    piv["venta_actual"] = piv.get(f"venta_{curr_month}", 0)
    piv["var_venta"] = piv["venta_actual"] - piv["venta_anterior"]
    piv["var_venta_pct"] = np.where(piv["venta_anterior"] > 0, piv["var_venta"] / piv["venta_anterior"] * 100, 0)
    piv["unidades_anterior"] = piv.get(f"unidades_{prev_month}", 0)
    piv["unidades_actual"] = piv.get(f"unidades_{curr_month}", 0)
    piv["var_unidades"] = piv["unidades_actual"] - piv["unidades_anterior"]
    piv["periodo"] = f"{prev_month} → {curr_month}"
    return piv[["grupo", "periodo", "venta_anterior", "venta_actual", "var_venta", "var_venta_pct", "unidades_anterior", "unidades_actual", "var_unidades"]]


def classify_field_activity(
    code: str,
    weekday: str,
    tipo_actividad: str = "",
    ejecutor: str = "",
    cuenta_activacion: str = "",
    kpi_sebastian: str = "",
    estado_actividad: str = "",
) -> str:
    code = str(code or "").upper().strip()
    tipo = str(tipo_actividad or "").lower()
    ejecutor_norm = str(ejecutor or "").lower()
    estado = str(estado_actividad or "").lower()
    if "cancel" in estado:
        return "Actividad cancelada"
    if "cerr" in estado or "cerr" in code.lower() or "no operativa" in tipo:
        return "Tienda cerrada"
    if "visita" in tipo or code in FIELD_VISIT_CODES:
        return "Visita Sebastián" if "sebasti" in ejecutor_norm or str(kpi_sebastian).lower() in {"sí", "si"} else "Visita comercial"
    if "activación" in tipo or "activacion" in tipo or code in ACTIVATION_CODES:
        if "agencia" in ejecutor_norm:
            return "Activación agencia"
        if "sebasti" in ejecutor_norm or str(kpi_sebastian).lower() in {"sí", "si"}:
            return "Activación Sebastián semana" if weekday != "Sábado" else "Activación Sebastián sábado"
        if weekday == "Sábado":
            return "Activación sábado"
        return "Activación terreno semana"
    if code:
        return "Otra actividad"
    return "Sin actividad"


def classify_activity_row(row: pd.Series) -> str:
    return classify_field_activity(
        row.get("activacion_codigo", ""),
        row.get("dia_semana", ""),
        row.get("tipo_actividad", ""),
        row.get("ejecutor", ""),
        row.get("cuenta_activacion", ""),
        row.get("kpi_sebastian", ""),
        row.get("estado_actividad", ""),
    )


def valid_activities(activations: pd.DataFrame) -> pd.DataFrame:
    if activations is None or activations.empty:
        return pd.DataFrame()
    act = activations.copy()
    if "actividad_valida" in act.columns:
        act = act[act["actividad_valida"].astype(str).str.lower().isin(["sí", "si", "yes", "true", "1"])]
    elif "estado_actividad" in act.columns:
        act = act[~act["estado_actividad"].astype(str).str.lower().str.contains("cancel|cerr", regex=True, na=False)]
    return act



def _yes_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["sí", "si", "yes", "true", "1", "x"])


def field_visit_kpis(activations: pd.DataFrame, sales: pd.DataFrame | None = None) -> dict[str, pd.DataFrame | dict]:
    """KPIs operativos de terreno, separados por responsable y tipo de actividad.

    Regla de negocio:
    - Sebastián: cuenta KPI cuando el diccionario indique KPI Sebastián = Sí, o el ejecutor sea Sebastián.
    - Activaciones de cumplimiento semanal: solo activaciones ejecutadas de Sebastián de lunes a viernes.
    - Sábado se informa aparte, porque no cuenta para la meta mínima semanal definida para el cargo.
    - Agencia se informa aparte para no contaminar el desempeño individual de Sebastián.
    """
    empty_summary = {
        "visitas": 0,
        "visitas_con_incentivo": 0,
        "activaciones_semana": 0,
        "activaciones_sabado_agencia": 0,
        "activaciones_sabado_sebastian": 0,
        "activaciones_sabado": 0,
        "activaciones_agencia_total": 0,
        "actividades_sebastian_total": 0,
        "actividades_total": 0,
        "tiendas": 0,
        "semanas_ok": 0,
        "semanas_total": 0,
        "objetivo_activaciones_semana": 0,
        "brecha_activaciones_semana": 0,
        "cumplimiento_semanas_pct": 0,
        "cumplimiento_volumen_pct": 0,
        "estado": "Sin datos",
    }
    if activations is None or activations.empty:
        return {"summary": empty_summary, "weekly": pd.DataFrame(), "by_store": pd.DataFrame(), "detail": pd.DataFrame()}

    act = valid_activities(activations).copy()
    if act.empty:
        return {"summary": empty_summary, "weekly": pd.DataFrame(), "by_store": pd.DataFrame(), "detail": pd.DataFrame()}

    act["fecha"] = pd.to_datetime(act["fecha"]).dt.normalize()
    act["actividad_terreno"] = act.apply(classify_activity_row, axis=1)
    act["semana"] = act["fecha"].dt.to_period("W-SUN").astype(str)
    act["semana_inicio"] = act["fecha"].dt.to_period("W-SUN").apply(lambda p: p.start_time).dt.normalize()
    act["semana_fin"] = act["fecha"].dt.to_period("W-SUN").apply(lambda p: p.end_time).dt.normalize()

    ejecutor = act.get("ejecutor", pd.Series("", index=act.index)).astype(str).str.lower()
    tipo = act.get("tipo_actividad", pd.Series("", index=act.index)).astype(str).str.lower()
    cuenta_activacion = _yes_series(act.get("cuenta_activacion", pd.Series("No", index=act.index)))
    kpi_sebastian = _yes_series(act.get("kpi_sebastian", pd.Series("No", index=act.index)))
    kpi_agencia = _yes_series(act.get("kpi_agencia", pd.Series("No", index=act.index)))

    act["es_sebastian"] = kpi_sebastian | ejecutor.str.contains("sebasti", na=False)
    act["es_agencia"] = kpi_agencia | ejecutor.str.contains("agencia", na=False)
    act["es_visita"] = tipo.str.contains("visita", na=False) & act["es_sebastian"]
    act["es_visita_incentivo"] = tipo.str.contains("incentivo|galleta", regex=True, na=False) & act["es_visita"]
    act["es_activacion"] = cuenta_activacion | tipo.str.contains("activaci", na=False)
    act["es_lun_vie"] = ~act["dia_semana"].isin(["Sábado", "Domingo"])
    act["es_sabado"] = act["dia_semana"].eq("Sábado")
    act["es_activacion_sebastian_lun_vie"] = act["es_activacion"] & act["es_sebastian"] & act["es_lun_vie"]
    act["es_activacion_sabado_agencia"] = act["es_activacion"] & act["es_agencia"] & act["es_sabado"]
    act["es_activacion_sabado_sebastian"] = act["es_activacion"] & act["es_sebastian"] & act["es_sabado"]
    act["es_activacion_agencia"] = act["es_activacion"] & act["es_agencia"]
    act["es_actividad_sebastian"] = act["es_sebastian"] & (act["es_visita"] | act["es_activacion"])

    weekly = (
        act.groupby(["semana", "semana_inicio", "semana_fin"], as_index=False)
        .agg(
            visitas=("es_visita", "sum"),
            visitas_con_incentivo=("es_visita_incentivo", "sum"),
            activaciones_sebastian_lun_vie=("es_activacion_sebastian_lun_vie", "sum"),
            activaciones_sabado_agencia=("es_activacion_sabado_agencia", "sum"),
            activaciones_sabado_sebastian=("es_activacion_sabado_sebastian", "sum"),
            activaciones_agencia_total=("es_activacion_agencia", "sum"),
            actividades_sebastian_total=("es_actividad_sebastian", "sum"),
            tiendas_trabajadas=("tienda_codigo", "nunique"),
            actividades_total=("tienda_codigo", "count"),
        )
        .sort_values("semana_inicio")
    )
    weekly["objetivo_activaciones_semana"] = 4
    weekly["brecha_activaciones"] = (weekly["objetivo_activaciones_semana"] - weekly["activaciones_sebastian_lun_vie"]).clip(lower=0)
    weekly["cumplimiento_volumen_pct"] = np.minimum(weekly["activaciones_sebastian_lun_vie"] / 4 * 100, 100)
    weekly["cumple_semana"] = np.where(weekly["activaciones_sebastian_lun_vie"] >= 4, "Sí", "No")
    weekly["estado"] = np.select(
        [weekly["activaciones_sebastian_lun_vie"] >= 4, weekly["activaciones_sebastian_lun_vie"].between(2, 3)],
        ["Verde", "Amarillo"],
        default="Rojo",
    )

    by_store = (
        act.groupby(["tienda_codigo", "tienda_promotores", "comuna", "zona"], as_index=False)
        .agg(
            visitas=("es_visita", "sum"),
            visitas_con_incentivo=("es_visita_incentivo", "sum"),
            activaciones_sebastian_lun_vie=("es_activacion_sebastian_lun_vie", "sum"),
            activaciones_sabado_agencia=("es_activacion_sabado_agencia", "sum"),
            activaciones_sabado_sebastian=("es_activacion_sabado_sebastian", "sum"),
            activaciones_agencia_total=("es_activacion_agencia", "sum"),
            actividades_sebastian_total=("es_actividad_sebastian", "sum"),
            actividades_total=("tienda_codigo", "count"),
            primera_fecha=("fecha", "min"),
            ultima_fecha=("fecha", "max"),
        )
        .sort_values("actividades_total", ascending=False)
    )

    if sales is not None and not sales.empty:
        sales_by_store = sales.groupby("tienda_codigo", as_index=False).agg(venta=("venta", "sum"), unidades=("unidades", "sum"))
        by_store = by_store.merge(sales_by_store, on="tienda_codigo", how="left").fillna({"venta": 0, "unidades": 0})

    weeks_total = int(len(weekly))
    weeks_ok = int((weekly["cumple_semana"] == "Sí").sum()) if weeks_total else 0
    target_total = weeks_total * 4
    activations_weekday = int(act["es_activacion_sebastian_lun_vie"].sum())
    gap = int(max(target_total - activations_weekday, 0))
    compliance_weeks = safe_div(weeks_ok, weeks_total) * 100 if weeks_total else 0
    compliance_volume = min(safe_div(activations_weekday, target_total) * 100, 100) if target_total else 0

    if compliance_weeks >= 80 and gap == 0:
        status = "Verde"
    elif compliance_weeks >= 50 or compliance_volume >= 70:
        status = "Amarillo"
    else:
        status = "Rojo"

    summary = {
        "visitas": int(act["es_visita"].sum()),
        "visitas_con_incentivo": int(act["es_visita_incentivo"].sum()),
        "activaciones_semana": activations_weekday,
        "activaciones_sabado_agencia": int(act["es_activacion_sabado_agencia"].sum()),
        "activaciones_sabado_sebastian": int(act["es_activacion_sabado_sebastian"].sum()),
        "activaciones_sabado": int((act["es_activacion_sabado_agencia"] | act["es_activacion_sabado_sebastian"]).sum()),
        "activaciones_agencia_total": int(act["es_activacion_agencia"].sum()),
        "actividades_sebastian_total": int(act["es_actividad_sebastian"].sum()),
        "actividades_total": int(len(act)),
        "tiendas": int(act.loc[act["es_actividad_sebastian"], "tienda_codigo"].nunique()),
        "semanas_ok": weeks_ok,
        "semanas_total": weeks_total,
        "objetivo_activaciones_semana": target_total,
        "brecha_activaciones_semana": gap,
        "cumplimiento_semanas_pct": compliance_weeks,
        "cumplimiento_volumen_pct": compliance_volume,
        "estado": status,
    }

    return {"summary": summary, "weekly": weekly, "by_store": by_store, "detail": act}

def basic_diagnosis(df: pd.DataFrame, activations: pd.DataFrame) -> list[str]:
    notes: list[str] = []
    if df.empty:
        return ["No hay datos suficientes para diagnóstico."]
    ms = monthly_summary(df)
    if len(ms) >= 2:
        last = ms.iloc[-1]
        sign = "sube" if last["var_venta"] >= 0 else "cae"
        notes.append(f"La venta de {last['mes']} {sign} {money(abs(last['var_venta']))} versus el mes anterior ({pct(abs(last['var_venta_pct']))}).")
    top_store = store_ranking(df, n=1)
    if not top_store.empty:
        notes.append(f"La tienda líder es {top_store.iloc[0]['tienda']} con {money(top_store.iloc[0]['venta'])} en el período filtrado.")
    top_product = product_ranking(df, n=1)
    if not top_product.empty:
        notes.append(f"El producto líder es {top_product.iloc[0]['producto']} con {money(top_product.iloc[0]['venta'])}.")
    impact = activation_impact_monthly(df, activations)
    if not impact.empty:
        row = impact[impact["grupo"].eq("Tiendas con activación/visita")]
        if not row.empty:
            r = row.iloc[0]
            notes.append(f"Las tiendas con activación/visita muestran variación de {pct(r['var_venta_pct'])} en {r['periodo']}.")
    return notes


def store_activation_effect(df: pd.DataFrame, activations: pd.DataFrame) -> pd.DataFrame:
    """Store-level before/after view with an estimated uplift vs non-activated benchmark.

    Uses the latest two months in the filtered sales data. The current month activity list
    defines worked stores. Uplift is estimated as actual current sales minus expected sales,
    where expected sales = previous sales * (1 + non-worked-store growth rate).
    """
    if df is None or df.empty or df["mes"].nunique() < 2:
        return pd.DataFrame()
    months = sorted(df["mes"].dropna().unique())[-2:]
    prev_month, curr_month = months[0], months[1]
    base = (
        df[df["mes"].isin(months)]
        .groupby(["tienda_codigo", "tienda", "mes"], as_index=False)
        .agg(venta=("venta", "sum"), unidades=("unidades", "sum"))
    )
    piv = base.pivot_table(index=["tienda_codigo", "tienda"], columns="mes", values=["venta", "unidades"], fill_value=0)
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    out = piv.reset_index()
    out["venta_anterior"] = out.get(f"venta_{prev_month}", 0).astype(float)
    out["venta_actual"] = out.get(f"venta_{curr_month}", 0).astype(float)
    out["unidades_anterior"] = out.get(f"unidades_{prev_month}", 0).astype(float)
    out["unidades_actual"] = out.get(f"unidades_{curr_month}", 0).astype(float)
    out["var_venta"] = out["venta_actual"] - out["venta_anterior"]
    out["var_venta_pct"] = np.where(out["venta_anterior"] > 0, out["var_venta"] / out["venta_anterior"] * 100, 0.0)
    out["var_unidades"] = out["unidades_actual"] - out["unidades_anterior"]

    active = pd.DataFrame()
    if activations is not None and not activations.empty:
        act = valid_activities(activations).copy()
        act["fecha"] = pd.to_datetime(act["fecha"]).dt.normalize()
        act = act[act["mes"].eq(curr_month)].copy()
        if not act.empty:
            act["actividad_terreno"] = act.apply(classify_activity_row, axis=1)
            act["es_visita"] = act["actividad_terreno"].str.contains("Visita", na=False) & act.get("kpi_sebastian", "No").astype(str).str.lower().isin(["sí", "si"])
            act["es_activacion_semana"] = act["actividad_terreno"].eq("Activación Sebastián semana")
            act["es_activacion_sabado"] = act["actividad_terreno"].str.contains("Activación", na=False) & act["dia_semana"].eq("Sábado")
            active = (
                act.groupby("tienda_codigo", as_index=False)
                .agg(
                    actividades=("tienda_codigo", "count"),
                    visitas=("es_visita", "sum"),
                    activaciones_semana=("es_activacion_semana", "sum"),
                    activaciones_sabado=("es_activacion_sabado", "sum"),
                    primera_actividad=("fecha", "min"),
                    ultima_actividad=("fecha", "max"),
                )
            )
    out = out.merge(active, on="tienda_codigo", how="left") if not active.empty else out
    for col in ["actividades", "visitas", "activaciones_semana", "activaciones_sabado"]:
        out[col] = out[col].fillna(0).astype(int) if col in out.columns else 0
    out["tienda_trabajada"] = np.where(out["actividades"] > 0, "Sí", "No")

    # Benchmark growth from non-worked stores. If unavailable, use total portfolio growth.
    non_worked = out[(out["tienda_trabajada"] == "No") & (out["venta_anterior"] > 0)]
    if not non_worked.empty and non_worked["venta_anterior"].sum() > 0:
        benchmark_growth = (non_worked["venta_actual"].sum() - non_worked["venta_anterior"].sum()) / non_worked["venta_anterior"].sum()
    elif out["venta_anterior"].sum() > 0:
        benchmark_growth = (out["venta_actual"].sum() - out["venta_anterior"].sum()) / out["venta_anterior"].sum()
    else:
        benchmark_growth = 0.0
    out["benchmark_no_trabajadas_pct"] = benchmark_growth * 100
    out["venta_esperada"] = out["venta_anterior"] * (1 + benchmark_growth)
    out["uplift_estimado"] = out["venta_actual"] - out["venta_esperada"]
    out["periodo"] = f"{prev_month} → {curr_month}"

    def action(row):
        if row["tienda_trabajada"] == "Sí" and row["uplift_estimado"] > 0 and row["var_venta"] > 0:
            return "Escalar / mantener cobertura"
        if row["tienda_trabajada"] == "Sí" and row["uplift_estimado"] <= 0:
            return "Revisar ejecución en tienda"
        if row["tienda_trabajada"] == "No" and row["venta_anterior"] > 0 and row["var_venta"] < 0:
            return "Priorizar visita recuperación"
        if row["tienda_trabajada"] == "No" and row["venta_actual"] > 0:
            return "Evaluar activación para capturar upside"
        return "Monitorear"

    out["accion_sugerida"] = out.apply(action, axis=1)
    cols = [
        "tienda_codigo", "tienda", "periodo", "tienda_trabajada", "actividades", "visitas",
        "activaciones_semana", "activaciones_sabado", "venta_anterior", "venta_actual", "var_venta",
        "var_venta_pct", "venta_esperada", "uplift_estimado", "benchmark_no_trabajadas_pct",
        "unidades_anterior", "unidades_actual", "var_unidades", "accion_sugerida",
    ]
    return out[cols].sort_values("uplift_estimado", ascending=False)


def activation_calendar_matrix(activations: pd.DataFrame) -> pd.DataFrame:
    if activations is None or activations.empty:
        return pd.DataFrame()
    act = valid_activities(activations).copy()
    if act.empty:
        return pd.DataFrame()
    act["fecha"] = pd.to_datetime(act["fecha"]).dt.normalize()
    act["actividad_terreno"] = act.apply(classify_activity_row, axis=1)
    out = (
        act.groupby(["fecha", "dia_semana", "actividad_terreno"], as_index=False)
        .agg(tiendas=("tienda_codigo", "nunique"), actividades=("tienda_codigo", "count"))
        .sort_values("fecha")
    )
    return out



def sebastian_scorecard(activations: pd.DataFrame, sales: pd.DataFrame | None = None) -> dict:
    field = field_visit_kpis(activations, sales)
    fs = field["summary"]
    by_store = field["by_store"]
    top_store = ""
    top_sales = 0
    if by_store is not None and not by_store.empty and "venta" in by_store.columns:
        top = by_store.sort_values("venta", ascending=False).iloc[0]
        top_store = str(top.get("tienda_promotores", ""))
        top_sales = float(top.get("venta", 0))

    summary = {
        **fs,
        "cumplimiento_pct": fs.get("cumplimiento_semanas_pct", 0),  # compatibilidad con versiones previas
        "tienda_top_venta_trabajada": top_store,
        "venta_top_tienda_trabajada": top_sales,
    }
    return {"summary": summary, "weekly": field["weekly"], "by_store": by_store, "detail": field["detail"]}

def executive_action_plan(df: pd.DataFrame, activations: pd.DataFrame) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    impact = store_activation_effect(df, activations)
    if impact.empty:
        return [{"prioridad": "Media", "tema": "Datos", "accion": "Cargar al menos dos meses de sell out y el calendario de activaciones para generar plan comercial."}]

    recovery = impact[(impact["tienda_trabajada"] == "No") & (impact["var_venta"] < 0)].sort_values("var_venta").head(5)
    if not recovery.empty:
        stores = ", ".join(recovery["tienda"].head(3).tolist())
        actions.append({"prioridad": "Alta", "tema": "Recuperación", "accion": f"Priorizar visita/activación en tiendas no trabajadas con caída: {stores}."})

    review = impact[(impact["tienda_trabajada"] == "Sí") & (impact["uplift_estimado"] <= 0)].sort_values("uplift_estimado").head(5)
    if not review.empty:
        stores = ", ".join(review["tienda"].head(3).tolist())
        actions.append({"prioridad": "Alta", "tema": "Ejecución", "accion": f"Revisar calidad de ejecución en tiendas trabajadas sin uplift: {stores}."})

    winners = impact[(impact["tienda_trabajada"] == "Sí") & (impact["uplift_estimado"] > 0)].sort_values("uplift_estimado", ascending=False).head(5)
    if not winners.empty:
        stores = ", ".join(winners["tienda"].head(3).tolist())
        actions.append({"prioridad": "Media", "tema": "Escalamiento", "accion": f"Mantener o replicar formato de activación en tiendas con uplift positivo: {stores}."})

    products = product_ranking(df, n=5)
    if not products.empty:
        lead = products.iloc[0]
        actions.append({"prioridad": "Media", "tema": "Producto", "accion": f"Usar el producto líder ({lead['producto']}) como gancho de demostración y cross-sell en activaciones."})

    return actions


def _unique_join(values) -> str:
    vals = [str(v).strip() for v in values if str(v).strip() and str(v).strip().lower() not in {"nan", "none"}]
    return ", ".join(sorted(set(vals)))


def _activity_flags(act: pd.DataFrame) -> pd.DataFrame:
    """Normaliza flags para actividades de terreno usando el diccionario si existe."""
    if act is None or act.empty:
        return pd.DataFrame()
    out = valid_activities(act).copy()
    if out.empty:
        return out
    out["fecha"] = pd.to_datetime(out["fecha"]).dt.normalize()
    out["actividad_terreno"] = out.apply(classify_activity_row, axis=1)
    ejecutor = out.get("ejecutor", pd.Series("", index=out.index)).astype(str).str.lower()
    tipo = out.get("tipo_actividad", pd.Series("", index=out.index)).astype(str).str.lower()
    cuenta_activacion = _yes_series(out.get("cuenta_activacion", pd.Series("No", index=out.index)))
    kpi_sebastian = _yes_series(out.get("kpi_sebastian", pd.Series("No", index=out.index)))
    kpi_agencia = _yes_series(out.get("kpi_agencia", pd.Series("No", index=out.index)))
    out["es_sebastian"] = kpi_sebastian | ejecutor.str.contains("sebasti", na=False)
    out["es_agencia"] = kpi_agencia | ejecutor.str.contains("agencia", na=False)
    out["es_visita"] = tipo.str.contains("visita", na=False)
    out["es_incentivo"] = tipo.str.contains("incentivo|galleta", regex=True, na=False) | out.get("activacion_codigo", pd.Series("", index=out.index)).astype(str).str.upper().str.contains("G", na=False)
    out["es_activacion"] = cuenta_activacion | tipo.str.contains("activaci", na=False)
    out["grupo_ejecutor"] = np.select(
        [out["es_sebastian"] & out["es_agencia"], out["es_sebastian"], out["es_agencia"]],
        ["Mixto", "Sebastián", "Agencia"],
        default="Sin clasificar",
    )
    out["grupo_tipo"] = np.select(
        [out["es_activacion"] & out["es_visita"], out["es_activacion"], out["es_visita"] & out["es_incentivo"], out["es_visita"]],
        ["Activación + visita", "Activación", "Visita con incentivo", "Visita comercial"],
        default="Otra actividad",
    )
    return out


def activity_day_impact(sales: pd.DataFrame, activations: pd.DataFrame) -> pd.DataFrame:
    """Traza actividad de terreno vs venta del mismo día por tienda.

    La unidad de análisis es tienda-fecha. El indicador principal es venta_dia: venta
    registrada en esa tienda exactamente el día de la actividad. Como referencia, se calcula
    el promedio diario de la misma tienda en días sin actividad dentro del mismo mes.
    """
    if sales is None or sales.empty or activations is None or activations.empty:
        return pd.DataFrame()

    sales_day = sales.copy()
    sales_day["fecha"] = pd.to_datetime(sales_day["fecha"]).dt.normalize()
    sales_day = (
        sales_day.groupby(["tienda_codigo", "tienda", "fecha", "mes", "dia_semana"], as_index=False)
        .agg(venta_dia=("venta", "sum"), unidades_dia=("unidades", "sum"), skus_dia=("sku", "nunique"))
    )

    act = _activity_flags(activations)
    if act.empty:
        return pd.DataFrame()

    # Agregamos múltiples marcas en la misma tienda-fecha en una sola actividad comercial del día.
    act_day = (
        act.groupby(["tienda_codigo", "fecha"], as_index=False)
        .agg(
            tienda_promotores=("tienda_promotores", "first"),
            comuna=("comuna", "first"),
            zona=("zona", "first"),
            n_actividades=("activacion_codigo", "count"),
            codigos=("activacion_codigo", _unique_join),
            detalle_actividad=("activacion_nombre", _unique_join),
            ejecutores=("ejecutor", _unique_join),
            tipos_actividad=("tipo_actividad", _unique_join),
            grupo_ejecutor=("grupo_ejecutor", _unique_join),
            grupo_tipo=("grupo_tipo", _unique_join),
            tiene_sebastian=("es_sebastian", "max"),
            tiene_agencia=("es_agencia", "max"),
            tiene_visita=("es_visita", "max"),
            tiene_activacion=("es_activacion", "max"),
            tiene_incentivo=("es_incentivo", "max"),
        )
    )

    out = act_day.merge(sales_day, on=["tienda_codigo", "fecha"], how="left")
    out["venta_dia"] = out["venta_dia"].fillna(0)
    out["unidades_dia"] = out["unidades_dia"].fillna(0)
    out["skus_dia"] = out["skus_dia"].fillna(0)
    out["tienda"] = out["tienda"].fillna(out["tienda_promotores"])
    out["mes"] = out["mes"].fillna(out["fecha"].dt.strftime("%Y-%m"))
    if "dia_semana" not in out.columns or out["dia_semana"].isna().any():
        out["dia_semana"] = out["fecha"].dt.dayofweek.map({0:"Lunes",1:"Martes",2:"Miércoles",3:"Jueves",4:"Viernes",5:"Sábado",6:"Domingo"})
    else:
        out["dia_semana"] = out["dia_semana"].fillna(out["fecha"].dt.dayofweek.map({0:"Lunes",1:"Martes",2:"Miércoles",3:"Jueves",4:"Viernes",5:"Sábado",6:"Domingo"}))

    # Baseline: promedio de venta diaria de la misma tienda/mes en días con venta y sin actividad.
    activity_keys = act_day[["tienda_codigo", "fecha"]].drop_duplicates().assign(con_actividad=1)
    baseline_base = sales_day.merge(activity_keys, on=["tienda_codigo", "fecha"], how="left")
    baseline_base["con_actividad"] = baseline_base["con_actividad"].fillna(0)
    baseline_store = (
        baseline_base[baseline_base["con_actividad"].eq(0)]
        .groupby(["tienda_codigo", "mes"], as_index=False)
        .agg(promedio_tienda_sin_actividad=("venta_dia", "mean"), dias_base_tienda=("fecha", "nunique"))
    )
    baseline_global = (
        baseline_base[baseline_base["con_actividad"].eq(0)]
        .groupby("mes", as_index=False)
        .agg(promedio_general_sin_actividad=("venta_dia", "mean"), dias_base_general=("fecha", "nunique"))
    )
    out = out.merge(baseline_store, on=["tienda_codigo", "mes"], how="left")
    out = out.merge(baseline_global, on="mes", how="left")
    out["promedio_referencia"] = out["promedio_tienda_sin_actividad"].fillna(out["promedio_general_sin_actividad"]).fillna(0)
    out["dias_base_tienda"] = out["dias_base_tienda"].fillna(0)
    out["diferencia_vs_referencia"] = out["venta_dia"] - out["promedio_referencia"]
    out["uplift_pct"] = np.where(out["promedio_referencia"] > 0, out["diferencia_vs_referencia"] / out["promedio_referencia"] * 100, 0)
    out["actividad_con_venta"] = np.where(out["venta_dia"] > 0, "Sí", "No")
    out["lectura"] = np.select(
        [out["venta_dia"].eq(0), out["diferencia_vs_referencia"].gt(0), out["diferencia_vs_referencia"].lt(0)],
        ["Sin venta el día de actividad", "Sobre promedio tienda/mes", "Bajo promedio tienda/mes"],
        default="En línea con promedio",
    )
    out = out.sort_values(["fecha", "tienda_codigo"]).reset_index(drop=True)
    return out


def activity_day_summary(impact: pd.DataFrame) -> dict[str, float | int]:
    if impact is None or impact.empty:
        return {"dias_actividad": 0, "actividades": 0, "venta_dia": 0, "unidades_dia": 0, "venta_promedio_actividad": 0, "dias_con_venta_pct": 0, "uplift_estimado": 0, "uplift_pct": 0}
    dias = int(len(impact))
    venta = float(impact["venta_dia"].sum())
    unidades = float(impact["unidades_dia"].sum())
    actividades = int(impact["n_actividades"].sum())
    dias_con_venta = int((impact["venta_dia"] > 0).sum())
    uplift = float(impact["diferencia_vs_referencia"].sum())
    ref = float(impact["promedio_referencia"].sum())
    return {
        "dias_actividad": dias,
        "actividades": actividades,
        "venta_dia": venta,
        "unidades_dia": unidades,
        "venta_promedio_actividad": safe_div(venta, dias),
        "dias_con_venta_pct": safe_div(dias_con_venta, dias) * 100,
        "uplift_estimado": uplift,
        "uplift_pct": safe_div(uplift, ref) * 100 if ref else 0,
    }


def activity_day_by_executor(impact: pd.DataFrame) -> pd.DataFrame:
    if impact is None or impact.empty:
        return pd.DataFrame()
    rows = []
    for label, mask in {
        "Sebastián": impact["tiene_sebastian"].astype(bool),
        "Agencia": impact["tiene_agencia"].astype(bool),
        "Visita comercial": impact["tiene_visita"].astype(bool),
        "Activación": impact["tiene_activacion"].astype(bool),
        "Con incentivo": impact["tiene_incentivo"].astype(bool),
    }.items():
        sub = impact[mask]
        if sub.empty:
            continue
        s = activity_day_summary(sub)
        rows.append({"grupo": label, **s})
    return pd.DataFrame(rows)


def activity_day_by_store(impact: pd.DataFrame, n: int = 30) -> pd.DataFrame:
    if impact is None or impact.empty:
        return pd.DataFrame()
    out = (
        impact.groupby(["tienda_codigo", "tienda"], as_index=False)
        .agg(
            dias_actividad=("fecha", "count"),
            actividades=("n_actividades", "sum"),
            venta_dia=("venta_dia", "sum"),
            unidades_dia=("unidades_dia", "sum"),
            promedio_referencia=("promedio_referencia", "sum"),
            uplift_estimado=("diferencia_vs_referencia", "sum"),
            dias_con_venta=("actividad_con_venta", lambda s: (s == "Sí").sum()),
            primera_fecha=("fecha", "min"),
            ultima_fecha=("fecha", "max"),
        )
    )
    out["uplift_pct"] = np.where(out["promedio_referencia"] > 0, out["uplift_estimado"] / out["promedio_referencia"] * 100, 0)
    out["venta_promedio_dia_actividad"] = out["venta_dia"] / out["dias_actividad"].replace(0, np.nan)
    return out.sort_values("uplift_estimado", ascending=False).head(n).fillna(0)


def product_sales_on_activity_days(sales: pd.DataFrame, impact: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    if sales is None or sales.empty or impact is None or impact.empty:
        return pd.DataFrame()
    keys = impact[["tienda_codigo", "fecha"]].drop_duplicates()
    sales2 = sales.copy()
    sales2["fecha"] = pd.to_datetime(sales2["fecha"]).dt.normalize()
    act_sales = sales2.merge(keys, on=["tienda_codigo", "fecha"], how="inner")
    if act_sales.empty:
        return pd.DataFrame()
    return (
        act_sales.groupby(["sku", "producto", "categoria"], as_index=False)
        .agg(venta=("venta", "sum"), unidades=("unidades", "sum"), tiendas=("tienda_codigo", "nunique"), dias_actividad=("fecha", "nunique"))
        .sort_values("venta", ascending=False)
        .head(n)
    )

# -----------------------------
# Evaluación Sebastián por familias KPI
# -----------------------------

def sebastian_commercial_impact(impact: pd.DataFrame) -> dict[str, pd.DataFrame | dict]:
    """Resume actividad vs venta mismo día en las tres bolsas relevantes.

    Bolsas:
    - Sebastián activación PM/L-V: actividades MSH/MSHG o activación de Sebastián fuera de sábado.
    - Sebastián visitas: VC/VCG.
    - Agencia sábado: MS u otras activaciones de agencia en sábado.
    """
    if impact is None or impact.empty:
        empty = pd.DataFrame()
        return {"summary": {}, "groups": empty, "detail": empty, "top_positive": empty, "top_negative": empty}
    df = impact.copy()
    for col in ["tiene_sebastian", "tiene_agencia", "tiene_visita", "tiene_activacion", "tiene_incentivo"]:
        if col not in df.columns:
            df[col] = False
    df["codigo_norm"] = df.get("codigos", "").astype(str).str.upper()

    conditions = [
        (df["tiene_sebastian"].astype(bool) & df["tiene_activacion"].astype(bool) & ~df["dia_semana"].eq("Sábado")),
        (df["tiene_sebastian"].astype(bool) & df["tiene_visita"].astype(bool)),
        (df["tiene_agencia"].astype(bool) & df["tiene_activacion"].astype(bool) & df["dia_semana"].eq("Sábado")),
    ]
    labels = ["Sebastián activación PM/L-V", "Sebastián visita comercial", "Agencia sábado"]
    df["bolsa_kpi"] = np.select(conditions, labels, default="Otra actividad")
    df_eval = df[df["bolsa_kpi"].ne("Otra actividad")].copy()
    if df_eval.empty:
        empty = pd.DataFrame()
        return {"summary": {}, "groups": empty, "detail": empty, "top_positive": empty, "top_negative": empty}

    groups = (
        df_eval.groupby("bolsa_kpi", as_index=False)
        .agg(
            dias_actividad=("fecha", "count"),
            actividades=("n_actividades", "sum"),
            tiendas=("tienda_codigo", "nunique"),
            venta_dia=("venta_dia", "sum"),
            unidades_dia=("unidades_dia", "sum"),
            dias_con_venta=("actividad_con_venta", lambda s: (s == "Sí").sum()),
            uplift_estimado=("diferencia_vs_referencia", "sum"),
            promedio_referencia=("promedio_referencia", "mean"),
        )
    )
    groups["dias_con_venta_pct"] = np.where(groups["dias_actividad"] > 0, groups["dias_con_venta"] / groups["dias_actividad"] * 100, 0)
    groups["venta_promedio_dia"] = np.where(groups["dias_actividad"] > 0, groups["venta_dia"] / groups["dias_actividad"], 0)
    groups["uplift_pct"] = np.where(groups["promedio_referencia"] > 0, groups["uplift_estimado"] / (groups["promedio_referencia"] * groups["dias_actividad"]) * 100, 0)

    def row_for(label: str) -> dict:
        row = groups[groups["bolsa_kpi"].eq(label)]
        return row.iloc[0].to_dict() if not row.empty else {}

    summary = {
        "seb_activacion": row_for("Sebastián activación PM/L-V"),
        "seb_visita": row_for("Sebastián visita comercial"),
        "agencia_sabado": row_for("Agencia sábado"),
        "venta_total_actividades": float(df_eval["venta_dia"].sum()),
        "uplift_total": float(df_eval["diferencia_vs_referencia"].sum()),
        "dias_actividad_total": int(df_eval["fecha"].nunique()),
        "tiendas_total": int(df_eval["tienda_codigo"].nunique()),
    }
    top_positive = df_eval.sort_values("diferencia_vs_referencia", ascending=False).head(20)
    top_negative = df_eval.sort_values("diferencia_vs_referencia", ascending=True).head(20)
    return {"summary": summary, "groups": groups, "detail": df_eval, "top_positive": top_positive, "top_negative": top_negative}


def visit_information_kpis(visits: pd.DataFrame) -> dict[str, pd.DataFrame | dict]:
    if visits is None or visits.empty:
        return {"summary": {}, "by_store": pd.DataFrame(), "pending": pd.DataFrame(), "detail": pd.DataFrame()}
    df = visits.copy()
    total = len(df)
    summary = {
        "visitas_registradas": int(total),
        "tiendas_visitadas": int(df["tienda_codigo"].replace("", np.nan).nunique()) if "tienda_codigo" in df.columns else int(df["tienda"].nunique()),
        "completitud_promedio": float(df.get("completitud_pct", pd.Series([0])).mean()),
        "fichas_alta_calidad": int((df.get("calidad_ficha", pd.Series(dtype=str)) == "Alta").sum()),
        "fichas_media_calidad": int((df.get("calidad_ficha", pd.Series(dtype=str)) == "Media").sum()),
        "fichas_baja_calidad": int((df.get("calidad_ficha", pd.Series(dtype=str)) == "Baja").sum()),
        "quiebres_detectados": int(df.get("quiebres_detectados", pd.Series([0])).sum()),
        "riesgos_detectados": int(df.get("riesgos_detectados", pd.Series([0])).sum()),
        "sobrestock_detectado": int(df.get("sobrestock_detectado", pd.Series([0])).sum()),
        "pendientes": int(df.get("tiene_pendiente", pd.Series([False])).sum()),
        "con_fotos": int(df.get("tiene_fotos", pd.Series([False])).sum()),
        "vendedores_clave": int(df.get("tiene_vendedor_clave", pd.Series([False])).sum()),
        "conoce_magicshine": int(df.get("conoce_magicshine_si", pd.Series([False])).sum()),
    }
    group_cols = [c for c in ["tienda_codigo", "tienda", "comuna"] if c in df.columns]
    by_store = pd.DataFrame()
    if group_cols:
        by_store = (
            df.groupby(group_cols, as_index=False)
            .agg(
                visitas=("fecha", "count"),
                ultima_visita=("fecha", "max"),
                completitud_promedio=("completitud_pct", "mean"),
                quiebres=("quiebres_detectados", "sum"),
                riesgos=("riesgos_detectados", "sum"),
                sobrestock=("sobrestock_detectado", "sum"),
                pendientes=("tiene_pendiente", "sum"),
                con_fotos=("tiene_fotos", "sum"),
            )
            .sort_values(["pendientes", "quiebres", "riesgos", "visitas"], ascending=False)
        )
    pending = df[df.get("tiene_pendiente", pd.Series([False] * len(df))).astype(bool)].copy()
    if not pending.empty:
        pending = pending.sort_values("fecha", ascending=False)
    return {"summary": summary, "by_store": by_store, "pending": pending, "detail": df}


def content_kpis(content: pd.DataFrame) -> dict[str, pd.DataFrame | dict]:
    if content is None or content.empty:
        return {"summary": {}, "by_type": pd.DataFrame(), "detail": pd.DataFrame()}
    df = content.copy()
    summary = {
        "piezas": int(len(df)),
        "tiendas": int(df["tienda"].replace("", np.nan).nunique()) if "tienda" in df.columns else 0,
        "entregadas": int(df.get("entregado_bool", pd.Series([False] * len(df))).sum()),
        "aprobadas": int(df.get("aprobado_bool", pd.Series([False] * len(df))).sum()),
        "aprobacion_pct": safe_div(int(df.get("aprobado_bool", pd.Series([False] * len(df))).sum()), len(df)) * 100,
    }
    by_type = pd.DataFrame()
    if "tipo_contenido" in df.columns:
        by_type = (
            df.groupby("tipo_contenido", as_index=False)
            .agg(piezas=("fecha", "count"), aprobadas=("aprobado_bool", "sum"), entregadas=("entregado_bool", "sum"), tiendas=("tienda", "nunique"))
            .sort_values("piezas", ascending=False)
        )
    return {"summary": summary, "by_type": by_type, "detail": df}
