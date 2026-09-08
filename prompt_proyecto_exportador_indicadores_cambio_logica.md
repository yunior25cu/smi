# Prompt: Construcción del proyecto "Exportador de indicadores SQL a plantilla Excel"

Copiá y pegá este documento completo como instrucción inicial para el agente de IA
(Claude Code u otro) que va a construir el proyecto. Contiene el contexto, las
decisiones ya tomadas, la arquitectura, y el plan de trabajo por fases con
criterios de aceptación y tests. No lo resumas ni lo comprimas antes de pasarlo:
el agente necesita todo el detalle para no re-descubrir decisiones que ya están
tomadas.

---

## 1. Contexto del proyecto

Existe una plantilla Excel (`.xls`/`.xlsx`) por institución y por mes, con una hoja
llamada `DJ` que contiene ~230 filas de conceptos de salud y hasta 32 columnas de
valores (16 niveles de precio × 2 bloques NO FONASA / FONASA), más columnas de
"valor máximo autorizado". En total hay **~750 celdas de valor** que hoy se llenan
a mano y que hay que llenar automáticamente con resultados de consultas SQL.

Cada valor a llenar corresponde a un **indicador**, definido en una tabla de
catálogo `MAGIK.PLACONSU` con esta forma:

```sql
SELECT * FROM MAGIK.PLACONSU;
-- Columnas conocidas: PLASQLID (int, PK), PLASQLNOM (nombre corto),
-- PLASQLDESC (descripción), PLASQLSENT (texto de un SELECT con placeholders
-- @AAAA@ y @MM@ para año y mes)
```

Ejemplo de una fila:

```
PLASQLID: 147
PLASQLNOM: 208- H TI NF ANITCONCEPTIVOS DE EMERGENCIA
PLASQLDESC: RECETAS NF ANTICONCEPTIVOS DE EMERGENCIA
PLASQLSENT:
  select sum(dwfrcntr)
  from dwfarrec
  Where dwano = @AAAA@ and dwmes = @MM@
  AND perserid in (1,101)
  and percatid in (select percatid from clascat where (...))
  AND arid in (38334);
```

> **Corrección de especificación (revisión 2, posterior a la primera entrega
> del prompt):** la especificación original decía que el entregable era la
> hoja `DJ`. La parte interesada corrigió esto: **el entregable real es la
> propia hoja `4315 Utilización`**, no `DJ`. Si ya se implementó código contra
> `DJ`, hay que revisarlo a la luz de este cambio antes de seguir. El resto de
> este documento ya está actualizado con la corrección; no queda ningún
> rastro intencional de la versión vieja.

La hoja `4315 Utilización` (**nombre real de la hoja, verificado contra el
archivo: tiene un espacio final —** `"4315 Utilizacion "` **— no asumir que no
lo tiene al abrirla por nombre con `openpyxl`**) tiene, para cada indicador,
un par de columnas contiguas con roles distintos y **no simétricos**:

- **Columna PRECIO** (ej. `G22`): valor administrativo/tarifario ya cargado y
  correcto (ej. `67,76`). **No se escribe nunca. No se modifica bajo ningún
  concepto.** No tiene relación con el resultado de la consulta SQL mensual.
- **Columna ORDENES/TICKET** (ej. `H22`, la columna inmediatamente a la
  derecha de PRECIO): hoy contiene, como *placeholder* temporal usado para
  armar el mapeo a mano, el texto de `PLASQLDESC` (ej.
  `"RECETAS NF ANTICONCEPTIVOS DE EMERGENCIA"`, que corresponde a
  `PLASQLID = 147`). **Esta es la celda que hay que sobrescribir**,
  reemplazando ese texto por el valor numérico resultante de ejecutar el
  `PLASQLSENT` de ese `PLASQLID` para el año/mes pedido. El nombre de columna
  ("ORDENES/TICKET") ya indica su propósito real: es una cantidad, no texto.

En síntesis: **de las ~750 celdas de valor identificadas, la escritura ocurre
únicamente en las columnas ORDENES/TICKET (la mitad del total, ~375 celdas);
las columnas PRECIO son de solo lectura para este proyecto.**

## 2. Decisiones ya tomadas (no las vuelvas a discutir, impleméntalas así)

1. **Lenguaje y librerías**: Python 3.11+, `openpyxl` para leer/escribir Excel,
   `pytest` para tests. El driver de base de datos se define en la Fase 0 (ver
   más abajo) según el motor real.
2. **Clave de matching = `PLASQLID` (numérico), nunca el texto de
   `PLASQLDESC`.** Ya se detectaron descripciones duplicadas y con errores de
   tipeo en el Excel real (ej. "CONTRL DE EMBARAZO K", "ESPECIALISTAS ORDEENS NF
   P2"), así que el texto no es una clave confiable. El mapeo indicador → celda
   se construye una vez, a mano o semi-asistido, y se guarda en un archivo de
   configuración versionado (no se recalcula en cada corrida).
3. **Granularidad de salida**: un archivo Excel de salida por institución y por
   mes/año (no un archivo consolidado con todas las instituciones).
4. **Hoja y celda destino (revisión 2 — reemplaza la especificación
   original):** el entregable es la hoja `4315 Utilización` (no `DJ` — `DJ`
   queda fuera de alcance salvo que el usuario indique lo contrario). Dentro
   de esa hoja, cada indicador se escribe en su celda de la columna
   **ORDENES/TICKET**, reemplazando el texto placeholder que hoy contiene por
   el valor numérico devuelto por el `PLASQLSENT` de su `PLASQLID`. La celda
   de **PRECIO** asociada a ese mismo indicador **nunca se escribe** — debe
   quedar con el mismo valor y formato antes y después de la corrida, byte a
   byte.
5. **La plantilla existente se usa como base de cada corrida**: nunca se genera
   un Excel desde cero con `openpyxl.Workbook()`. Se abre una copia del archivo
   plantilla de esa institución y se escribe encima, preservando formato, celdas
   combinadas y protección de hoja.
6. **La contraseña de protección de hoja la tiene el usuario** y se provee por
   variable de entorno o archivo de configuración local (nunca hardcodeada ni
   commiteada). El detalle de si hace falta desproteger/re-proteger la hoja al
   guardar se resuelve en la Fase 3 (openpyxl puede escribir celdas de una hoja
   protegida sin necesidad de la contraseña, pero hay que verificarlo contra el
   archivo real y documentar el resultado).
7. **Consulta consolidada, no ~375 queries sueltas**: cada `PLASQLSENT` es un
   `SELECT` escalar. Se arma dinámicamente un query único (`UNION ALL` etiquetado
   por `plasqlid`) sustituyendo `@AAAA@`/`@MM@` una sola vez, y se ejecuta una
   sola vez contra la base por corrida.
8. **Nunca fallar en silencio.** Todo indicador del catálogo que no tenga celda
   mapeada, toda celda mapeada cuyo `plasqlid` no exista en el catálogo, todo
   resultado `NULL`/vacío de una consulta, y toda celda ORDENES/TICKET que
   **después de la corrida siga conteniendo texto en vez de un número**
   (señal de que el mapeo no la alcanzó), tiene que quedar registrado en un
   log de control legible por un humano, no solo en logs técnicos.

## 3. Preguntas abiertas que el agente DEBE resolver en la Fase 0, contra el
   entorno real, antes de escribir código de negocio

No asumas respuestas para esto — investigalas o preguntale al usuario:

- **Motor y driver de base de datos.** Los nombres de tabla (`dwfarrec`,
  `clascat`) y la sintaxis sugieren posiblemente Informix, DB2 o similar; no está
  confirmado. Definir el driver Python correspondiente (`pyodbc`, `ibm_db`,
  `jaydebeapi`, etc.) recién cuando se sepa.
- **¿`PLACONSU` tiene una columna de institución?** El filtro `arid in (38334)`
  viene hardcodeado dentro de `PLASQLSENT` en el ejemplo visto, lo que sugiere
  que el catálogo completo ya podría estar filtrado por institución (una fila
  distinta por institución para el "mismo" indicador conceptual), en vez de un
  catálogo único parametrizable por institución. Confirmar el esquema real de la
  tabla antes de diseñar el conector de datos.
- **Formato de credenciales de conexión** (host, puerto, base, usuario/clave o
  autenticación integrada) — definir junto con el usuario el mecanismo de
  configuración (`.env`, archivo `config.ini`, variables de entorno del SO).
- **¿La hoja `DJ` queda completamente fuera de alcance,** o hace falta
  mantenerla generada para algún otro uso aunque ya no sea el entregable
  primario? Confirmar con el usuario antes de decidir si vale la pena
  conservar o eliminar cualquier código ya escrito contra `DJ`.
- **Formato numérico a aplicar en la celda ORDENES/TICKET una vez escrita.**
  Hoy es una celda de texto sin `number_format` numérico. Definir con el
  usuario si el valor siempre es entero (cantidad de órdenes/tickets) o puede
  tener decimales según el indicador, y qué `number_format` aplicar (ej.
  `#,##0` vs `0.00`) — no asumirlo por indicador individual.

## 4. Arquitectura objetivo

```
config/
  institutions.yaml        # instituciones habilitadas: id, nombre, ruta plantilla, hoja destino
  indicator_map.csv        # plasqlid, institucion_id, hoja, celda  (clave real del proyecto)
  .env.example             # variables de conexión y password de hoja (sin valores reales)
tools/
  build_indicator_map.py   # utilidad de un solo uso (ver Fase 1): lee el texto placeholder
                            # que hoy ocupa cada celda ORDENES/TICKET, lo cruza contra
                            # PLACONSU.PLASQLDESC y propone filas de indicator_map.csv para
                            # revisión humana — no se usa en la corrida mensual regular
src/
  db/
    connection.py          # apertura de conexión, a partir de Fase 0
    query_builder.py        # arma el UNION ALL a partir del catálogo + año/mes
    catalog_repository.py   # lee PLACONSU, valida contra indicator_map.csv
  excel/
    template_writer.py      # abre plantilla, escribe valores, preserva formato/protección
    workbook_paths.py       # resuelve institución+mes -> ruta de plantilla y de salida
  core/
    indicator_map.py        # carga y valida config/indicator_map.csv
    run_export.py            # orquestador: junta todo, corre el pipeline completo
    control_log.py           # genera el log de control (huérfanos, nulos, sin mapear)
  cli.py                      # entrypoint: institución + mes/año o rango de meses
gui/
  app.py                      # ventana tkinter, capa de presentación pura sobre run_export.py
  error_messages.py           # traduce excepciones técnicas a mensajes de usuario en lenguaje llano
build/
  exportador.spec             # configuración de PyInstaller para el empaquetado en .exe
tests/
  unit/
  integration/
  fixtures/
    sample_workbook.xlsx     # workbook mínimo de prueba, no el archivo real de producción
requirements.txt
README.md
```

## 5. Plan de trabajo por fases

Trabajá **una fase a la vez**. Al terminar cada fase: correr los tests de esa
fase, mostrar un resumen breve de qué se implementó y qué decisiones tomaste
(sobre todo en la Fase 0), y **esperar confirmación antes de pasar a la
siguiente fase**. No avances varias fases de una sola vez aunque técnicamente
puedas: cada fase es un punto de revisión.

### Fase 0 — Descubrimiento y setup del entorno
- Confirmar motor de base de datos, driver, y forma de autenticación (ver
  sección 3). Si no podés acceder a la base real, documentar explícitamente los
  supuestos que vas a usar y marcarlos como "a validar por el usuario".
- Confirmar si `PLACONSU` tiene columna de institución o si el catálogo ya viene
  pre-filtrado por institución (ver sección 3).
- Crear el repositorio con la estructura de la sección 4 (vacía, con
  `__init__.py` donde corresponda).
- `requirements.txt` inicial: `openpyxl`, `pytest`, `pyyaml`, `python-dotenv`, y
  el driver de DB una vez definido.
- Entregable: repo instalable (`pip install -r requirements.txt` funciona),
  `README.md` con las respuestas a la sección 3.

### Fase 1 — Mapa de configuración (indicador → celda)
- Definir el esquema de `config/indicator_map.csv`: `plasqlid, institucion_id,
  hoja, celda` (ej. `147, SMI, "4315 Utilizacion ", H22` — notar que `celda`
  apunta siempre a la columna ORDENES/TICKET, nunca a la columna PRECIO
  contigua; ver sección 1 y decisión 4).
- Escribir `indicator_map.py`: carga el CSV, valida que no haya `plasqlid`
  duplicado para la misma institución apuntando a celdas distintas, valida
  formato de celda (regex tipo `^[A-Z]+[0-9]+$`).
- Tests unitarios: CSV válido carga bien; CSV con `plasqlid` duplicado falla con
  error claro; celda con formato inválido falla; CSV vacío no rompe el programa
  pero lo señala.
- **`tools/build_indicator_map.py` (recomendado, ahorra armar ~375 direcciones
  de celda a mano):** ya que el texto placeholder que hoy ocupa cada celda
  ORDENES/TICKET es, precisamente, el `PLASQLDESC` del indicador que le
  corresponde, se puede leer la hoja real una sola vez, tomar ese texto de
  cada celda de esa columna, y cruzarlo contra `PLACONSU.PLASQLDESC` para
  proponer automáticamente `(plasqlid, hoja, celda)`. Esto es solo una
  **propuesta para revisión humana**, no un mapeo final automático: ya se
  detectaron descripciones duplicadas (ej. "Medico Referencia" aparece 4
  veces) y con errores de tipeo en el archivo real, así que el resultado de
  esta herramienta debe marcarse explícitamente como "ambiguo" o "sin match"
  cuando corresponda, para que una persona lo revise antes de que ese
  `indicator_map.csv` se use en una corrida real.
- Tests unitarios de `build_indicator_map.py`: dado un catálogo de prueba y un
  workbook de prueba con texto conocido, produce el CSV esperado; un texto
  duplicado en el catálogo se marca como ambiguo, no se resuelve solo; un
  texto sin match en el catálogo se marca como huérfano.
- Entregable: no hace falta poblar las ~375 filas reales todavía — alcanza con
  un CSV de ejemplo de 5-10 filas para los tests de `indicator_map.py`.

### Fase 2 — Capa de acceso a datos
- `catalog_repository.py`: trae el catálogo completo de `PLACONSU` (o el
  subconjunto de una institución, según lo que se haya confirmado en Fase 0).
- `query_builder.py`: dado el catálogo y un año/mes, sustituye `@AAAA@`/`@MM@`
  en cada `PLASQLSENT` y arma un único `SELECT plasqlid, valor FROM (... UNION
  ALL ...)`. Si algún `PLASQLSENT` no es un `SELECT` escalar simple (ej. trae
  varias columnas), debe fallar de forma explícita y clara, no intentar
  adivinar.
- Ejecutar la consulta consolidada y devolver un `dict[int, float | None]`
  (`plasqlid -> valor`).
- Tests unitarios: `query_builder` arma el SQL esperado a partir de un catálogo
  de prueba (sin conexión real); manejo de `PLASQLSENT` malformado.
- Tests de integración (marcados aparte, se saltean si no hay conexión
  disponible en CI): ejecución real contra una base de desarrollo/staging si el
  usuario la provee.

### Fase 3 — Escritura en la plantilla Excel
- `template_writer.py`: abre la plantilla de una institución con `openpyxl`,
  ubica la hoja `4315 Utilización` (**verificar el nombre exacto contra el
  archivo real antes de hardcodearlo — puede incluir un espacio final, como
  en el archivo inspeccionado**), y para cada fila de `indicator_map.csv` de
  esa institución **reemplaza el contenido de la celda ORDENES/TICKET
  indicada** (hoy texto) por el valor numérico del indicador.
- **La celda PRECIO contigua a cada celda escrita no se toca bajo ningún
  concepto** — ni su valor ni su formato. Esto no es un detalle menor: es una
  invariante que los tests de esta fase tienen que verificar explícitamente
  (ver más abajo), no solo asumir.
- Al escribir el valor numérico, aplicar el `number_format` que se haya
  definido con el usuario (ver preguntas abiertas, sección 3) — la celda hoy
  es texto sin formato numérico, así que este paso no puede omitirse ni
  copiarse del formato existente.
- Debe preservar celdas combinadas y el estado de protección de hoja fuera de
  las celdas ORDENES/TICKET explícitamente mapeadas. Documentar en el código y
  en el README qué se verificó respecto a escribir sobre hoja protegida sin
  contraseña.
- **Verificación post-escritura (no opcional):** después de escribir todas las
  celdas del mapa, recorrer la columna ORDENES/TICKET completa de la hoja y
  reportar cualquier celda que siga conteniendo texto en vez de un número —
  esto atrapa tanto indicadores que quedaron sin mapear como errores de
  dirección de celda en el `indicator_map.csv` (ver decisión 8 y Fase 4).
- Nunca modificar el archivo plantilla original: siempre trabajar sobre una
  copia, y el archivo de salida tiene su propio nombre
  (`{institucion}_{AAAA}_{MM}.xlsx`).
- Tests unitarios: usar un workbook de prueba mínimo (`tests/fixtures/`, **no**
  el archivo real de producción) que incluya, para al menos dos indicadores,
  su par de celdas PRECIO + ORDENES/TICKET (esta última con texto placeholder,
  igual que en el archivo real), y verificar que después de escribir:
  (a) las celdas ORDENES/TICKET mapeadas tienen el valor numérico correcto y
  el `number_format` esperado, (b) **las celdas PRECIO quedan con el mismo
  valor y el mismo formato que antes de la corrida, sin excepción**, (c) las
  celdas ORDENES/TICKET no mapeadas conservan su texto original intacto (no se
  blanquean), y (d) la verificación post-escritura detecta correctamente una
  celda ORDENES/TICKET dejada a propósito sin mapear en el fixture de prueba.

### Fase 4 — Orquestador y CLI
- `run_export.py`: dado institución + mes/año (o un rango de meses), corre el
  pipeline completo: cargar mapa → traer catálogo → armar y ejecutar query
  consolidada → escribir plantilla → generar log de control.
- `control_log.py`: genera un reporte (texto o CSV) con cuatro secciones:
  indicadores del catálogo sin celda mapeada, celdas mapeadas cuyo `plasqlid` no
  existe en el catálogo traído, indicadores cuyo resultado fue `NULL`/vacío, y
  celdas ORDENES/TICKET que tras la corrida siguen conteniendo texto en vez de
  un número (ver verificación post-escritura de la Fase 3).
- `cli.py`: comando de línea, ej. `python -m src.cli --institucion SMI --anio
  2026 --mes 8` y variante de rango `--desde 2026-01 --hasta 2026-08`.
- Tests: orquestador probado con catálogo y mapa de prueba y una conexión de
  base mockeada (sin pegarle a una base real), verificando que el log de control
  detecta correctamente los cuatro tipos de discrepancia.

### Fase 5 — Endurecimiento y documentación final
- Logging estructurado (no solo `print`), manejo de errores de conexión con
  mensaje claro, validación de argumentos de CLI.
- `README.md` final: cómo instalar, cómo configurar `.env`, cómo poblar
  `indicator_map.csv` para una institución nueva, cómo correr una exportación,
  cómo leer el log de control.
- Suite de tests corriendo completa con `pytest`, con cobertura razonable de la
  lógica de negocio (no hace falta 100%, pero sí las rutas de error de las
  fases 1 a 4).

### Fase 6 — Interfaz de escritorio y empaquetado (para uso no técnico)

Esta fase es posterior al MVP funcional (Fases 0-5) y tiene un público objetivo
distinto: personal de contable, sin conocimientos técnicos, en Windows, sin
Python instalado y sin acceso a una terminal. No la mezcles con las fases
anteriores ni le agregues lógica de negocio propia — es una capa de
presentación sobre `run_export.py` (Fase 4) y nada más. Si `run_export.py`
cambia de firma para acomodar la GUI, esa lógica va en Fase 4, no acá.

- **Tecnología**: `tkinter` (incluido en la instalación estándar de Python, no
  agrega dependencias nuevas) empaquetado con PyInstaller como
  `--onefile --windowed`.
- **Elementos de la ventana**:
  - Combo desplegable de instituciones, poblado desde `institutions.yaml` (no
    hardcodeado en la GUI).
  - Selectores de mes y año, con opción de rango (desde/hasta).
  - Botón "Generar", deshabilitado hasta que los campos requeridos sean
    válidos (no debe poder clickearse con institución sin seleccionar).
  - Indicador de progreso + texto de estado en lenguaje llano por etapa:
    "Consultando base de datos...", "Escribiendo Excel...", "Listo".
- **Alertas y mensajes** — siempre en lenguaje humano, nunca un stack trace de
  Python en pantalla (el detalle técnico va al log, la ventana solo muestra el
  mensaje traducido):
  - Éxito: mensaje con la ruta del archivo generado y un botón "Abrir carpeta"
    (`os.startfile` en Windows).
  - Error de conexión a la base: mensaje del tipo "No se pudo conectar a la
    base de datos. Avisá a sistemas.", con el detalle técnico real solo en el
    log.
  - Advertencia no bloqueante si el log de control (Fase 4) tiene indicadores
    sin match o con valores nulos: el archivo se genera igual, pero se avisa
    "revisar N indicadores en el log de control" con un botón para abrirlo.
- **`error_messages.py`**: capa dedicada a traducir cada tipo de excepción
  manejada (conexión fallida, archivo de plantilla no encontrado, permiso de
  escritura denegado, celda mapeada inexistente, etc.) a un mensaje de usuario
  fijo y en español llano. Esta capa sí se testea unitariamente — es lógica
  pura, sin UI de por medio.
- **Empaquetado**: PyInstaller `--onefile --windowed`, ícono propio, nombre de
  archivo final claro para quien lo recibe (ej. `ExportadorIndicadores.exe`).
- **Decisión pendiente que el agente NO debe asumir por su cuenta antes de
  escribir el `connection.py` de esta fase**: si el `.exe` se conecta
  directamente a la base de datos (las credenciales viajan y quedan
  accesibles en la máquina de contable) o si le habla a un servicio
  intermedio controlado por el equipo técnico, de forma que la máquina del
  usuario final nunca tenga credenciales de base propias. Dado que el proceso
  maneja datos de salud, esta decisión depende de la infraestructura real de
  la organización — el agente debe preguntarla explícitamente antes de
  implementar la capa de conexión de esta fase, en vez de reusar sin más el
  `connection.py` pensado para uso técnico interno de la Fase 0/2.
- **Notas de plataforma para el README de esta fase**:
  - Windows SmartScreen muy probablemente marque el `.exe` sin firma la
    primera vez que alguien lo ejecute ("Windows protegió su PC") — es
    comportamiento esperado con ejecutables sin firma digital, no un bug.
    Documentar el procedimiento interno para distribuirlo vía software
    aprobado, o la posibilidad de firmarlo si la organización ya tiene
    certificado de firma de código.
  - Forzar `encoding="utf-8"` en toda escritura de archivos (logs, CSV) para
    no depender de la code page de la consola de Windows, dado que hay
    nombres de institución y descripciones con tildes.
- **Tests**: no hace falta cobertura automatizada de los widgets en sí, pero
  sí de `error_messages.py` (cada excepción manejada produce el mensaje
  esperado) y de que el botón "Generar" quede deshabilitado con campos
  incompletos.

## 7. Reglas transversales para todas las fases

- No commitear credenciales, contraseñas ni el archivo Excel real de
  producción. Usar únicamente fixtures sintéticas para tests.
- Cualquier decisión de diseño que tomes por tu cuenta (no cubierta
  explícitamente en este documento) debe quedar anotada en el `README.md` bajo
  una sección "Decisiones de diseño", con una frase de justificación.
- Preferí fallar rápido y explícito sobre asumir silenciosamente.
