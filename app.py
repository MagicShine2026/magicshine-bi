from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import APP_NAME, MODULE_NAME, VERSION, BRAND_COLOR, DARK_COLOR, ACCENT_COLOR
from utils.data_engine import build_master_dataset
from utils import analytics as an

# Import defensivo: evita que una diferencia entre app.py y utils/analytics.py deje la app caída.
def _empty_df(*args, **kwargs):
    return pd.DataFrame()

def _empty_list(*args, **kwargs):
    return []

def _empty_scorecard(*args, **kwargs):
    return {"summary": {}, "weekly": pd.DataFrame(), "by_store": pd.DataFrame(), "detail": pd.DataFrame()}

WEEKDAY_ORDER = getattr(an, "WEEKDAY_ORDER", ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"])
activation_impact_monthly = getattr(an, "activation_impact_monthly", _empty_df)
activation_summary = getattr(an, "activation_summary", _empty_df)
basic_diagnosis = getattr(an, "basic_diagnosis", _empty_list)
category_summary = getattr(an, "category_summary", _empty_df)
daily_sales = getattr(an, "daily_sales", _empty_df)
field_visit_kpis = getattr(an, "field_visit_kpis", _empty_scorecard)
store_activation_effect = getattr(an, "store_activation_effect", _empty_df)
activation_calendar_matrix = getattr(an, "activation_calendar_matrix", _empty_df)
activity_day_impact = getattr(an, "activity_day_impact", _empty_df)
activity_day_summary = getattr(an, "activity_day_summary", lambda impact: {})
activity_day_by_executor = getattr(an, "activity_day_by_executor", _empty_df)
activity_day_by_store = getattr(an, "activity_day_by_store", _empty_df)
product_sales_on_activity_days = getattr(an, "product_sales_on_activity_days", _empty_df)
sebastian_commercial_impact = getattr(an, "sebastian_commercial_impact", lambda impact: {"summary": {}, "groups": pd.DataFrame(), "detail": pd.DataFrame(), "top_positive": pd.DataFrame(), "top_negative": pd.DataFrame()})
visit_information_kpis = getattr(an, "visit_information_kpis", lambda visits: {"summary": {}, "by_store": pd.DataFrame(), "pending": pd.DataFrame(), "detail": pd.DataFrame()})
content_kpis = getattr(an, "content_kpis", lambda content: {"summary": {}, "by_type": pd.DataFrame(), "detail": pd.DataFrame()})
sebastian_scorecard = getattr(an, "sebastian_scorecard", _empty_scorecard)
executive_action_plan = getattr(an, "executive_action_plan", _empty_list)
growth_by_store = getattr(an, "growth_by_store", _empty_df)
integer = getattr(an, "integer", lambda value: str(value))
kpi_summary = getattr(an, "kpi_summary", lambda df: {})
latest_month_comparison = getattr(an, "latest_month_comparison", lambda df: {})
money = getattr(an, "money", lambda value: str(value))
monthly_summary = getattr(an, "monthly_summary", _empty_df)
pct = getattr(an, "pct", lambda value: str(value))
product_ranking = getattr(an, "product_ranking", _empty_df)
store_ranking = getattr(an, "store_ranking", _empty_df)
weekday_ranking = getattr(an, "weekday_ranking", _empty_df)

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
    """Renderiza una tarjeta KPI sin saltos/indentación que Streamlit pueda interpretar como código."""
    trend_html = ""
    if trend is not None:
        cls = "kpi-positive" if positive else "kpi-negative" if positive is False else "kpi-note"
        trend_html = f'<div class="{cls}">{trend}</div>'
    html = (
        f'<div class="ms-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{trend_html}'
        f'<div class="kpi-note">{note}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


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
def load_data_cached(sellout_files, promoter_file, visits_file, content_file):
    return build_master_dataset(sellout_files, promoter_file, visits_file, content_file)


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
    visits_file = st.file_uploader(
        "Ficha visitas / información comercial",
        type=["xlsx", "xls"],
        accept_multiple_files=False,
        help="Plantilla de visitas de Sebastián. Se procesa en memoria y no se guarda en la nube.",
    )
    content_file = st.file_uploader(
        "Contenido terreno (opcional)",
        type=["xlsx", "xls"],
        accept_multiple_files=False,
        help="Planilla simple: Fecha, Tienda, Tipo contenido, Link, Estado, Aprobado. También puede venir como hoja Contenido en la ficha de visitas.",
    )
    st.divider()
    st.caption("Los archivos se procesan en memoria. No se guardan en GitHub ni en el repositorio.")

if not sellout_files:
    st.info("Sube los archivos de Sell Out para construir la tabla maestra.")
    st.markdown(
        """
        ### Magic Shine BI · Impacto Sebastián
        Esta versión mantiene el motor ETL y agrega análisis comercial para gestión del canal Autoplanet.

        **Incluye:**
        - KPIs ejecutivos y variación mensual.
        - Gráficos de venta diaria, venta mensual, tienda, producto y categoría.
        - Ranking de tiendas, productos, días y crecimiento.
        - Análisis de activaciones y visitas.
        - Evaluación de Sebastián en 3 familias: Sell Out, contenido e información comercial.
        """
    )
    st.stop()

with st.spinner("Procesando archivos y construyendo dashboard ejecutivo..."):
    result = load_data_cached(sellout_files, promoter_file, visits_file, content_file)

master = result["master"]
activations = result["activaciones"]
visits = result.get("visitas", pd.DataFrame())
content = result.get("contenido", pd.DataFrame())
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

    selected_activation = st.multiselect("Activación ejecutada", ["Sí", "No"], default=[])

    activity_names = sorted([x for x in master["activacion_nombre"].dropna().unique().tolist() if x])
    selected_activity = st.multiselect("Detalle actividad", activity_names, default=[])

    executors = sorted([x for x in master.get("ejecutor", pd.Series(dtype=str)).dropna().unique().tolist() if x])
    selected_executors = st.multiselect("Ejecutor", executors, default=[])

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
if selected_executors:
    filtered = filtered[filtered["ejecutor"].isin(selected_executors)]

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

tab_exec, tab_sales, tab_rankings, tab_activation, tab_dayimpact, tab_sebastian, tab_plan, tab_quality, tab_download = st.tabs([
    "📊 Resumen ejecutivo",
    "📈 Ventas",
    "🏆 Rankings",
    "🎯 Activaciones",
    "💰 Impacto comercial",
    "👤 Evaluación Sebastián",
    "🧭 Plan comercial",
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
            ms = ms.copy()
            ms["mes_label"] = ms["mes"].astype(str)
            fig = px.bar(ms, x="mes_label", y="venta", text_auto=".2s", title="Venta mensual")
            fig.update_traces(marker_color=BRAND_COLOR)
            fig.update_layout(
                height=370,
                margin=dict(l=10, r=10, t=60, b=10),
                xaxis_title="Mes",
                xaxis_type="category",
            )
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
            st.markdown("#### Venta con vs sin activación ejecutada")
            st.dataframe(fmt_table(act_summary, money_cols=["venta", "venta_promedio_dia", "venta_unidad"], int_cols=["unidades", "registros", "dias", "tiendas"]), use_container_width=True, hide_index=True)
            fig = px.bar(act_summary, x="activacion", y="venta", text_auto=".2s", title="Venta con vs sin activación ejecutada")
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

        st.markdown("#### Impacto por tienda vs benchmark de tiendas no trabajadas")
        store_effect = store_activation_effect(filtered, activations)
        if store_effect.empty:
            st.info("Se requieren al menos dos meses de venta para estimar uplift por tienda.")
        else:
            c3, c4 = st.columns([1, 1])
            with c3:
                st.markdown("**Top uplift estimado**")
                st.dataframe(
                    fmt_table(
                        store_effect.head(10),
                        money_cols=["venta_anterior", "venta_actual", "var_venta", "venta_esperada", "uplift_estimado"],
                        int_cols=["actividades", "visitas", "activaciones_semana", "activaciones_sabado", "unidades_anterior", "unidades_actual", "var_unidades"],
                        pct_cols=["var_venta_pct", "benchmark_no_trabajadas_pct"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            with c4:
                st.markdown("**Tiendas trabajadas con uplift negativo**")
                neg = store_effect[(store_effect["tienda_trabajada"] == "Sí") & (store_effect["uplift_estimado"] <= 0)].sort_values("uplift_estimado").head(10)
                st.dataframe(
                    fmt_table(
                        neg,
                        money_cols=["venta_anterior", "venta_actual", "var_venta", "venta_esperada", "uplift_estimado"],
                        int_cols=["actividades", "visitas", "activaciones_semana", "activaciones_sabado"],
                        pct_cols=["var_venta_pct", "benchmark_no_trabajadas_pct"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

            plot_df = store_effect.sort_values("uplift_estimado", ascending=False).head(15).sort_values("uplift_estimado")
            if not plot_df.empty:
                fig = px.bar(plot_df, y="tienda", x="uplift_estimado", color="tienda_trabajada", orientation="h", title="Top 15 uplift estimado por tienda")
                fig.update_layout(height=520, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Calendario de actividades")
        cal = activation_calendar_matrix(activations)
        if not cal.empty:
            fig = px.bar(cal, x="fecha", y="actividades", color="actividad_terreno", title="Actividades por fecha y tipo")
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=60, b=10))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Actividades detectadas")
        show = ["fecha", "dia_semana", "tienda_codigo", "tienda_promotores", "comuna", "zona", "activacion_codigo", "activacion_nombre", "tipo_actividad", "estado_actividad", "ejecutor", "horario", "cuenta_activacion", "kpi_sebastian", "kpi_agencia"]
        show = [c for c in show if c in activations.columns]
        st.dataframe(fmt_table(activations[show].sort_values(["fecha", "tienda_codigo"])), use_container_width=True, hide_index=True)


with tab_dayimpact:
    st.subheader("Impacto comercial: actividad vs venta del mismo día")
    st.markdown(
        "<div class='section-note'><b>Lectura:</b> esta pestaña cruza cada actividad registrada con la venta de Magic Shine en la misma tienda y en la misma fecha. No asume causalidad automática; muestra cuánto se vendió ese día y lo compara contra el promedio diario de esa tienda en días sin actividad dentro del mismo mes.</div>",
        unsafe_allow_html=True,
    )

    impact_day = activity_day_impact(filtered, activations)
    if impact_day.empty:
        st.info("No hay actividades válidas para cruzar con ventas del período filtrado.")
    else:
        day_summary = activity_day_summary(impact_day)
        d1, d2, d3, d4, d5, d6 = st.columns(6)
        with d1:
            kpi_card("Días con actividad", integer(day_summary.get("dias_actividad", 0)), "Tienda-fecha únicas")
        with d2:
            kpi_card("Actividades", integer(day_summary.get("actividades", 0)), "Marcas registradas")
        with d3:
            kpi_card("Venta mismo día", money(day_summary.get("venta_dia", 0)), "Sell out en tienda-fecha")
        with d4:
            kpi_card("Unidades mismo día", integer(day_summary.get("unidades_dia", 0)), "Unidades vendidas")
        with d5:
            kpi_card("Venta prom. actividad", money(day_summary.get("venta_promedio_actividad", 0)), "Promedio por tienda-fecha")
        with d6:
            kpi_card("Uplift estimado", money(day_summary.get("uplift_estimado", 0)), f"{pct(day_summary.get('uplift_pct', 0))} vs referencia")

        if day_summary.get("uplift_estimado", 0) > 0:
            st.success("En el período filtrado, los días con actividad venden sobre la referencia estimada de tienda/mes.")
        else:
            st.warning("En el período filtrado, los días con actividad no superan la referencia estimada de tienda/mes. Revisar ejecución, tienda o mix de productos.")

        c1, c2 = st.columns([1.0, 1.0])
        with c1:
            by_exec = activity_day_by_executor(impact_day)
            st.markdown("#### Venta mismo día por responsable / tipo")
            if by_exec.empty:
                st.info("Sin datos por responsable.")
            else:
                st.dataframe(
                    fmt_table(
                        by_exec,
                        money_cols=["venta_dia", "venta_promedio_actividad", "uplift_estimado"],
                        int_cols=["dias_actividad", "actividades", "unidades_dia"],
                        pct_cols=["dias_con_venta_pct", "uplift_pct"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
                fig = px.bar(by_exec, x="grupo", y="venta_dia", text_auto=".2s", title="Venta el mismo día por grupo")
                fig.update_traces(marker_color=BRAND_COLOR)
                fig.update_layout(height=360, margin=dict(l=10, r=10, t=60, b=10), xaxis_title="")
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("#### Actividades por fecha vs venta mismo día")
            timeline = (
                impact_day.groupby("fecha", as_index=False)
                .agg(venta_dia=("venta_dia", "sum"), actividades=("n_actividades", "sum"), tiendas=("tienda_codigo", "nunique"))
                .sort_values("fecha")
            )
            fig = px.bar(timeline, x="fecha", y="venta_dia", text_auto=".2s", title="Venta en fechas con actividad")
            fig.update_traces(marker_color=ACCENT_COLOR)
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=60, b=10), xaxis_title="Fecha")
            st.plotly_chart(fig, use_container_width=True)

        c3, c4 = st.columns([1.1, 0.9])
        with c3:
            st.markdown("#### Tiendas: actividad vs venta del mismo día")
            by_store_day = activity_day_by_store(impact_day, n=50)
            if by_store_day.empty:
                st.info("Sin datos por tienda.")
            else:
                st.dataframe(
                    fmt_table(
                        by_store_day,
                        money_cols=["venta_dia", "promedio_referencia", "uplift_estimado", "venta_promedio_dia_actividad"],
                        int_cols=["dias_actividad", "actividades", "unidades_dia", "dias_con_venta"],
                        pct_cols=["uplift_pct"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
        with c4:
            st.markdown("#### Productos vendidos en días con actividad")
            prod_act = product_sales_on_activity_days(filtered, impact_day, n=15)
            if prod_act.empty:
                st.info("No hay ventas de producto en días con actividad.")
            else:
                st.dataframe(
                    fmt_table(prod_act, money_cols=["venta"], int_cols=["unidades", "tiendas", "dias_actividad"]),
                    use_container_width=True,
                    hide_index=True,
                )
                fig = px.bar(prod_act.sort_values("venta"), y="producto", x="venta", orientation="h", title="Top productos en días con actividad")
                fig.update_traces(marker_color=BRAND_COLOR)
                fig.update_layout(height=450, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Detalle tienda-fecha")
        detail_cols = [
            "fecha", "dia_semana", "mes", "tienda_codigo", "tienda", "codigos", "detalle_actividad",
            "ejecutores", "tipos_actividad", "n_actividades", "venta_dia", "unidades_dia",
            "promedio_referencia", "diferencia_vs_referencia", "uplift_pct", "lectura",
        ]
        detail_cols = [c for c in detail_cols if c in impact_day.columns]
        st.dataframe(
            fmt_table(
                impact_day[detail_cols].sort_values(["fecha", "tienda_codigo"]),
                money_cols=["venta_dia", "promedio_referencia", "diferencia_vs_referencia"],
                int_cols=["n_actividades", "unidades_dia"],
                pct_cols=["uplift_pct"],
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Descargar impacto tienda-fecha CSV",
            impact_day.to_csv(index=False).encode("utf-8-sig"),
            file_name="impacto_actividad_mismo_dia.csv",
            mime="text/csv",
        )


with tab_sebastian:
    st.subheader("Evaluación Sebastián — 3 familias KPI")
    st.markdown(
        "<div class='section-note'><b>Criterio:</b> la agenda la define gerencia. Por lo tanto, la evaluación no se centra en si la visita estaba programada, sino en si la actividad generó venta, contenido útil e información comercial accionable. Todos los archivos se procesan en memoria: no quedan guardados en GitHub ni en Streamlit.</div>",
        unsafe_allow_html=True,
    )

    impact_day_all = activity_day_impact(filtered, activations)
    commercial = sebastian_commercial_impact(impact_day_all)
    commercial_summary = commercial.get("summary", {}) or {}

    st.markdown("### 1. Sell Out tiendas asignadas — 40%")
    st.caption("Mide venta del mismo día en tienda con actividad vs promedio de la misma tienda en días sin actividad.")

    seb_act = commercial_summary.get("seb_activacion", {}) or {}
    seb_vis = commercial_summary.get("seb_visita", {}) or {}
    ag_sat = commercial_summary.get("agencia_sabado", {}) or {}

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Activaciones Sebastián PM", integer(seb_act.get("dias_actividad", 0)), f"Venta mismo día: {money(seb_act.get('venta_dia', 0))}")
    with c2:
        kpi_card("Uplift activaciones PM", money(seb_act.get("uplift_estimado", 0)), f"{pct(seb_act.get('uplift_pct', 0))} vs referencia", None, seb_act.get("uplift_estimado", 0) >= 0)
    with c3:
        kpi_card("Visitas comerciales", integer(seb_vis.get("dias_actividad", 0)), f"Venta mismo día: {money(seb_vis.get('venta_dia', 0))}")
    with c4:
        kpi_card("Uplift visitas", money(seb_vis.get("uplift_estimado", 0)), f"{pct(seb_vis.get('uplift_pct', 0))} vs referencia", None, seb_vis.get("uplift_estimado", 0) >= 0)

    c5, c6, c7 = st.columns(3)
    with c5:
        kpi_card("Agencia sábados", integer(ag_sat.get("dias_actividad", 0)), f"Venta mismo día: {money(ag_sat.get('venta_dia', 0))}")
    with c6:
        kpi_card("Venta actividades evaluadas", money(commercial_summary.get("venta_total_actividades", 0)), f"{integer(commercial_summary.get('dias_actividad_total', 0))} días con actividad")
    with c7:
        kpi_card("Tiendas impactadas", integer(commercial_summary.get("tiendas_total", 0)), "Locales únicos con actividad evaluada")

    groups = commercial.get("groups", pd.DataFrame())
    if groups is None or groups.empty:
        st.warning("No hay suficientes datos para evaluar actividad vs venta del mismo día. Revisa promotores y sell out cargados.")
    else:
        c8, c9 = st.columns([1.05, 0.95])
        with c8:
            st.markdown("#### Comparativo por tipo de actividad")
            st.dataframe(
                fmt_table(
                    groups,
                    money_cols=["venta_dia", "venta_promedio_dia", "promedio_referencia", "uplift_estimado"],
                    int_cols=["dias_actividad", "actividades", "tiendas", "unidades_dia", "dias_con_venta"],
                    pct_cols=["dias_con_venta_pct", "uplift_pct"],
                ),
                use_container_width=True,
                hide_index=True,
            )
        with c9:
            fig = px.bar(groups, x="bolsa_kpi", y="venta_dia", text_auto=".2s", title="Venta mismo día por bolsa KPI")
            fig.update_traces(marker_color=BRAND_COLOR)
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=60, b=10), xaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

        top_pos = commercial.get("top_positive", pd.DataFrame())
        top_neg = commercial.get("top_negative", pd.DataFrame())
        c10, c11 = st.columns(2)
        detail_cols = ["fecha", "dia_semana", "tienda_codigo", "tienda", "bolsa_kpi", "codigos", "venta_dia", "promedio_referencia", "diferencia_vs_referencia", "uplift_pct", "lectura"]
        with c10:
            st.markdown("#### Mejores resultados actividad → venta")
            if top_pos is not None and not top_pos.empty:
                cols = [c for c in detail_cols if c in top_pos.columns]
                st.dataframe(fmt_table(top_pos[cols], money_cols=["venta_dia", "promedio_referencia", "diferencia_vs_referencia"], pct_cols=["uplift_pct"]), use_container_width=True, hide_index=True)
        with c11:
            st.markdown("#### Actividades a revisar")
            if top_neg is not None and not top_neg.empty:
                cols = [c for c in detail_cols if c in top_neg.columns]
                st.dataframe(fmt_table(top_neg[cols], money_cols=["venta_dia", "promedio_referencia", "diferencia_vs_referencia"], pct_cols=["uplift_pct"]), use_container_width=True, hide_index=True)

    st.divider()

    st.markdown("### 2. Creación de contenido — 30%")
    content_score = content_kpis(content)
    cs = content_score.get("summary", {}) or {}
    if content is None or content.empty:
        st.markdown(
            "<div class='risk-note'><b>Pendiente de carga:</b> este módulo queda preparado. Puedes cargar una planilla separada o una hoja <b>Contenido</b> dentro de la ficha de visitas. Formato: Fecha, Tienda, Tipo contenido, Link, Estado, Aprobado. El archivo se procesa en memoria y no se guarda en la nube.</div>",
            unsafe_allow_html=True,
        )
        st.dataframe(pd.DataFrame([
            {"Fecha": "2026-07-12", "Tienda": "Maipú Norte", "Tipo contenido": "Video", "Link": "https://...", "Estado": "Entregado", "Aprobado": "Sí"},
            {"Fecha": "2026-07-18", "Tienda": "Quilicura", "Tipo contenido": "Entrevista vendedor", "Link": "https://...", "Estado": "Pendiente", "Aprobado": "No"},
        ]), use_container_width=True, hide_index=True)
    else:
        cc1, cc2, cc3, cc4 = st.columns(4)
        with cc1:
            kpi_card("Piezas cargadas", integer(cs.get("piezas", 0)), "Contenido terreno")
        with cc2:
            kpi_card("Entregadas", integer(cs.get("entregadas", 0)), "Estado entregado/listo")
        with cc3:
            kpi_card("Aprobadas", integer(cs.get("aprobadas", 0)), pct(cs.get("aprobacion_pct", 0)))
        with cc4:
            kpi_card("Tiendas con contenido", integer(cs.get("tiendas", 0)), "Locales únicos")
        by_type = content_score.get("by_type", pd.DataFrame())
        if by_type is not None and not by_type.empty:
            st.markdown("#### Contenido por tipo")
            st.dataframe(fmt_table(by_type, int_cols=["piezas", "aprobadas", "entregadas", "tiendas"]), use_container_width=True, hide_index=True)
        st.markdown("#### Detalle contenido")
        st.dataframe(content_score.get("detail", pd.DataFrame()), use_container_width=True, hide_index=True)

    st.divider()

    st.markdown("### 3. Métricas e información comercial — 30%")
    info_score = visit_information_kpis(visits)
    vs = info_score.get("summary", {}) or {}
    if visits is None or visits.empty:
        st.markdown(
            "<div class='risk-note'><b>Pendiente de carga:</b> sube la plantilla de visitas para medir fichas completas, quiebres, riesgos, sobrestock, pendientes, fotos, vendedor clave y conocimiento de Magic Shine.</div>",
            unsafe_allow_html=True,
        )
    else:
        ic1, ic2, ic3, ic4, ic5, ic6 = st.columns(6)
        with ic1:
            kpi_card("Visitas registradas", integer(vs.get("visitas_registradas", 0)), "Fichas cargadas")
        with ic2:
            kpi_card("Tiendas visitadas", integer(vs.get("tiendas_visitadas", 0)), "Locales únicos")
        with ic3:
            kpi_card("Completitud promedio", pct(vs.get("completitud_promedio", 0)), "Calidad de ficha")
        with ic4:
            kpi_card("Quiebres", integer(vs.get("quiebres_detectados", 0)), "Detectados en tienda")
        with ic5:
            kpi_card("Pendientes", integer(vs.get("pendientes", 0)), "Requieren seguimiento")
        with ic6:
            kpi_card("Con fotos", integer(vs.get("con_fotos", 0)), "Evidencia terreno")

        ic7, ic8, ic9, ic10 = st.columns(4)
        with ic7:
            kpi_card("Riesgos", integer(vs.get("riesgos_detectados", 0)), "Levantados")
        with ic8:
            kpi_card("Sobrestock", integer(vs.get("sobrestock_detectado", 0)), "Detectado")
        with ic9:
            kpi_card("Vendedor clave", integer(vs.get("vendedores_clave", 0)), "Identificados")
        with ic10:
            kpi_card("Conoce Magic Shine", integer(vs.get("conoce_magicshine", 0)), "Respuestas positivas")

        st.markdown("#### Tiendas con información comercial")
        by_store_info = info_score.get("by_store", pd.DataFrame())
        if by_store_info is not None and not by_store_info.empty:
            st.dataframe(
                fmt_table(by_store_info, int_cols=["visitas", "quiebres", "riesgos", "sobrestock", "pendientes", "con_fotos"], pct_cols=["completitud_promedio"]),
                use_container_width=True,
                hide_index=True,
            )
        pending = info_score.get("pending", pd.DataFrame())
        if pending is not None and not pending.empty:
            st.markdown("#### Pendientes comerciales")
            cols = [c for c in ["fecha", "tienda_codigo", "tienda", "comuna", "detalle_pendiente", "notas", "quiebres_detectados", "riesgos_detectados"] if c in pending.columns]
            st.dataframe(fmt_table(pending[cols], int_cols=["quiebres_detectados", "riesgos_detectados"]), use_container_width=True, hide_index=True)

    with st.expander("Control operativo secundario: agenda y cumplimiento semanal"):
        score = sebastian_scorecard(activations, filtered)
        fs = score["summary"]
        oc1, oc2, oc3, oc4 = st.columns(4)
        with oc1:
            kpi_card("Activ. Sebastián L-V", integer(fs.get("activaciones_semana", 0)), "Dato operativo, no KPI principal")
        with oc2:
            kpi_card("Visitas", integer(fs.get("visitas", 0)), f"Incluye {integer(fs.get('visitas_con_incentivo', 0))} con incentivo")
        with oc3:
            kpi_card("Agencia sábado", integer(fs.get("activaciones_sabado_agencia", 0)), "Control agencia")
        with oc4:
            kpi_card("Tiendas trabajadas", integer(fs.get("tiendas", 0)), "Locales únicos Sebastián")
        weekly = score["weekly"]
        if not weekly.empty:
            cols = [c for c in ["semana", "estado", "activaciones_sebastian_lun_vie", "visitas", "activaciones_sabado_agencia", "tiendas_trabajadas"] if c in weekly.columns]
            st.dataframe(fmt_table(weekly[cols], int_cols=["activaciones_sebastian_lun_vie", "visitas", "activaciones_sabado_agencia", "tiendas_trabajadas"]), use_container_width=True, hide_index=True)

with tab_plan:
    st.subheader("Plan comercial sugerido")
    plan = executive_action_plan(filtered, activations)
    plan_df = pd.DataFrame(plan)
    st.dataframe(plan_df, use_container_width=True, hide_index=True)

    st.markdown("#### Priorización por tienda")
    effect = store_activation_effect(filtered, activations)
    if effect.empty:
        st.info("Se requieren al menos dos meses para generar priorización por tienda.")
    else:
        priority = effect.sort_values(["accion_sugerida", "uplift_estimado"], ascending=[True, False])
        st.dataframe(
            fmt_table(
                priority,
                money_cols=["venta_anterior", "venta_actual", "var_venta", "venta_esperada", "uplift_estimado"],
                int_cols=["actividades", "visitas", "activaciones_semana", "activaciones_sabado", "unidades_anterior", "unidades_actual", "var_unidades"],
                pct_cols=["var_venta_pct", "benchmark_no_trabajadas_pct"],
            ),
            use_container_width=True,
            hide_index=True,
        )

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
