from __future__ import annotations

import numpy as np
import pandas as pd

WEEKDAY_ORDER = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
WEEKDAY_MAP = {day: i for i, day in enumerate(WEEKDAY_ORDER)}

FIELD_VISIT_CODES = {"VC", "VCG", "G"}
ACTIVATION_CODES = {"MS", "AM", "PM"}
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
    active_stores = set(activations[activations["mes"].eq(curr_month)]["tienda_codigo"].dropna().unique())
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


def classify_field_activity(code: str, weekday: str) -> str:
    code = str(code or "").upper().strip()
    if code in FIELD_VISIT_CODES:
        return "Visita comercial"
    if code in ACTIVATION_CODES and weekday != "Sábado":
        return "Activación terreno semana"
    if code in SATURDAY_CODES and weekday == "Sábado":
        return "Activación sábado"
    if "CERR" in code:
        return "Tienda cerrada"
    if code:
        return "Otra actividad"
    return "Sin actividad"


def field_visit_kpis(activations: pd.DataFrame, sales: pd.DataFrame | None = None) -> dict[str, pd.DataFrame | dict]:
    if activations is None or activations.empty:
        return {
            "summary": {"visitas": 0, "activaciones_semana": 0, "activaciones_sabado": 0, "tiendas": 0, "semanas_ok": 0, "semanas_total": 0},
            "weekly": pd.DataFrame(),
            "by_store": pd.DataFrame(),
            "detail": pd.DataFrame(),
        }
    act = activations.copy()
    act["fecha"] = pd.to_datetime(act["fecha"]).dt.normalize()
    act["actividad_terreno"] = act.apply(lambda r: classify_field_activity(r.get("activacion_codigo", ""), r.get("dia_semana", "")), axis=1)
    act["semana"] = act["fecha"].dt.to_period("W-MON").astype(str)
    act["es_visita"] = act["actividad_terreno"].eq("Visita comercial")
    act["es_activacion_semana"] = act["actividad_terreno"].eq("Activación terreno semana")
    act["es_activacion_sabado"] = act["actividad_terreno"].eq("Activación sábado")

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
