# Interfaz entre pulenta y la web

pulenta (`pulenta/`) y la plataforma web (`sitio/` → `web/`) viven en el
mismo repo. De pulenta queda solo lo que usa el sitio: `scripts/familias.py`
y lo que escribe en `datos/` (la app de análisis de PDF se borró el
05/10/2026; está en el historial de git). Cloudflare publica solo `web/`.
Lo que pasa de un lado al otro son los datos de este archivo y una sola
dependencia de código: `familias.py` de pulenta importa `lematica.py` y
`_rutas.py` del anexo de la matriz (ver abajo). La web no importa nada de
pulenta. Un cambio en cualquiera de estos formatos se anota acá antes de
hacerlo.

## Qué es de cada lado

| Lado | Carpetas | Build / CI | Se publica |
|---|---|---|---|
| web | `sitio/`, `web/`, `wrangler.jsonc` | `publicar.yml` (`sitio/**`), `matriz.yml` | sí, `web/` en p314b.space |
| pulenta | `pulenta/` (`scripts/`, `datos/`) | lo corre `superficie.yml` | no (sus datos entran en `web/` por `parientes.py` y `publicados.py`) |

`datos-lee/` es cuerpo de la autora: lo leen los dos lados, no es de
ninguno.

## De la web a pulenta

`pulenta/scripts/familias.py` (Tanda 1 del plan de pulenta, en el historial)
lee, sin modificar nada:

- `cache-matriz/pasajes.json`: índice de pasajes del cuerpo. Lo arma
  `sitio/matriz/indexar_pasajes.py`; no se versiona (caché de Actions o
  corrida local).
- `cache-matriz/anexo/fechas.json`: fecha de cada obra. Lo arma
  `sitio/matriz/anexo/scripts/fechas.py`.
- `cache-matriz/anexo/estructural.json`: los vectores de la fase 2 del
  anexo. Lo arma `sitio/matriz/anexo/scripts/estructural.py`.
- `sitio/lemas.json`: los lemas de la autora.
- Los módulos `lematica.py` y `_rutas.py` de `sitio/matriz/anexo/scripts/`,
  importados desde ahí (no copiados), para que pulenta lematice igual que
  la matriz.
- El texto original de cada obra (`sitio/obras/*.json` o el `.txt` de
  `datos-lee/`), por la ruta `fuente` que trae `pasajes.json`.

Escribe solo en `pulenta/datos/`: `familias.json`,
`familias-revision.csv` (con columnas vacías para la decisión de la
autora) y `obras.json`. El sitio lee `familias.json` (`sitio/parientes.py`)
y `obras.json` (`sitio/publicados.py`).

## De pulenta a la web

Hoy todo pasa a mano; ningún script de un lado escribe en el otro.

- **`pulenta` en cada obra** (`sitio/obras/<slug>.json`): las métricas de
  una corrida, tipeadas a mano en el uploader (bloque «Métricas de
  pulenta», hoy oculto). Solo el uploader lo escribe y lo lee. Es un objeto
  anidado:

  ```
  pulenta: {
    ocurrencias, tipoUnico, ttr, entropiaNorm,          // totales
    modos:     { secuencial|espacial|vectorial: { clusters, nodosPorCluster,
                                                  entropia, enlaces, criterio } } | null,
    nulo:      { secuencial|espacial|vectorial: { modularidad, azarMedia,
                                                  azarSd, z, conclusion } } | null,
    calibrado: { longMinima, modo, stopwords, ngramas, nodosLim, umbral } | null
  }
  ```

  Cada bloque es `null` si está vacío; si está todo vacío al guardar, el
  campo entero es `null`. Pero el `criterio` del modo vectorial viene
  prellenado y fijo, así que el campo casi nunca queda en `null`: de las
  70 obras que lo traen, 68 tienen solo ese `criterio` y todo lo demás en
  `null`, y 2 (`de-repetir`, `tuyo-siempre-etc`) tienen métricas reales.
  7 obras no traen el campo.
- **`_pulenta` en cada obra**: el índice (`sitio/index.html`) lee este
  otro campo, `{ H, ttr, entropia, config }`, pero hoy nada lo escribe, así
  que siempre llega `null`. Unificarlo con `pulenta` es tarea del hilo de
  complemento. `metricas-pulenta.html` es texto explicativo: no lee ninguno
  de los dos.
- **`evidencia_pulenta`** en los instrumentos de `sitio/subgrafo.json`:
  lista de `{sitio, freq | weight_cluster | cluster_weight_max, incluir}`.
  La usan `recalcular_subgrafo.py` (señal por sitio) y
  `matriz/recalibrar.py` (migración al registro).

Si algún día pulenta exporta estos números sola, lo hace a un archivo en
`pulenta/datos/` con este mismo formato, y la web lo lee de ahí: pulenta
no escribe en `sitio/`.
