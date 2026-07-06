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


def field_visit_kpis(activations: pd.DataFrame, sales: pd.DataFrame | None = None) -> dict[str, pd.DataFrame | dict]:
    if activations is None or activations.empty:
        return {
            "summary": {"visitas": 0, "activaciones_semana": 0, "activaciones_sabado": 0, "tiendas": 0, "semanas_ok": 0, "semanas_total": 0},
            "weekly": pd.DataFrame(),
            "by_store": pd.DataFrame(),
            "detail": pd.DataFrame(),
        }
    act = valid_activities(activations).copy()
    if act.empty:
        return {"summary": {"visitas": 0, "activaciones_semana": 0, "activaciones_sabado": 0, "tiendas": 0, "semanas_ok": 0, "semanas_total": 0}, "weekly": pd.DataFrame(), "by_store": pd.DataFrame(), "detail": pd.DataFrame()}
    act["fecha"] = pd.to_datetime(act["fecha"]).dt.normalize()
    act["actividad_terreno"] = act.apply(classify_activity_row, axis=1)
    act["semana"] = act["fecha"].dt.to_period("W-MON").astype(str)
    act["es_visita"] = act["actividad_terreno"].str.contains("Visita", na=False) & act.get("kpi_sebastian", "No").astype(str).str.lower().isin(["sí", "si"])
    act["es_activacion_semana"] = act["actividad_terreno"].eq("Activación Sebastián semana")
    act["es_activacion_sabado"] = act["actividad_terreno"].str.contains("Activación", na=False) & act["dia_semana"].eq("Sábado")
    act["es_agencia"] = act.get("ejecutor", "").astype(str).str.lower().str.contains("agencia", na=False)

    weekly = (
        act.groupby("semana", as_index=False)
        .agg(
            visitas=("es_visita", "sum"),
            activaciones_semana=("es_activacion_semana", "sum"),
            activaciones_sabado=("es_activacion_sabado", "sum"),
            tiendas=("tienda_codigo", "nunique"),
            actividades=("tienda_codigo", "count"),
        )
        .sort_values("semana")
    )
    weekly["cumple_min_4_activaciones_semana"] = np.where(weekly["activaciones_semana"] >= 4, "Sí", "No")

    by_store = (
        act.groupby(["tienda_codigo", "tienda_promotores", "comuna", "zona"], as_index=False)
        .agg(
            visitas=("es_visita", "sum"),
            activaciones_semana=("es_activacion_semana", "sum"),
            activaciones_sabado=("es_activacion_sabado", "sum"),
            actividades=("tienda_codigo", "count"),
            primera_fecha=("fecha", "min"),
            ultima_fecha=("fecha", "max"),
        )
        .sort_values("actividades", ascending=False)
    )

    if sales is not None and not sales.empty:
        sales_by_store = sales.groupby("tienda_codigo", as_index=False).agg(venta=("venta", "sum"), unidades=("unidades", "sum"))
        by_store = by_store.merge(sales_by_store, on="tienda_codigo", how="left").fillna({"venta": 0, "unidades": 0})

    summary = {
        "visitas": int(act["es_visita"].sum()),
        "activaciones_semana": int(act["es_activacion_semana"].sum()),
        "activaciones_sabado": int(act["es_activacion_sabado"].sum()),
        "tiendas": int(act["tienda_codigo"].nunique()),
        "semanas_ok": int((weekly["cumple_min_4_activaciones_semana"] == "Sí").sum()) if not weekly.empty else 0,
        "semanas_total": int(len(weekly)),
        "actividades_total": int(len(act)),
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
    weekly = field["weekly"]
    weeks_total = max(int(fs.get("semanas_total", 0)), 1)
    compliance_rate = int(fs.get("semanas_ok", 0)) / weeks_total * 100 if weeks_total else 0
    if weekly is not None and not weekly.empty and "activaciones_semana" in weekly.columns:
        weekly_target_gap = int((4 - weekly["activaciones_semana"].clip(upper=4)).clip(lower=0).sum())
    else:
        weekly_target_gap = 0

    if compliance_rate >= 80:
        status = "Verde"
    elif compliance_rate >= 50:
        status = "Amarillo"
    else:
        status = "Rojo"

    by_store = field["by_store"]
    top_store = ""
    top_sales = 0
    if by_store is not None and not by_store.empty and "venta" in by_store.columns:
        top = by_store.sort_values("venta", ascending=False).iloc[0]
        top_store = str(top.get("tienda_promotores", ""))
        top_sales = float(top.get("venta", 0))

    summary = {
        **fs,
        "cumplimiento_pct": compliance_rate,
        "brecha_activaciones_semana": weekly_target_gap,
        "estado": status,
        "tienda_top_venta_trabajada": top_store,
        "venta_top_tienda_trabajada": top_sales,
    }
    return {"summary": summary, "weekly": weekly, "by_store": by_store, "detail": field["detail"]}


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
