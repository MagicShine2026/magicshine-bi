from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import APP_NAME, MODULE_NAME, VERSION, BRAND_COLOR, DARK_COLOR, ACCENT_COLOR
from utils.data_engine import build_master_dataset
from utils.analytics import (
    WEEKDAY_ORDER,
    activation_impact_monthly,
    activation_summary,
    basic_diagnosis,
    category_summary,
    daily_sales,
    field_visit_kpis,
    growth_by_store,
    integer,
    kpi_summary,
    latest_month_comparison,
    money,
    monthly_summary,
    pct,
    product_ranking,
    store_ranking,
    weekday_ranking,
)

st.set_page_config(page_title=f"{APP_NAME} | {MODULE_NAME}", page_icon="📊", layout="wide")

st.markdown(
    f"""
    <style>
    .main {{background-color:#F7F9FB;}}
    .block-container {{padding-top: 1.2rem; padding-bottom: 2.5rem; max-width: 1500px;}}
    .ms-card {{background:#FFFFFF;border:1px solid #E5E7EB;border-radius:16px;padding:18px;box-shadow:0 1px 5px rgba(15,61,74,0.07);min-height:108px;}}
    .kpi-label {{font-size:12px;color:#6B7280;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:7px;}}
    .kpi-value {{font-size:27px;font-weight:800;color:{DARK_COLOR};line-height:1.1;}}
    .kpi-note {{font-size:12px;color:#9CA3AF;margin-top:7px;}}
    .kpi-positive {{color:#0F766E;font-weight:700;}}
    .kpi-negative {{color:#B91C1C;font-weight:700;}}
    .section-note {{background:#EAF6F5;border-left:5px solid {BRAND_COLOR};padding:14px 18px;border-radius:12px;margin:12px 0 20px 0;}}
    .risk-note {{background:#FFF7ED;border-left:5px solid #F59E0B;padding:14px 18px;border-radius:12px;margin:12px 0 20px 0;}}
    h1, h2, h3 {{color:{DARK_COLOR};}}
    div[data-testid="stMetric"] {{background:#FFFFFF;border:1px solid #E5E7EB;border-radius:16px;padding:16px;}}
    </style>
    """,
    unsafe_allow_html=True,
)


def kpi_card(label: str, value: str, note: str = "", trend: str | None = None, positive: bool | None = None) -> None:
    trend_html = ""
    if trend is not None:
        cls = "kpi-positive" if positive else "kpi-negative" if positive is False else "kpi-note"
        trend_html = f'<div class="{cls}">{trend}</div>'
    st.markdown(
        f"""
        <div class="ms-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {trend_html}
            <div class="kpi-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def fmt_table(df: pd.DataFrame, money_cols: list[str] | None = None, int_cols: list[str] | None = None, pct_cols: list[str] | None = None) -> pd.DataFrame:
    out = df.copy()
    for col in money_cols or []:
        if col in out.columns:
            out[col] = out[col].apply(money)
    for col in int_cols or []:
        if col in out.columns:
            out[col] = out[col].apply(integer)
    for col in pct_cols or []:
        if col in out.columns:
            out[col] = out[col].apply(pct)
    for col in out.select_dtypes(include=["datetime64[ns]"]).columns:
        out[col] = out[col].dt.strftime("%Y-%m-%d")
    return out


@st.cache_data(show_spinner=False)
def load_data_cached(sellout_files, promoter_file):
    return build_master_dataset(sellout_files, promoter_file)


st.title(APP_NAME)
st.caption(f"{MODULE_NAME} · {VERSION}")

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
        ### Módulo 2: Dashboard Ejecutivo
        Esta versión mantiene el motor ETL y agrega análisis comercial para gestión del canal Autoplanet.

        **Incluye:**
        - KPIs ejecutivos y variación mensual.
        - Gráficos de venta diaria, venta mensual, tienda, producto y categoría.
        - Ranking de tiendas, productos, días y crecimiento.
        - Análisis de activaciones y visitas.
        - Primer marco de KPIs para Sebastián / trabajo en terreno.
        """
    )
    st.stop()

with st.spinner("Procesando archivos y construyendo dashboard ejecutivo..."):
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

    products = sorted(master["producto"].dropna().unique().tolist())
    selected_products = st.multiselect("Producto", products, default=[])

    selected_weekdays = st.multiselect("Día semana", WEEKDAY_ORDER, default=[])

    selected_activation = st.multiselect("Activación", ["Sí", "No"], default=[])

    activity_names = sorted([x for x in master["activacion_nombre"].dropna().unique().tolist() if x])
    selected_activity = st.multiselect("Tipo actividad", activity_names, default=[])

filtered = master.copy()
if selected_months:
    filtered = filtered[filtered["mes"].isin(selected_months)]
if selected_stores:
    filtered = filtered[filtered["tienda"].isin(selected_stores)]
if selected_categories:
    filtered = filtered[filtered["categoria"].isin(selected_categories)]
if selected_products:
    filtered = filtered[filtered["producto"].isin(selected_products)]
if selected_weekdays:
    filtered = filtered[filtered["dia_semana"].isin(selected_weekdays)]
if selected_activation:
    filtered = filtered[filtered["activacion"].isin(selected_activation)]
if selected_activity:
    filtered = filtered[filtered["activacion_nombre"].isin(selected_activity)]

summary = kpi_summary(filtered)
comparison = latest_month_comparison(filtered)

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    trend = f"{money(comparison.get('var_venta', 0))} / {pct(comparison.get('var_venta_pct', 0))}" if comparison.get("mes_anterior") else ""
    kpi_card("Venta total", money(summary["venta"]), "Sell out $ filtrado", trend or None, comparison.get("var_venta", 0) >= 0)
with k2:
    trend = f"{integer(comparison.get('var_unidades', 0))} / {pct(comparison.get('var_unidades_pct', 0))}" if comparison.get("mes_anterior") else ""
    kpi_card("Unidades", integer(summary["unidades"]), "Unidades vendidas", trend or None, comparison.get("var_unidades", 0) >= 0)
with k3:
    kpi_card("Tiendas", integer(summary["tiendas"]), "Locales con venta")
with k4:
    kpi_card("SKUs", integer(summary["skus"]), "Productos con movimiento")
with k5:
    kpi_card("Venta / unidad", money(summary["venta_unidad"]), "Promedio ponderado")

st.divider()

tab_exec, tab_sales, tab_rankings, tab_activation, tab_sebastian, tab_quality, tab_download = st.tabs([
    "📊 Resumen ejecutivo",
    "📈 Ventas",
    "🏆 Rankings",
    "🎯 Activaciones",
    "👤 KPIs Sebastián",
    "🧱 Calidad de datos",
    "⬇️ Descargas",
])

with tab_exec:
    st.subheader("Resumen ejecutivo")
    notes = basic_diagnosis(filtered, activations)
    st.markdown("<div class='section-note'><b>Lectura automática:</b><br>" + "<br>".join([f"• {n}" for n in notes]) + "</div>", unsafe_allow_html=True)

    c1, c2 = st.columns([1.15, 0.85])
    with c1:
        ms = monthly_summary(filtered)
        if not ms.empty:
            fig = px.bar(ms, x="mes", y="venta", text_auto=".2s", title="Venta mensual")
            fig.update_traces(marker_color=BRAND_COLOR)
            fig.update_layout(height=370, margin=dict(l=10, r=10, t=60, b=10))
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        ws = weekday_ranking(filtered)
        if not ws.empty:
            fig = px.bar(ws, x="dia_semana", y="venta", title="Venta por día de semana", text_auto=".2s")
            fig.update_traces(marker_color=ACCENT_COLOR)
            fig.update_layout(height=370, margin=dict(l=10, r=10, t=60, b=10), xaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        top = store_ranking(filtered, n=10)
        st.markdown("#### Top 10 tiendas")
        st.dataframe(fmt_table(top, money_cols=["venta", "venta_unidad"], int_cols=["unidades", "skus", "dias"]), use_container_width=True, hide_index=True)
    with c4:
        top_p = product_ranking(filtered, n=10)
        st.markdown("#### Top 10 productos")
        st.dataframe(fmt_table(top_p, money_cols=["venta", "venta_unidad"], int_cols=["unidades", "tiendas"]), use_container_width=True, hide_index=True)

with tab_sales:
    st.subheader("Ventas")
    d = daily_sales(filtered)
    if not d.empty:
        fig = px.line(d, x="fecha", y="venta", markers=True, title="Evolución diaria de ventas")
        fig.update_traces(line_color=BRAND_COLOR)
        fig.update_layout(height=390, margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        store = store_ranking(filtered, n=15).sort_values("venta")
        fig = px.bar(store, y="tienda", x="venta", orientation="h", title="Top 15 tiendas por venta")
        fig.update_traces(marker_color=BRAND_COLOR)
        fig.update_layout(height=520, margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        prod = product_ranking(filtered, n=15).sort_values("venta")
        fig = px.bar(prod, y="producto", x="venta", orientation="h", title="Top 15 productos por venta")
        fig.update_traces(marker_color=BRAND_COLOR)
        fig.update_layout(height=520, margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig, use_container_width=True)

    cats = category_summary(filtered)
    if not cats.empty:
        fig = px.treemap(cats, path=["categoria"], values="venta", color="venta", title="Venta por categoría")
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig, use_container_width=True)

with tab_rankings:
    st.subheader("Rankings comerciales")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Top 10 tiendas")
        st.dataframe(fmt_table(store_ranking(filtered, n=10), money_cols=["venta", "venta_unidad"], int_cols=["unidades", "skus", "dias"]), use_container_width=True, hide_index=True)
    with c2:
        st.markdown("#### Bottom 10 tiendas con venta")
        bottom = store_ranking(filtered[filtered["venta"] > 0], ascending=True, n=10)
        st.dataframe(fmt_table(bottom, money_cols=["venta", "venta_unidad"], int_cols=["unidades", "skus", "dias"]), use_container_width=True, hide_index=True)

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("#### Top 10 productos")
        st.dataframe(fmt_table(product_ranking(filtered, n=10), money_cols=["venta", "venta_unidad"], int_cols=["unidades", "tiendas"]), use_container_width=True, hide_index=True)
    with c4:
        st.markdown("#### Ranking día de semana")
        st.dataframe(fmt_table(weekday_ranking(filtered), money_cols=["venta", "venta_promedio_dia"], int_cols=["unidades", "dias"]), use_container_width=True, hide_index=True)

    growth = growth_by_store(filtered)
    if not growth.empty:
        st.markdown("#### Crecimiento por tienda vs mes anterior")
        gtop = growth.sort_values("var_venta", ascending=False).head(15)
        fig = px.bar(gtop.sort_values("var_venta"), y="tienda", x="var_venta", orientation="h", title="Top crecimiento $ por tienda")
        fig.update_traces(marker_color=BRAND_COLOR)
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(fmt_table(growth.sort_values("var_venta", ascending=False), money_cols=["venta_anterior", "venta_actual", "var_venta"], int_cols=["unidades_anterior", "unidades_actual", "var_unidades"], pct_cols=["var_venta_pct"]), use_container_width=True, hide_index=True)

with tab_activation:
    st.subheader("Activaciones y visitas")
    if activations.empty:
        st.warning("No se cargó archivo de promotores o no se detectaron activaciones.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            act_summary = activation_summary(filtered)
            st.markdown("#### Venta con vs sin actividad")
            st.dataframe(fmt_table(act_summary, money_cols=["venta", "venta_promedio_dia", "venta_unidad"], int_cols=["unidades", "registros", "dias", "tiendas"]), use_container_width=True, hide_index=True)
            fig = px.bar(act_summary, x="activacion", y="venta", text_auto=".2s", title="Venta con vs sin activación/visita")
            fig.update_traces(marker_color=BRAND_COLOR)
            fig.update_layout(height=360)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            impact = activation_impact_monthly(filtered, activations)
            st.markdown("#### Impacto mensual: tiendas trabajadas vs no trabajadas")
            if impact.empty:
                st.info("Se requieren al menos dos meses de sell out para calcular impacto mensual.")
            else:
                st.dataframe(fmt_table(impact, money_cols=["venta_anterior", "venta_actual", "var_venta"], int_cols=["unidades_anterior", "unidades_actual", "var_unidades"], pct_cols=["var_venta_pct"]), use_container_width=True, hide_index=True)
                fig = px.bar(impact, x="grupo", y="var_venta_pct", text="var_venta_pct", title="Variación % por grupo")
                fig.update_traces(marker_color=ACCENT_COLOR, texttemplate="%{text:.1f}%")
                fig.update_layout(height=360)
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Actividades detectadas")
        show = ["fecha", "dia_semana", "tienda_codigo", "tienda_promotores", "comuna", "zona", "activacion_codigo", "activacion_nombre", "detalle_archivo", "horario_archivo"]
        st.dataframe(fmt_table(activations[show].sort_values(["fecha", "tienda_codigo"])), use_container_width=True, hide_index=True)

with tab_sebastian:
    st.subheader("KPIs Sebastián / trabajo en terreno")
    st.markdown(
        "<div class='risk-note'><b>Nota operacional:</b> el archivo actual no trae una columna explícita de responsable/promotor. "
        "Por ahora esta pestaña mide trabajo de terreno usando códigos de actividad: VC/VCG/G como visita comercial y MS/AM/PM como activación. "
        "Para medir 100% a Sebastián, el próximo archivo debe incluir columna <b>Responsable</b> o <b>Ejecutor</b>.</div>",
        unsafe_allow_html=True,
    )
    field = field_visit_kpis(activations, filtered)
    fs = field["summary"]
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi_card("Visitas comerciales", integer(fs["visitas"]), "Códigos VC / VCG / G")
    with c2:
        kpi_card("Activaciones semana", integer(fs["activaciones_semana"]), "Excluye sábados")
    with c3:
        kpi_card("Activaciones sábado", integer(fs["activaciones_sabado"]), "Normalmente agencia / sábado")
    with c4:
        kpi_card("Tiendas trabajadas", integer(fs["tiendas"]), "Locales únicos")
    with c5:
        compliance = f"{fs['semanas_ok']} / {fs['semanas_total']}"
        kpi_card("Semanas cumplen mínimo", compliance, "Meta: 4 activaciones semanales sin sábado", None, None)

    st.markdown("#### Cumplimiento semanal")
    weekly = field["weekly"]
    if weekly.empty:
        st.info("No hay actividades para medir.")
    else:
        st.dataframe(fmt_table(weekly, int_cols=["visitas", "activaciones_semana", "activaciones_sabado", "tiendas", "actividades"]), use_container_width=True, hide_index=True)
        fig = px.bar(weekly, x="semana", y=["visitas", "activaciones_semana", "activaciones_sabado"], barmode="group", title="Actividades por semana")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Tiendas trabajadas y venta asociada")
    by_store = field["by_store"]
    if not by_store.empty:
        st.dataframe(fmt_table(by_store, money_cols=["venta"], int_cols=["visitas", "activaciones_semana", "activaciones_sabado", "actividades", "unidades"]), use_container_width=True, hide_index=True)

    st.markdown("#### KPIs pendientes de incorporar con nueva fuente")
    st.write("Contenido generado, bases de datos captadas, capacitación a vendedores, levantamiento de oportunidades y supervisión cualitativa requieren un archivo adicional de reporte de terreno.")

with tab_quality:
    st.subheader("Calidad de datos")
    if not quality.empty:
        display_quality = quality.copy()
        st.dataframe(fmt_table(display_quality, money_cols=["venta_total"], int_cols=["unidades_total", "filas_excel", "registros_generados", "tiendas", "skus", "filas_omitidas"]), use_container_width=True, hide_index=True)
    else:
        st.warning("No hay reporte de calidad disponible.")

    st.subheader("Incidencias")
    if issues.empty:
        st.success("No se detectaron errores críticos de lectura.")
    else:
        st.dataframe(issues, use_container_width=True, hide_index=True)

    st.subheader("Tabla maestra")
    show_cols = ["fecha", "mes", "dia_semana", "tienda_codigo", "tienda", "categoria", "sku", "producto", "unidades", "venta", "activacion", "activacion_codigo", "activacion_nombre"]
    st.dataframe(fmt_table(filtered[show_cols].sort_values(["fecha", "tienda_codigo", "producto"]), money_cols=["venta"], int_cols=["unidades"]), use_container_width=True, hide_index=True)

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
