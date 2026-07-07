# Magic Shine BI — v0.5 Impacto Sebastián

Versión enfocada en evaluar a Sebastián según las 3 familias KPI del cargo:

1. **Sell Out tiendas asignadas (40%)**
   - Activación PM / lunes-viernes Sebastián vs venta del mismo día.
   - Visita comercial Sebastián vs venta del mismo día.
   - Activación sábado Agencia como benchmark separado.
   - Comparación contra promedio de la misma tienda en días sin actividad.

2. **Creación de contenido (30%)**
   - Módulo preparado para cargar una planilla simple: `Fecha`, `Tienda`, `Tipo contenido`, `Link`, `Estado`, `Aprobado`.
   - También puede venir como hoja `Contenido` dentro de la plantilla de visitas.
   - Los archivos se procesan en memoria y no se guardan en GitHub ni en Streamlit.

3. **Métricas e información comercial (30%)**
   - Lectura de la plantilla de visitas de Sebastián.
   - KPIs de fichas completas, tiendas visitadas, quiebres, riesgos, sobrestock, pendientes, fotos, vendedor clave y conocimiento Magic Shine.

## Archivos confidenciales

No subir Excel reales al repositorio. El dashboard los recibe desde la interfaz de Streamlit y los procesa en memoria.


## v0.5.1

- Renombra el grupo “Tiendas sin activación/visita” a “Tiendas sin acciones” para mejorar la lectura comercial del análisis comparativo.
