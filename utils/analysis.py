from __future__ import annotations
import pandas as pd


def executive_findings(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["No hay datos cargados para analizar."]
    findings = []
    total = df["venta"].sum()
    top_store = df.groupby("tienda")["venta"].sum().sort_values(ascending=False).head(1)
    top_product = df.groupby("producto")["venta"].sum().sort_values(ascending=False).head(1)
    if not top_store.empty:
        findings.append(f"La tienda con mayor venta es {top_store.index[0]}, con ${top_store.iloc[0]:,.0f}.")
    if not top_product.empty:
        findings.append(f"El producto líder es {top_product.index[0]}, con ${top_product.iloc[0]:,.0f}.")
    if "activacion" in df.columns:
        act = df.groupby("activacion")["venta"].sum()
        if "Sí" in act.index:
            share = act.get("Sí",0)/total*100 if total else 0
            findings.append(f"Las ventas en días/tiendas con activación representan {share:.1f}% del sell out cargado.")
    monthly = df.groupby("mes")["venta"].sum().sort_index()
    if len(monthly) >= 2:
        prev, curr = monthly.iloc[-2], monthly.iloc[-1]
        if prev:
            findings.append(f"El último mes varía {(curr/prev-1)*100:.1f}% versus el mes anterior.")
    findings.append("Lectura crítica: para atribuir impacto de promotores se debe comparar tiendas activadas contra una línea base comparable, no solo mirar ventas absolutas.")
    return findings


def action_plan(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return []
    actions = [
        "Separar tiendas activadas de no activadas y medir lift por tienda respecto de su propio promedio previo.",
        "Priorizar activaciones en tiendas con alto tráfico y baja conversión relativa, no solo en las que ya venden más.",
        "Revisar quiebres o mix si una tienda cae en unidades pero mantiene venta en pesos.",
        "Definir un KPI semanal: venta incremental por día de promotor y ranking de eficiencia por tienda.",
    ]
    return actions
