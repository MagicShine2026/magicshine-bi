# Magic Shine BI

**Módulo:** Retail Intelligence · Autoplanet  
**Versión:** v0.2 Dashboard Ejecutivo

Esta versión mantiene el motor ETL de v0.1 y agrega dashboard comercial para análisis ejecutivo de ventas, activaciones y trabajo en terreno.

## Qué incluye

- Carga múltiple de archivos Sell Out Autoplanet desde la interfaz.
- Carga de archivo Promotores / Activaciones.
- Normalización automática de datos.
- KPIs ejecutivos: venta, unidades, tiendas, SKUs, venta/unidad.
- Comparación mensual automática.
- Gráficos de venta mensual, diaria, por tienda, producto, categoría y día de semana.
- Rankings: top tiendas, bottom tiendas, top productos, ranking por día y crecimiento por tienda.
- Cruce con activaciones: venta con/sin actividad y variación mensual de tiendas trabajadas vs no trabajadas.
- Pestaña KPIs Sebastián / trabajo en terreno.
- Control de calidad de datos e incidencias.
- Descargas CSV.

## Seguridad de datos

No subas Excel comerciales al repositorio. La app procesa los archivos en memoria desde el navegador.

El `.gitignore` evita subir archivos `.xlsx`, `.xls` y `.xlsm`.

## Publicación en Streamlit

| Campo | Valor |
|---|---|
| Repository | `MagicShine2026/magicshine-bi` |
| Branch | `main` |
| Main file path | `app.py` |

## Nota sobre KPIs Sebastián

El archivo actual de promotores no trae una columna explícita de responsable. Esta versión mide trabajo de terreno por códigos de actividad:

- `VC`, `VCG`, `G`: visita comercial.
- `MS`, `AM`, `PM` en días distintos de sábado: activación de terreno semana.
- `MS` sábado: activación sábado.

Para atribución directa a Sebastián, el siguiente formato debería incluir una columna `Responsable` o `Ejecutor`.
