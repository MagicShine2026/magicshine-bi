from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import APP_NAME, MODULE_NAME, VERSION, BRAND_COLOR, DARK_COLOR
from utils.data_engine import build_master_dataset, kpi_summary

st.set_page_config(page_title=f"{APP_NAME} | {MODULE_NAME}", page_icon="📊", layout="wide")

st.markdown(
    f"""
    <style>
    .main {{background-color:#F7F9FB;}}
    .block-container {{padding-top: 1.2rem; padding-bottom: 2.5rem;}}
    .ms-card {{background:#FFFFFF;border:1px solid #E5E7EB;border-radius:16px;padding:18px;box-shadow:0 1px 4px rgba(15,61,74,0.06);}}
    .kpi-label {{font-size:12px;color:#6B7280;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:6px;}}
    .kpi-value {{font-size:28px;font-weight:800;color:{DARK_COLOR};line-height:1.1;}}
    .kpi-note {{font-size:12px;color:#9CA3AF;margin-top:6px;}}
    .status-ok {{color:#0F766E;font-weight:700;}}
    .status-warn {{color:#B45309;font-weight:700;}}
    .status-error {{color:#B91C1C;font-weight:700;}}
    h1, h2, h3 {{color:{DARK_COLOR};}}
    div[data-testid="stMetric"] {{background:#FFFFFF;border:1px solid #E5E7EB;border-radius:16px;padding:16px;}}
    </style>
    """,
    unsafe_allow_html=True,
)


def money(value: float) -> str:
    return f"${value:,.0f}".replace(",", ".")


def integer(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def kpi_card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="ms-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_data_cached(sellout_files, promoter_file):
    return build_master_dataset(sellout_files, promoter_file)


st.title("Magic Shine BI")
st.caption(f"{MODULE_NAME} · {VERSION} · Motor ETL + vista de control de datos")

with st.sidebar:
    st.header("📂 Carga de datos")
    sellout_files = st.file_uploader(
        "Sell Out Autoplanet",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        help="Sube uno o más archivos mensuales. Ej.: Sell out 05.2026.xlsx, Sell out 06.2026.xlsx",
    )
    promoter_file = st.file_uploader(
        "Promotores / activaciones",
        type=["xlsx", "xls"],
        accept_multiple_files=False,
        help="Archivo de programación de activaciones. Opcional para cargar solo ventas.",
    )
    st.divider()
    st.caption("Los archivos se procesan en memoria. No se guardan en GitHub ni en el repositorio.")

if not sellout_files:
    st.info("Sube los archivos de Sell Out para construir la tabla maestra.")
    st.markdown(
        """
        ### Módulo 1: Motor ETL
        Esta versión se concentra en dejar la base de datos confiable antes de construir más análisis.

        **Qué valida:**
        - Detecta mes y año de cada archivo.
        - Encuentra la fila de encabezado aunque el reporte tenga portada.
        - Convierte la matriz diaria a una tabla analítica.
        - Cruza ventas con activaciones por tienda y fecha.
        - Muestra calidad de datos e incidencias.
        """
    )
    st.stop()

with st.spinner("Procesando archivos y construyendo tabla maestra..."):
    result = load_data_cached(sellout_files, promoter_file)

master = result["master"]
activations = result["activaciones"]
quality = result["calidad"]
issues = result["issues"]

if master.empty:
    st.error("No se pudo construir la tabla maestra. Revisa la sección de incidencias.")
    if not issues.empty:
        st.dataframe(issues, use_container_width=True, hide_index=True)
    st.stop()

# Sidebar filters after successful load.
with st.sidebar:
    st.header("🔎 Filtros")
    months = sorted(master["mes"].dropna().unique().tolist())
    selected_months = st.multiselect("Mes", months, default=months)

    stores = sorted(master["tienda"].dropna().unique().tolist())
    selected_stores = st.multiselect("Tienda", stores, default=[])

    categories = sorted(master["categoria"].dropna().unique().tolist())
    selected_categories = st.multiselect("Categoría", categories, default=[])

    weekdays_order = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    selected_weekdays = st.multiselect("Día semana", weekdays_order, default=[])

    selected_activation = st.multiselect("Activación", ["Sí", "No"], default=[])

filtered = master.copy()
if selected_months:
    filtered = filtered[filtered["mes"].isin(selected_months)]
if selected_stores:
    filtered = filtered[filtered["tienda"].isin(selected_stores)]
if selected_categories:
    filtered = filtered[filtered["categoria"].isin(selected_categories)]
if selected_weekdays:
    filtered = filtered[filtered["dia_semana"].isin(selected_weekdays)]
if selected_activation:
    filtered = filtered[filtered["activacion"].isin(selected_activation)]

summary = kpi_summary(filtered)

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    kpi_card("Venta total", money(summary["venta"]), "Sell out $ filtrado")
with k2:
    kpi_card("Unidades", integer(summary["unidades"]), "Unidades vendidas")
with k3:
    kpi_card("Tiendas", integer(summary["tiendas"]), "Locales con venta")
with k4:
    kpi_card("SKUs", integer(summary["skus"]), "Productos con movimiento")
with k5:
    kpi_card("Venta / unidad", money(summary["ticket"]), "Promedio ponderado")

st.divider()

tab_etl, tab_preview, tab_rankings, tab_activation, tab_download = st.tabs([
    "🧱 Calidad de datos",
    "📋 Tabla maestra",
    "🏆 Primeros rankings",
    "🎯 Cruce activaciones",
    "⬇️ Descargas",
])

with tab_etl:
    st.subheader("Control de carga")
    if not quality.empty:
        display_quality = quality.copy()
        for col in ["venta_total", "unidades_total"]:
            if col in display_quality.columns:
                display_quality[col] = display_quality[col].apply(lambda x: money(x) if pd.notna(x) and col == "venta_total" else integer(x) if pd.notna(x) else "")
        st.dataframe(display_quality, use_container_width=True, hide_index=True)
    else:
        st.warning("No hay reporte de calidad disponible.")

    st.subheader("Incidencias")
    if issues.empty:
        st.success("No se detectaron errores críticos de lectura.")
    else:
        st.dataframe(issues, use_container_width=True, hide_index=True)

    st.subheader("Resumen técnico de la tabla maestra")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros", integer(len(master)))
    c2.metric("Fechas", integer(master["fecha"].nunique()))
    c3.metric("Archivos", integer(master["archivo_origen"].nunique()))
    c4.metric("Activaciones cruzadas", integer((master["activacion"] == "Sí").sum()))

with tab_preview:
    st.subheader("Vista previa de datos normalizados")
    show_cols = [
        "fecha", "mes", "dia_semana", "tienda_codigo", "tienda", "categoria", "sku", "producto",
        "unidades", "venta", "activacion", "activacion_codigo", "activacion_nombre",
    ]
    st.dataframe(filtered[show_cols].sort_values(["fecha", "tienda_codigo", "producto"]), use_container_width=True, hide_index=True)

    st.subheader("Evolución diaria")
    daily = filtered.groupby("fecha", as_index=False).agg(venta=("venta", "sum"), unidades=("unidades", "sum"))
    fig = px.line(daily, x="fecha", y="venta", markers=True, title="Venta diaria filtrada")
    fig.update_traces(line_color=BRAND_COLOR)
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig, use_container_width=True)

with tab_rankings:
    st.subheader("Rankings iniciales")
    r1, r2 = st.columns(2)
    with r1:
        store_rank = (
            filtered.groupby(["tienda_codigo", "tienda"], as_index=False)
            .agg(venta=("venta", "sum"), unidades=("unidades", "sum"), skus=("sku", "nunique"))
            .sort_values("venta", ascending=False)
            .head(10)
        )
        st.markdown("#### Top 10 tiendas")
        st.dataframe(store_rank, use_container_width=True, hide_index=True)
        fig = px.bar(store_rank.sort_values("venta"), y="tienda", x="venta", orientation="h", title="Top tiendas por venta")
        fig.update_traces(marker_color=BRAND_COLOR)
        fig.update_layout(height=430)
        st.plotly_chart(fig, use_container_width=True)
    with r2:
        product_rank = (
            filtered.groupby(["sku", "producto"], as_index=False)
            .agg(venta=("venta", "sum"), unidades=("unidades", "sum"), tiendas=("tienda_codigo", "nunique"))
            .sort_values("venta", ascending=False)
            .head(10)
        )
        st.markdown("#### Top 10 productos")
        st.dataframe(product_rank, use_container_width=True, hide_index=True)
        fig = px.bar(product_rank.sort_values("venta"), y="producto", x="venta", orientation="h", title="Top productos por venta")
        fig.update_traces(marker_color=BRAND_COLOR)
        fig.update_layout(height=430)
        st.plotly_chart(fig, use_container_width=True)

    day_rank = (
        filtered.groupby("dia_semana", as_index=False)
        .agg(venta=("venta", "sum"), unidades=("unidades", "sum"), dias=("fecha", "nunique"))
    )
    day_rank["orden"] = day_rank["dia_semana"].map({day: i for i, day in enumerate(weekdays_order)})
    day_rank["venta_promedio_dia"] = day_rank["venta"] / day_rank["dias"].replace(0, pd.NA)
    day_rank = day_rank.sort_values("venta", ascending=False).drop(columns="orden")
    st.markdown("#### Ranking por día de semana")
    st.dataframe(day_rank, use_container_width=True, hide_index=True)

with tab_activation:
    st.subheader("Cruce ventas + activaciones")
    if activations.empty:
        st.warning("No se cargó archivo de promotores o no se detectaron activaciones.")
    else:
        a1, a2 = st.columns([1, 1])
        with a1:
            act_summary = (
                filtered.groupby("activacion", as_index=False)
                .agg(venta=("venta", "sum"), unidades=("unidades", "sum"), registros=("sku", "count"), dias=("fecha", "nunique"))
            )
            act_summary["venta_promedio_dia"] = act_summary["venta"] / act_summary["dias"].replace(0, pd.NA)
            st.dataframe(act_summary, use_container_width=True, hide_index=True)
        with a2:
            fig = px.bar(act_summary, x="activacion", y="venta", title="Venta con vs sin activación", text_auto=".2s")
            fig.update_traces(marker_color=BRAND_COLOR)
            fig.update_layout(height=360)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Activaciones detectadas")
        st.dataframe(activations.sort_values(["fecha", "tienda_codigo"]), use_container_width=True, hide_index=True)

with tab_download:
    st.subheader("Descargas operativas")
    st.download_button(
        "Descargar tabla maestra CSV",
        data=master.to_csv(index=False).encode("utf-8-sig"),
        file_name="magicshine_bi_tabla_maestra.csv",
        mime="text/csv",
    )
    st.download_button(
        "Descargar datos filtrados CSV",
        data=filtered.to_csv(index=False).encode("utf-8-sig"),
        file_name="magicshine_bi_filtrado.csv",
        mime="text/csv",
    )
    if not activations.empty:
        st.download_button(
            "Descargar activaciones CSV",
            data=activations.to_csv(index=False).encode("utf-8-sig"),
            file_name="magicshine_bi_activaciones.csv",
            mime="text/csv",
        )
