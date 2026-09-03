# Exportador de indicadores SQL a plantilla Excel

Llena automáticamente la hoja `DJ` de la plantilla Excel de cada institución
con los valores calculados por el catálogo de indicadores SQL `MAGIK.PLACONSU`.

Estado actual: **Fases 0 a 6 completas** según
`prompt_proyecto_exportador_indicadores interfaz.md` (descubrimiento/setup,
mapa de configuración indicador → celda, capa de acceso a datos, escritura
en la plantilla Excel, orquestador/CLI, endurecimiento/documentación, e
interfaz de escritorio empaquetable). Ver "Pendiente de Fase 2" más abajo:
falta conectar contra el data warehouse real (Oracle, según confirmó el
usuario) — a propósito pospuesto para el final del proyecto, así que
**todavía no se puede correr una exportación real de punta a punta contra
Oracle** (el CLI y la GUI llegan hasta ahí y fallan con un mensaje claro).
Mientras tanto, se validó el pipeline completo de punta a punta contra datos
reales cargados temporalmente en SQL Server (`DWFARREC`/`CLASCAT`, ver
"Prueba real interina contra SQL Server").

## Instalación

```
pip install -r requirements.txt
```

Requiere Python 3.11+ y, para conectar contra SQL Server, el driver ODBC
correspondiente instalado en el sistema (`ODBC Driver 17` o `18 for SQL
Server`; en Windows normalmente ya viene con SQL Server Client Tools, o se
instala aparte). El conector Oracle (pendiente, ver "Pendiente de Fase 2")
va a sumar su propio driver a `requirements.txt` cuando se implemente.

## Cómo configurar `.env`

Copiá `config/.env.example` a `.env` en la raíz del proyecto y completá:

- `DB_SERVER`, `DB_DATABASE`: servidor y base del catálogo (`MAGIK`). Por
  defecto apunta a `Ryzen7PC\SQLEXPRESS`, la instancia usada durante el
  desarrollo.
- `DB_TRUSTED_CONNECTION`: `yes` para autenticación integrada de Windows
  (el caso normal, no hace falta usuario/clave). Poné `no` y completá
  `DB_USER`/`DB_PASSWORD` solo si el servidor requiere autenticación SQL.
- `DB_ODBC_DRIVER`: nombre exacto del driver ODBC instalado (`ODBC Driver 17
  for SQL Server` por defecto).
- `SHEET_PROTECTION_PASSWORD`: no hace falta para el flujo normal (`openpyxl`
  escribe en hojas protegidas sin pedirla, ver más abajo); se deja disponible
  por si a futuro hiciera falta desproteger la hoja explícitamente.

`.env` nunca se commitea (está en `.gitignore`); `.env.example` sí, sin
valores reales de contraseña.

## Cómo poblar `indicator_map.csv` para una institución nueva

1. Agregá la institución en `config/institutions.yaml`: `id` (el mismo que
   vas a usar en `--institucion` del CLI), `nombre`, `plantilla` (ruta al
   `.xlsx` de esa institución — si el archivo real es `.xls`, convertilo
   primero con `python scripts/convert_xls_to_xlsx.py <origen.xls>
   <destino.xlsx>`), y `hoja` (el nombre de la hoja destino, `DJ` en la
   plantilla conocida).
2. Por cada indicador que quieras completar automáticamente, agregá una fila
   a `config/indicator_map.csv`: `plasqlid` (el `PLASQLID` real de
   `MAGIK.PLACONSU`, no el texto de `PLASQLDESC` — ver decisión 2 del
   prompt sobre por qué el texto no es una clave confiable), `institucion_id`
   (el mismo `id` del paso 1), `hoja`, `celda` (ej. `G22`).
3. Corré `load_indicator_map("config/indicator_map.csv")` (o simplemente
   `python -m src.cli ...`, que lo carga al arrancar) para validar el
   archivo: falla explícito si hay una celda con formato inválido o un
   `plasqlid` mapeado a dos celdas distintas para la misma institución.
4. Cualquier indicador del catálogo que quede sin fila en
   `indicator_map.csv` para esa institución no rompe la corrida: aparece
   listado en la sección "Indicadores del catálogo sin celda mapeada" del
   log de control, para completar de a poco.

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
- Se inicializó un repositorio git local para el proyecto (los commits se
  hacen solo cuando el usuario lo pide explícitamente).
- **`config/indicator_map.csv` (Fase 1) arranca chico a propósito, con solo
  mapeos confirmados contra la plantilla real** (no un CSV de ejemplo con
  celdas ilustrativas). Se intentó primero cruzar automáticamente el texto de
  concepto de `DJ` (columna A) contra `PLASQLNOM`/`PLASQLDESC` del catálogo,
  asumiendo -como sugería el prompt- que existía una hoja de referencia
  ("4315 Utilización") con el texto de `PLASQLDESC` al lado de cada celda de
  valor. **Resultó ser falso**: esa hoja, en el archivo real, es solo una
  copia calculada de `DJ` vía fórmulas (`=IF(DJ!G13="","",DJ!G13)`), sin
  ningún texto de referencia adicional. Se probó además cruzar por texto
  directamente: términos como "TICKET" o "CONSULTORIO" (presentes en
  conceptos reales de `DJ`) aparecen **cero veces** en todo `PLASQLNOM`/
  `PLASQLDESC`, confirmando que son dos vocabularios distintos y que no hay
  forma automática confiable de derivar el mapeo. El usuario decidió, en
  consecuencia, ir agregando filas de a una a medida que se confirman contra
  la plantilla real (hoy: `147` → `DJ!G22`), en vez de intentar adivinar
  ~750 celdas por texto.
- **Duplicados de `plasqlid` en `indicator_map.csv`**: solo se rechaza cuando
  el mismo `plasqlid`, para la misma `institucion_id`, apunta a **celdas
  distintas** (mapeo ambiguo). Una fila repetida exactamente igual (mismo
  `plasqlid`+`institucion_id`+`celda`) no se considera error: es redundante
  pero no ambigua, así que se tolera y ambas filas quedan cargadas.
- El formato de celda (`^[A-Z]+[0-9]+$`) se valida tal cual viene en el CSV,
  **sin normalizar mayúsculas/minúsculas**: `g22` se rechaza igual que `22G`.
  Se prefirió explícito sobre indulgente, en línea con la regla transversal
  de "fallar rápido y explícito".

## Pendiente de Fase 2 (necesita respuesta del usuario)

Corriendo la Fase 2 contra el servidor real (`Ryzen7PC\SQLEXPRESS`) aparecieron
dos hallazgos que no estaban previstos en el prompt. Uno ya se resolvió con
el usuario, el otro sigue abierto:

1. **Placeholders `@Servicios@` / `@Servidios@`: resuelto.** Además de
   `@AAAA@`/`@MM@` (documentados) se encontraron `@FHINICIO@`/`@FHFIN@` en 112
   `PLASQLSENT` reales (se resuelven solos: primer/último día del mes) y
   `@Servicios@`/`@Servidios@` (typo real del catálogo) en 20 `PLASQLSENT`,
   en un filtro `PerSerId in (@Servicios@)`. El usuario confirmó que debe
   resolver al mismo filtro hardcodeado en el resto del catálogo:
   `perserid in (1,101)` (ver `DEFAULT_SERVICIOS` en `query_builder.py`).
   Cualquier otro placeholder `@algo@` no documentado sigue fallando con un
   `QueryBuilderError` explícito en vez de adivinarse o mandarse roto al motor.
2. **Dónde vive el data warehouse: motor confirmado (Oracle), conector
   pospuesto a propósito.** La base `MAGIK` en `Ryzen7PC\SQLEXPRESS` tiene
   **una sola tabla: `PLACONSU`**. Las tablas que las `PLASQLSENT` consultan
   (`dwfarrec`, `DWAfilia`, `DWTecOrd`, `clascat`, etc.) no existen en ninguna
   base de ese servidor (se revisaron todas: `MAGIK`, `master`, `Cediyi`,
   `CardProMask`, `balaxys_ecommerce`, `pymeconta_dev`, `pymeconta_local`) ni
   hay servidores vinculados (`sys.servers`) que apunten a otro lado. El
   usuario confirmó que ese data warehouse es **Oracle**. Por decisión
   explícita del usuario, el conector Oracle (driver `oracledb` o similar,
   credenciales, alcance de red) **se deja para el final del proyecto**, después
   de las Fases 3, 4 y 5. Hasta entonces, cualquier ejecución real de
   indicadores contra Oracle sigue sin funcionar (`fetch_indicator_values`
   necesita una conexión DB-API 2.0 real, que todavía no existe para Oracle).
   `catalog_repository.py` y `query_builder.py` ya están escritos de forma
   agnóstica al motor (reciben cualquier conexión DB-API 2.0), así que
   conectar Oracle al final no debería requerir tocarlos.

Ninguno de los dos bloqueaba terminar la Fase 2 (`catalog_repository.py` y
`query_builder.py` están completos y probados, incluso contra el catálogo
real). Las Fases 3 (escritura en la plantilla) y 4 (orquestador) tampoco
dependen del data warehouse: el orquestador de la Fase 4 recibe
`dict[plasqlid, valor]` ya calculado, sin importar de dónde salió.

## Decisiones de diseño de la Fase 3

- **`config/institutions.yaml` se creó en la Fase 3**, no en la Fase 1 (el
  prompt no especificaba en qué fase debía crearse, solo que `indicator_map.csv`
  era el entregable de la Fase 1). `workbook_paths.py` lo necesita para
  resolver la ruta de plantilla de cada institución, así que se creó recién
  cuando hizo falta. Contiene una sola institución (`SMI`), apuntando a
  `templates/SMI/4315 Utilizacion.xlsx` (la plantilla real convertida en
  Fase 0), hoja `DJ`.
- **`tests/fixtures/sample_workbook.xlsx`** se genera con
  `scripts/build_test_fixture.py` (usa `openpyxl.Workbook()` para crear un
  archivo sintético desde cero — no viola la decisión 4 del prompt, que
  prohíbe generar así la plantilla *real* de una corrida, no un fixture de
  test). Tiene una hoja `DJ` con protección de hoja con contraseña real,
  celdas combinadas (`A2:B2`) y `number_format` propio en las celdas de
  valor, para poder probar exactamente los tres puntos que pide la Fase 3.
  Es la única excepción al `*.xlsx` del `.gitignore`.
- **`template_writer.write_values` recibe `dict[celda, valor]` genérico**, no
  objetos `IndicatorMapEntry`/`CatalogEntry`: no necesita saber nada de
  `plasqlid` ni de SQL. Cruzar el mapa de indicadores con los valores
  traídos de la base es responsabilidad del orquestador de la Fase 4, no de
  este módulo — mantiene la escritura de Excel testeable en aislamiento.
- **Un valor `None` se escribe como celda vacía**, no se omite. Decidir qué
  hacer con los indicadores sin resultado (loguearlos, alertar) es trabajo
  del log de control de la Fase 4; `template_writer` simplemente refleja el
  dato que le pasan, sin opinar.
- **Volver a exportar la misma institución/mes sobreescribe el archivo de
  salida** sin pedir confirmación (se considera un caso de uso normal, no un
  error), pero queda un `logger.info` marcando que se sobreescribió.
- Se repitió contra la plantilla real convertida (no solo el fixture) la
  verificación de que `openpyxl` escribe sin pedir la contraseña de
  protección de hoja: valores, `number_format`, celdas combinadas y el
  estado de protección quedan todos intactos.

## Interfaz de escritorio (Fase 6)

Ventana `tkinter` para personal de contable sin conocimientos técnicos, sin
terminal ni Python instalado: capa de presentación pura sobre
`run_export.py`, sin lógica de negocio propia.

**Correr desde código fuente** (para desarrollo/pruebas):
```
python gui/app.py
```

**Uso**: elegir institución del desplegable, año y mes (o tildar "Rango de
meses" y completar "Desde"/"Hasta" en formato `AAAA-MM`). El botón
"Generar" queda deshabilitado hasta que los campos requeridos sean válidos.
Mientras corre, muestra una barra de progreso y el estado en lenguaje llano
("Consultando base de datos...", "Escribiendo Excel..."). Al terminar:
- Si salió bien: mensaje con la ruta del archivo generado y la opción de
  abrir la carpeta de salida.
- Si el log de control encontró discrepancias: además del mensaje anterior,
  ofrece abrir el log de control directamente.
- Si algo falló: mensaje de error en español llano (nunca un stack trace de
  Python en pantalla) — el detalle técnico completo queda en el log.

**Conexión a la base de datos (decisión del usuario, Fase 6)**: el `.exe` se
conecta **directo** a la base, igual que `src/cli.py` — mismas
`connection.py`/`.env`, mismo stub de Oracle mientras siga pendiente. No hay
un servicio intermedio. Esto significa que, en la máquina de quien use el
`.exe`, va a haber credenciales de conexión a una base con datos de salud
(vía `.env` junto al ejecutable). Es una decisión explícita, tomada con el
trade-off conocido a cambio de simplicidad (no hay que construir ni operar
un servicio intermedio).

**Variante interina (`gui/app_test_mssql.py`)**: mientras Oracle no esté
conectado, `gui/app.py` (la interfaz final) muestra "La conexión a la base de
datos de indicadores todavía no está configurada" al generar, tal como está
pensado. Para poder probar la GUI de punta a punta contra datos reales
mientras tanto (igual que `scripts/run_export_test_mssql.py` para el CLI),
existe esta variante: reutiliza `ExportadorApp` sin cambios, solo hace que
`dw_conn` también apunte a SQL Server y usa
`config/indicator_map.test_mssql.csv` en vez del real.

```
python gui/app_test_mssql.py
```
```
pyinstaller build/exportador_test_mssql.spec
```
Genera `dist/ExportadorIndicadores_PRUEBA.exe` (nombre y título de ventana
deliberadamente distintos al `.exe` final, para no confundirlos). Transitorio:
se deja de usar cuando el conector Oracle esté implementado.

### Empaquetado y distribución

```
pip install pyinstaller
pyinstaller build/exportador.spec
```

Genera `dist/ExportadorIndicadores.exe` (probado: abre, carga las
instituciones de `institutions.yaml`, y maneja errores de conexión con el
mensaje traducido correspondiente). El `.exe` **no lleva embebidos**
`config/` ni `templates/`: los resuelve relativos a su propia carpeta (no al
directorio de trabajo actual, que no es controlable por alguien que hace
doble clic), así que hay que copiar `config/`, `templates/` y `.env` **al
lado** del `.exe` antes de distribuirlo. `requirements.txt` no incluye
`pyinstaller` a propósito: es una herramienta de empaquetado puntual, no una
dependencia del pipeline (mismo criterio que con `pywin32`/`xlrd` en la
Fase 0).

**Notas de plataforma**:
- Windows SmartScreen muy probablemente marque el `.exe` sin firma la
  primera vez que alguien lo ejecute ("Windows protegió su PC"). Es el
  comportamiento esperado con un ejecutable sin firma digital, no un bug del
  programa. Para distribuirlo hay que usar el canal de software aprobado de
  la organización, o firmarlo si ya existe un certificado de firma de
  código.
- Toda escritura de archivo del pipeline (`control_log.py`, `indicator_map.py`)
  ya fuerza `encoding="utf-8"` explícito, para no depender de la code page de
  la consola de Windows (relevante: nombres de institución y descripciones
  con tildes).

### Decisiones de diseño de la Fase 6

- **Las funciones de validación (`can_submit`, `is_valid_year`,
  `is_valid_month_number`, `is_valid_year_month`) son puras**, sin ningún
  import de `tkinter`, definidas a nivel de módulo en `gui/app.py`. Permite
  testear la regla "el botón Generar queda deshabilitado con campos
  incompletos" (pedida explícitamente por el prompt) sin instanciar ninguna
  ventana.
- **`run_pipeline()` (en `gui/app.py`) es la única función que abre
  conexiones y corre `run_export`**, separada de la clase `ExportadorApp`:
  se probó tanto en aislamiento (con conexiones reales, incluyendo el camino
  de error del conector Oracle pendiente) como a través de la ventana real
  (simulando un click en "Generar" con los diálogos de `tkinter`
  interceptados, sin bloquear la terminal).
- **La corrida real pasa a un hilo (`threading.Thread`) separado del hilo de
  la interfaz**, con progreso reportado vía una `queue.Queue` que el hilo
  principal consulta con `root.after(...)`. Sin esto, la ventana se congela
  mientras dura la consulta a la base y la escritura del Excel.
- **Rutas por defecto (`config/`, `output/`) relativas a la ubicación del
  propio ejecutable** (`sys.executable` cuando está empaquetado,
  `__file__` cuando corre desde código fuente), no al directorio de trabajo
  actual: se detectó en las pruebas que depender del `cwd` es frágil para
  alguien que abre el `.exe` con doble clic (no elige desde dónde se lanza).
- **`gui/error_messages.py` nunca devuelve el texto crudo de una excepción**:
  cada tipo de error mapeado tiene una frase fija en español llano, y
  cualquier excepción no contemplada cae a un mensaje genérico. El detalle
  técnico completo solo llega al log (`logging`), nunca a un cuadro de
  diálogo.
- **No se probó firmar el `.exe` ni configurar un canal de distribución
  real** (fuera del alcance de este proyecto): queda documentada la
  advertencia de SmartScreen, pero la resolución operativa (firma de código,
  software aprobado interno) depende de la organización.

## Estructura del proyecto

Ver `prompt_proyecto_exportador_indicadores.md`, sección 4, para la
arquitectura completa planeada. El detalle de `config/indicator_map.csv` y
`config/institutions.yaml` se define en la Fase 1.

## Cómo correr una exportación

```
python -m src.cli --institucion SMI --anio 2026 --mes 8
python -m src.cli --institucion SMI --desde 2026-01 --hasta 2026-08
```

Hoy esto llega hasta abrir la conexión al catálogo (SQL Server, funciona) y
falla explícitamente al intentar abrir la conexión al data warehouse
(Oracle, pendiente — ver "Pendiente de Fase 2"). Una vez armado ese
conector, no hace falta tocar nada más de este flujo.

## Prueba real interina contra SQL Server (mientras Oracle no está conectado)

Para validar el pipeline de punta a punta antes de tener el conector Oracle,
se creó `DWFARREC` y `CLASCAT` en la misma base `MAGIK` (SQL Server), con
datos reales, como banco de pruebas temporal. `python -m src.cli` no sirve
para esto: usa el conector Oracle (pendiente) para las consultas de datos.
En su lugar:

```
python scripts/run_export_test_mssql.py --institucion SMI --anio 2026 --mes 5
```

Mismos parámetros que `src.cli` (`--institucion`, `--anio`/`--mes` o
`--desde`/`--hasta`, `--output-dir`, `--log-level`). Este script abre **las
dos conexiones contra SQL Server** (catálogo y "data warehouse" son la misma
base por ahora) y usa `config/indicator_map.test_mssql.csv` en vez de
`config/indicator_map.csv` -ese archivo real todavía tiene indicadores de
ejemplo que apuntan a tablas que no existen (`DWAfilia`, `DWTecOrd`), y
juntarlos todos en la misma corrida rompería la consulta consolidada
completa (una sola tabla faltante frena a todos los indicadores de esa
corrida, por diseño). `indicator_map.test_mssql.csv` solo tiene los dos
indicadores que hoy tienen datos reales cargados (`147` y `94`, ambos sobre
`dwfarrec`).

Es un script transitorio: una vez que el conector Oracle esté implementado y
`indicator_map.csv` tenga el mapeo real completo, se deja de usar y se pasa
a `python -m src.cli` directamente.

## Cómo leer el log de control

Cada corrida genera, junto al `.xlsx` de salida, un archivo
`{institucion}_{AAAA}_{MM}_control.txt` con tres secciones: indicadores del
catálogo sin celda mapeada, celdas mapeadas cuyo `plasqlid` no existe en el
catálogo, e indicadores con resultado `NULL`/vacío. El CLI también lo imprime
por consola y termina con código de salida 1 si hay alguna discrepancia (0 si
no hay ninguna). `src/core/control_log.py` también expone `write_csv()` para
un formato tabular, si hace falta procesarlo con otra herramienta.

## Decisiones de diseño de la Fase 4

- **`run_export` recibe dos conexiones separadas** (`catalog_conn`,
  `dw_conn`), no una sola: el hallazgo de la Fase 2 (catálogo en SQL Server,
  ejecución en Oracle) hace que asumir una única conexión sea directamente
  incorrecto en este proyecto, no una simplificación válida.
- **Solo se ejecuta la query consolidada para los indicadores realmente
  mapeados** en `indicator_map.csv` de esa institución (no los ~2248 del
  catálogo completo): más eficiente, y evita arrastrar problemas de
  indicadores no utilizados (placeholders raros, tablas faltantes) a
  corridas que no los necesitan. El catálogo completo igual se trae siempre,
  porque hace falta para detectar "indicadores sin celda mapeada".
- **"Indicadores sin celda mapeada" se calcula por institución**, no de forma
  global: un indicador mapeado para otra institución en el mismo
  `indicator_map.csv` no cuenta como discrepancia en la corrida de esta.
- **Un plasqlid mapeado dos veces a la misma celda** (fila duplicada exacta,
  tolerada desde la Fase 1) se deduplica antes de armar la query consolidada:
  si no, `query_builder` la rechazaría por ID repetido aunque el mapa sea
  válido.
- **El conector Oracle (`src/db/dw_connection.py`) es un stub que falla
  explícito**, por decisión del usuario de posponerlo. `cli.py` ya está
  escrito contra la interfaz final (abre `catalog_conn` y `dw_conn` por
  separado, se los pasa a `run_export`), así que cuando se implemente el
  conector real alcanza con reemplazar `get_dw_connection()` sin tocar
  `run_export.py`, `control_log.py` ni `template_writer.py`.

## Decisiones de diseño de la Fase 5

- **Logging estructurado con el módulo `logging`**, no solo `print()`:
  `cli.py` configura `logging.basicConfig` con el nivel elegido por
  `--log-level` (default `INFO`); los módulos internos (`connection.py`,
  `template_writer.py`, `catalog_repository.py`) ya venían usando `logging`
  desde fases anteriores. `print()` se reserva para la salida "de producto"
  pensada para el usuario del CLI (ruta del archivo generado, texto del log
  de control), no para diagnóstico.
- **`get_connection()` envuelve los errores de `pyodbc`** (servidor caído,
  credenciales inválidas, driver no instalado) en un `ConnectionConfigError`
  con el servidor y la base a los que se intentó conectar, sin exponer la
  contraseña. El mensaje crudo de `pyodbc` (a veces una sola línea con
  varios códigos de error concatenados) queda igual disponible como `__cause__`
  para quien necesite el detalle técnico completo.
- **`cli.py` distingue errores esperables de bugs reales.** Un conjunto
  acotado de excepciones (`ConnectionConfigError`, `IndicatorMapError`,
  `InstitutionConfigError`, `QueryBuilderError`, `TemplateWriterError`,
  `NotImplementedError` -incluye el conector Oracle pendiente-, `ValueError`
  -incluye argumentos de rango inválidos) se reportan como un mensaje de una
  línea en `stderr` y código de salida `2`, sin traceback. Cualquier otra
  excepción (un bug de verdad) se deja propagar con el traceback completo:
  esconderlo ahí sería peor que mostrarlo.
- **Código de salida del CLI**: `0` sin discrepancias, `1` con discrepancias
  en el log de control pero la corrida terminó bien, `2` si no pudo ni
  empezar (configuración o conexión inválida). Así un script que encadene
  varias corridas puede distinguir "revisar el log" de "esto ni corrió".
- **`--anio`/`--mes`/`--desde`/`--hasta` se validan en el CLI** contra el
  mismo rango (`MIN_ANIO`/`MAX_ANIO`) que usa `query_builder.py`, para fallar
  antes de abrir ninguna conexión en vez de después de haber traído el
  catálogo completo.
- **Cobertura de tests**: 98% de sentencias en `src/` (110 tests, medido con
  `pytest --cov=src --cov-report=term-missing`; no se agregó `pytest-cov` a
  `requirements.txt` porque es una herramienta de diagnóstico puntual, no una
  dependencia del pipeline). Se agregaron tests específicamente para cerrar
  rutas de error que habían quedado sin probar: valores vacíos de
  `institucion_id`/`hoja` en `indicator_map.csv`, el stub del conector
  Oracle, y dos casos límite del parser de `query_builder.py` (un `;` o una
  `,` dentro de un string literal, y una columna cuyo nombre contiene la
  palabra "from" como substring, ej. `fromage`).
