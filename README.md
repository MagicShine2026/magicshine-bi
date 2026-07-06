# Magic Shine BI

**Módulo:** Retail Intelligence · Autoplanet  
**Versión:** v0.1 ETL

Esta versión contiene el primer módulo funcional: motor de carga, normalización y control de calidad de datos para Sell Out Autoplanet y activaciones/promotores.

## Qué hace esta versión

- Carga múltiples archivos Excel de Sell Out desde la interfaz de Streamlit.
- Detecta automáticamente mes y año del archivo.
- Encuentra la fila de encabezado aunque el reporte tenga portada o filas iniciales distintas.
- Convierte la matriz diaria de Autoplanet a una tabla analítica en formato largo.
- Carga el archivo de promotores/activaciones.
- Cruza ventas y activaciones por `tienda_codigo + fecha`.
- Muestra control de calidad de la carga.
- Permite descargar la tabla maestra normalizada en CSV.

## Estructura

```text
magicshine-bi/
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
│   └── config.toml
├── data/
│   └── .gitkeep
└── utils/
    ├── __init__.py
    └── data_engine.py
```

## Publicación en Streamlit

Configuración recomendada:

| Campo | Valor |
|---|---|
| Repository | `MagicShine2026/magicshine-bi` |
| Branch | `main` |
| Main file path | `app.py` |

## Seguridad de datos

No subas los Excel comerciales al repositorio. La app usa carga directa desde navegador y procesa los archivos en memoria.

El `.gitignore` está configurado para evitar subir archivos `.xlsx`, `.xls` y `.xlsm`.

## Próximo módulo

v0.2: Dashboard ejecutivo y análisis comparativo Mayo vs Junio con rankings comerciales.
