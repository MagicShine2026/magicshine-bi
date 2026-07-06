# Magic Shine BI — v0.3.1

Módulo Retail Intelligence · Autoplanet.

## Qué incorpora esta versión

- Lectura de hoja `Diccionario` o `Diccionario_Actividades` dentro del archivo de promotores.
- Clasificación automática de códigos de actividad sin depender de colores de celda.
- Separación entre:
  - Activación Agencia
  - Activación Sebastián
  - Visita Sebastián
  - Visita con incentivo
  - Activación cancelada
  - Tienda cerrada
- KPIs de Sebastián calculados desde el diccionario:
  - Visitas
  - Activaciones de lunes a viernes
  - Activaciones sábado
  - Cumplimiento semanal de 4 activaciones sin contar sábado
- Nuevos campos en la tabla de activaciones:
  - `tipo_actividad`
  - `estado_actividad`
  - `ejecutor`
  - `cuenta_activacion`
  - `kpi_sebastian`
  - `kpi_agencia`
  - `actividad_valida`

## Estructura esperada del archivo de promotores

Hojas aceptadas:

- `Consolidado`
- `Diccionario` o `Diccionario_Actividades`

Columnas mínimas del diccionario:

| Abreviatura | Marca | Detalle | Horario | Ejecutor |
|---|---|---|---|---|
| MS | MagicShine | Activación full día | 10:00 - 18:00 | Agencia |
| MSC | MagicShine | Activación full día programada y cancelada | 10:00 - 18:00 | Agencia |
| MSH | MagicShine | Activación de mediodía | 14:30 - 18:30 | Sebastián |
| MSHG | MagicShine | Activación de mediodía + galletas de regalo | 14:30 - 18:30 | Sebastián |
| VC | MagicShine | Visita comercial |  | Sebastián |
| VCG | MagicShine | Visita comercial + galletas de regalo |  | Sebastián |

## Seguridad

Los Excel se cargan desde la app y se procesan en memoria. No se guardan en GitHub.
