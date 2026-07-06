from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import APP_NAME, MODULE_NAME, BRAND_COLOR, DARK_COLOR
from utils.loader import read_sellout_files, read_promoters_file, enrich_with_activations
from utils.kpi import summarize, month_growth, top_table
from utils.analysis import executive_findings, action_plan

st.set_page_config(page_title=f"{APP_NAME} | {MODULE_NAME}", layout="wide", page_icon="📊")

st.markdown(
    f"""
    <style>
    .main {{background-color:#F7F9FB;}}
    .block-container {{padding-top: 1.5rem;}}
    .kpi-card {{background:white;border:1px solid #E5E7EB;border-radius:16px;padding:18px;box-shadow:0 1px 4px rgba(0,0,0,0.04);}}
    .kpi-label {{font-size:13px;color:#6B7280;margin-bottom:4px;}}
    .kpi-value {{font-size:27px;font-weight:750;color:{DARK_COLOR};}}
    .section-card {{background:white;border:1px solid #E5E7EB;border-radius:16px;padding:18px;margin-top:12px;}}
    h1, h2, h3 {{color:{DARK_COLOR};}}
    </style>
    """,
    unsafe_allow_html=True,
)


def money(x):
    return f"${x:,.0f}".replace(",", ".")


def num(x):
    return f"{x:,.0f}".replace(",", ".")


def kpi_card(label, value, help_text=""):
    st.markdown(
        f"""
        <div class='kpi-card'>
          <div class='kpi-label'>{label}</div>
          <div class='kpi-value'>{value}</div>
          <div style='font-size:12px;color:#9CA3AF'>{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.title("Magic Shine BI — Autoplanet")
st.caption("Dashboard de sell out y activaciones. Sprint 1: carga de datos, KPIs, rankings y lectura ejecutiva.")

with st.sidebar:
    st.header("📂 Carga de archivos")
    sellout_files = st.file_uploader(
        "Sube archivos Sell Out Autoplanet",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        help="Ejemplo: Sell out 05.2026.xlsx, Sell out 06.2026.xlsx",
    )
    promoter_file = st.file_uploader(
        "Sube archivo de promotores / activaciones",
        type=["xlsx", "xls"],
        accept_multiple_files=False,
    )
    st.divider()
    st.caption("Los Excel se procesan en memoria. No quedan guardados en GitHub.")

if not sellout_files:
    st.info("Sube uno o más archivos de sell out para iniciar el análisis.")
    st.markdown("""
    ### Flujo recomendado
    1. Sube los sell out mensuales desde mayo en adelante.
    2. Sube el archivo de promotores.
    3. Revisa KPIs, rankings e impacto de activaciones.

    **Importante:** esta versión no guarda datos. Cada vez que abras la app deberás cargar los Excel de análisis.
    """)
    st.stop()

try:
    sales, errors = read_sellout_files(sellout_files)
except Exception as exc:
    st.error(f"No pude procesar los archivos de sell out: {exc}")
    st.stop()

activations = pd.DataFrame()
if promoter_file:
    try:
        activations = read_promoters_file(promoter_file)
    except Exception as exc:
        st.warning(f"No pude leer el archivo de promotores: {exc}")

sales = enrich_with_activations(sales, activations)

if errors:
    with st.expander("Advertencias de carga"):
        for err in errors:
            st.warning(err)

with st.sidebar:
    st.header("🔎 Filtros")
    months = sorted(sales["mes"].dropna().unique())
    sel_months = st.multiselect("Mes", months, default=months)
    stores = sorted(sales["tienda"].dropna().unique())
    sel_stores = st.multiselect("Tienda", stores, default=[])
    categories = sorted(sales["categoria"].dropna().unique())
    sel_categories = st.multiselect("Categoría", categories, default=[])
    weekdays = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
    sel_weekdays = st.multiselect("Día semana", weekdays, default=[])
    act_filter = st.multiselect("Activación", ["Sí", "No"], default=[])

filtered = sales.copy()
if sel_months:
    filtered = filtered[filtered["mes"].isin(sel_months)]
if sel_stores:
    filtered = filtered[filtered["tienda"].isin(sel_stores)]
if sel_categories:
    filtered = filtered[filtered["categoria"].isin(sel_categories)]
if sel_weekdays:
    filtered = filtered[filtered["dia_semana"].isin(sel_weekdays)]
if act_filter:
    filtered = filtered[filtered["activacion"].isin(act_filter)]

summary = summarize(filtered)
growth = month_growth(filtered)

c1, c2, c3, c4, c5 = st.columns(5)
with c1: kpi_card("Venta total", money(summary["venta"]))
with c2: kpi_card("Unidades", num(summary["unidades"]))
with c3: kpi_card("Tiendas", num(summary["tiendas"]))
with c4: kpi_card("SKUs", num(summary["skus"]))
with c5: kpi_card("Var. último mes", "—" if growth is None else f"{growth:.1f}%")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["📈 Resumen", "🏪 Rankings", "🎯 Activaciones", "🤖 Lectura ejecutiva"])

with tab1:
    left, right = st.columns([1.15, 1])
    with left:
        monthly = filtered.groupby("mes", as_index=False).agg(venta=("venta","sum"), unidades=("unidades","sum"))
        fig = px.bar(monthly, x="mes", y="venta", text_auto=".2s", title="Venta por mes")
        fig.update_layout(height=390, margin=dict(l=10,r=10,t=60,b=10))
        st.plotly_chart(fig, use_container_width=True)
    with right:
        daily = filtered.groupby("fecha", as_index=False).agg(venta=("venta","sum"), unidades=("unidades","sum"))
        fig = px.line(daily, x="fecha", y="venta", markers=True, title="Venta diaria")
        fig.update_layout(height=390, margin=dict(l=10,r=10,t=60,b=10))
        st.plotly_chart(fig, use_container_width=True)

    cat = filtered.groupby("categoria", as_index=False).agg(venta=("venta","sum"), unidades=("unidades","sum")).sort_values("venta", ascending=False)
    fig = px.treemap(cat, path=["categoria"], values="venta", title="Mix por categoría")
    fig.update_layout(height=430, margin=dict(l=10,r=10,t=60,b=10))
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    a, b = st.columns(2)
    with a:
        st.subheader("Top tiendas")
        top_stores = top_table(filtered, "tienda", 10)
        st.dataframe(top_stores, use_container_width=True, hide_index=True)
        fig = px.bar(top_stores.sort_values("venta"), y="tienda", x="venta", orientation="h", title="Top 10 tiendas por venta")
        fig.update_layout(height=430)
        st.plotly_chart(fig, use_container_width=True)
    with b:
        st.subheader("Top productos")
        top_products = top_table(filtered, "producto", 10)
        st.dataframe(top_products, use_container_width=True, hide_index=True)
        fig = px.bar(top_products.sort_values("venta"), y="producto", x="venta", orientation="h", title="Top 10 productos por venta")
        fig.update_layout(height=430)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Ranking por día de semana")
    day_rank = filtered.groupby("dia_semana", as_index=False).agg(venta=("venta","sum"), unidades=("unidades","sum"))
    day_rank["orden"] = day_rank["dia_semana"].map({d:i for i,d in enumerate(weekdays)})
    day_rank = day_rank.sort_values("venta", ascending=False).drop(columns="orden")
    st.dataframe(day_rank, use_container_width=True, hide_index=True)

with tab3:
    if activations.empty:
        st.warning("Sube el archivo de promotores para medir activaciones.")
    else:
        st.subheader("Ventas con vs sin activación")
        act_summary = filtered.groupby("activacion", as_index=False).agg(venta=("venta","sum"), unidades=("unidades","sum"), dias=("fecha","nunique"))
        act_summary["venta_promedio_dia"] = act_summary["venta"] / act_summary["dias"].replace(0, pd.NA)
        st.dataframe(act_summary, use_container_width=True, hide_index=True)
        fig = px.bar(act_summary, x="activacion", y="venta", text_auto=".2s", title="Venta en días/tiendas con y sin activación")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Calendario de activaciones detectadas")
        st.dataframe(activations.sort_values(["fecha", "tienda"]), use_container_width=True, hide_index=True)

with tab4:
    st.subheader("Lectura ejecutiva automática")
    st.markdown("### Hallazgos")
    for item in executive_findings(filtered):
        st.markdown(f"- {item}")
    st.markdown("### Acciones recomendadas")
    for item in action_plan(filtered):
        st.markdown(f"- {item}")

st.divider()
st.download_button(
    "Descargar datos normalizados CSV",
    data=filtered.to_csv(index=False).encode("utf-8-sig"),
    file_name="magicshine_autoplanet_normalizado.csv",
    mime="text/csv",
)
