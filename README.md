# Magic Shine BI — v0.5.2 Filtro tiendas AP

## Cambio principal

Se aplica el filtro solicitado sobre los archivos de Sell Out antes de cualquier KPI, ranking o comparación:

- Campo base: `Nombre 1`.
- Se conservan solo filas cuyo valor comienza con `AP`.
- Se excluyen canales/logística/subtotales como `Ega-Kat`, `GPlanet Externos`, `Lo Boza`, `Logístico`, `Megalogistica` y `Total general`.
- La fila `Total general` no se usa para validar; los totales se recalculan sumando filas AP filtradas.

## Control de calidad agregado

En la pestaña **Calidad de datos** se agregan:

- `filas_excel`
- `filas_tienda_ap`
- `filas_excluidas_no_ap`
- `valores_excluidos_nombre_1`
- `control_unidades`
- `control_venta`
- `control_calidad`

## Tests de control

- Mayo 2026: 4.780 unidades / $10.576.950
- Junio 2026: 4.715 unidades / $10.604.240

## Instalación

1. Copiar el contenido de esta carpeta sobre `Documents > GitHub > magicshine-bi`.
2. Reemplazar archivos.
3. Commit: `v0.5.2 filtro tiendas AP`
4. Push origin.
