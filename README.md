# Exportador de indicadores SQL a plantilla Excel

Llena automáticamente la hoja `DJ` de la plantilla Excel de cada institución
con los valores calculados por el catálogo de indicadores SQL `MAGIK.PLACONSU`.

Estado actual: **Fase 0 y Fase 1 completas** (descubrimiento/setup, y mapa de
configuración indicador → celda). Fases 2-5 según
`prompt_proyecto_exportador_indicadores.md`.

## Instalación

```
pip install -r requirements.txt
```

## Respuestas a las preguntas abiertas de la Fase 0

### Motor y driver de base de datos

Confirmado contra el entorno real: **Microsoft SQL Server 2022 Express**
(instancia `Ryzen7PC\SQLEXPRESS`, base `MAGIK`). No es Informix ni DB2.

- Driver: `pyodbc` con `ODBC Driver 17 for SQL Server` (ya instalado en la
  máquina de desarrollo; `ODBC Driver 18` también está disponible).
- Autenticación: **integrada de Windows** (`Trusted_Connection=yes`), sin
  usuario/clave. Se verificó conectando directamente contra la instancia real.
- Cadena de conexión de referencia:
  `DRIVER={ODBC Driver 17 for SQL Server};SERVER=Ryzen7PC\SQLEXPRESS;DATABASE=MAGIK;Trusted_Connection=yes;`

### Esquema de `PLACONSU`

- Columnas reales: `PLASQLID` (**float**, no `int` — hay que castear/validar
  al usarlo como clave), `PLASQLNOM`, `PLASQLDESC` (`nvarchar(255)`),
  `PLASQLSENT` (`nvarchar(max)`).
- **No tiene columna de institución.** El catálogo no está filtrado por fila
  por institución: cada base de datos (`MAGIK`) pertenece a una sola
  institución. Esto se confirma también en la plantilla Excel real, que trae
  la institución como dato fijo en la celda `DJ!B6` (`INSTITUCIÓN: SMI`). El
  filtro `arid in (...)` embebido en `PLASQLSENT` no es un filtro de
  institución: `arid` son IDs de artículo/prestación específicos de cada
  indicador, no de institución.
- **Hallazgo no anticipado por el prompt**: la tabla tiene 4496 filas pero
  solo 2248 valores distintos de `PLASQLID`. Cada uno está duplicado
  exactamente una vez (mismo `PLASQLNOM`, `PLASQLDESC` y `PLASQLSENT`,
  carácter por carácter). `catalog_repository.py` (Fase 2) debe deduplicar
  antes de armar el `UNION ALL`, si no el query consolidado fallaría o
  duplicaría resultados.

### Formato de credenciales de conexión

`.env` (ver `config/.env.example`), cargado con `python-dotenv`. Variables:
`DB_SERVER`, `DB_DATABASE`, `DB_TRUSTED_CONNECTION`, `DB_USER`, `DB_PASSWORD`
(vacías por defecto porque se usa autenticación integrada), `DB_ODBC_DRIVER`.

## Decisiones de diseño (no cubiertas explícitamente en el prompt)

- **La plantilla real es `.xls` binario legado (BIFF8/OLE2), no `.xlsx`.**
  `openpyxl` no puede leer ni escribir ese formato. Se resolvió con el usuario:
  cada plantilla maestra se convierte **una sola vez** a `.xlsx` con
  `scripts/convert_xls_to_xlsx.py` (usa automatización COM de Excel vía
  `pywin32`, requiere Excel instalado **solo para correr ese script puntual**,
  no para el pipeline de exportación). De ahí en adelante todo el proyecto
  (Fases 1-5) trabaja exclusivamente con `.xlsx` y `openpyxl` puro, sin
  depender de Excel instalado en el servidor que corra las exportaciones
  mensuales. `pywin32` y `xlrd` NO están en `requirements.txt` porque no los
  usa el pipeline, solo ese script de conversión ocasional.
- **Verificación de escritura sobre hoja protegida (pendiente marcada en la
  decisión 5 del prompt): resuelto.** Se probó contra la plantilla real
  convertida: `openpyxl` escribe valores en celdas de una hoja con
  `protection.sheet = True` **sin necesitar la contraseña**, y el archivo
  resultante conserva la protección, el hash de contraseña, el
  `number_format` original y las celdas combinadas intactas. La contraseña de
  protección (decisión 5 del prompt, variable `SHEET_PROTECTION_PASSWORD` en
  `.env`) queda disponible por si a futuro hiciera falta desproteger/proteger
  explícitamente, pero **no es necesaria para el flujo normal de escritura**.
- **Estructura real de la hoja `DJ`** (para referencia de las Fases 1 y 3):
  encabezados en la fila 11 — columna `A` = concepto (con celdas combinadas
  horizontales y verticales según el concepto), `F` = "valor máximo
  autorizado", `G:V` = 16 columnas "PRECIO 1..16" bajo el bloque `NO FONASA`
  (fila 9), `W:AL` = las mismas 16 columnas bajo `FONASA`. Datos de conceptos
  desde la fila 12 hasta la 238 (~230 filas, con secciones intercaladas sin
  valores, ej. "MEDICAMENTOS", "CONSULTAS"). Todos los valores son estáticos
  (`HasFormula = False`), no fórmulas, lo que simplifica la escritura.
- **`templates/<institucion>/` se agrega como convención de carpeta** (no
  estaba en la arquitectura original de la sección 4) para alojar las
  plantillas `.xlsx` ya convertidas por institución, separadas del archivo
  `.xls` original de producción. Ninguna de las dos se commitea (ver
  `.gitignore`).
- Se inicializó un repositorio git local para el proyecto; **no se hizo ningún
  commit todavía** (se hace solo cuando el usuario lo pida explícitamente).
- **`config/indicator_map.csv` (Fase 1) es un CSV de ejemplo con 8 filas**,
  usando `plasqlid` reales del catálogo (`147`, `420`, `819`, etc.) pero con
  celdas de la hoja `DJ` **ilustrativas, no verificadas contra el mapeo real**
  usuario-a-usuario de la plantilla. Poblar las ~750 filas reales queda para
  cuando se arme el mapeo definitivo junto con el usuario (no es parte del
  entregable de Fase 1, según el propio prompt).
- **Duplicados de `plasqlid` en `indicator_map.csv`**: solo se rechaza cuando
  el mismo `plasqlid`, para la misma `institucion_id`, apunta a **celdas
  distintas** (mapeo ambiguo). Una fila repetida exactamente igual (mismo
  `plasqlid`+`institucion_id`+`celda`) no se considera error: es redundante
  pero no ambigua, así que se tolera y ambas filas quedan cargadas.
- El formato de celda (`^[A-Z]+[0-9]+$`) se valida tal cual viene en el CSV,
  **sin normalizar mayúsculas/minúsculas**: `g22` se rechaza igual que `22G`.
  Se prefirió explícito sobre indulgente, en línea con la regla transversal
  de "fallar rápido y explícito".

## Estructura del proyecto

Ver `prompt_proyecto_exportador_indicadores.md`, sección 4, para la
arquitectura completa planeada. El detalle de `config/indicator_map.csv` y
`config/institutions.yaml` se define en la Fase 1.

## Cómo correr una exportación

Pendiente de Fase 4 (`cli.py`).

## Cómo leer el log de control

Pendiente de Fase 4 (`control_log.py`).
