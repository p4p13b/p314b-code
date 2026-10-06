# matriz/ — la matriz relacional

La matriz se arma con tus diagonales y tus decisiones. El motor solo propone
cruces; ninguna propuesta es una relación hasta que la aceptás, y ningún script
escribe, completa ni corrige emergentes. El modelo completo está en
`PROPUESTA-MATRIZ.md`.

Todos los comandos se corren desde `sitio/`.

## Qué hay acá

| archivo | qué es | lo escribe |
|---|---|---|
| `config.json` | qué se indexa, backend de embeddings, parámetros, `mostrar_propuestas` | vos |
| `instrumentos.json` | registro único de instrumentos | vos: `etiqueta`, `descripcion`, `alias`, `semilla`. `recalibrar.py`: todo lo que está bajo `calculado` |
| `decisiones.json` | tus decisiones sobre las propuestas | el taller (botón guardar decisiones) |
| `propuestas.json` | propuestas vigentes (estatuto `inferencia-matriz`) | `proponer_cruces.py` |
| `recorridos.json` | recorridos sobre las diagonales | `calcular_recorridos.py` |
| `relaciones.json` | matriz a nivel obra desde la lectura del Cowork (reescritura, menciones en logs, motivos del glosario, secuencia de blogs) | `cowork.py` |
| `propuestas-cowork.json` | sugerencias página a página de esa lectura (estatuto `lectura-cowork`); el taller las muestra junto a las del motor | `cowork.py` |
| `equivalencias.json` | nombres viejos de los textos («Proyecto» → «sí teoría») y, si hace falta, a qué posteo forzar un texto del archivo | vos (la armó Claude con tus respuestas en PREGUNTAS PARA PEPI) |
| `vigencia.json` | qué texto del Cowork vive hoy en qué posteo, papelera ociosa y textos que faltarían subir | `vigencia.py` (lo corre `cowork.py`) |
| `comun.py` | piezas compartidas por los scripts | — |

Fuera de `sitio/`, en la raíz del repo, queda `cache-matriz/`: el índice de
pasajes (`pasajes.json`, con páginas completas de `datos-lee`) y los vectores
ya calculados. Git lo ignora y no se publica. Se puede borrar: se regenera con
los scripts.

## El bucle

1. Escribís diagonales en el taller y las publicás con `generar_obra.py`
   (quedan en `acciones.json`).
2. `python3 matriz/indexar_pasajes.py` arma el índice de pasajes: una página
   por pasaje de cada PDF de `Archivo/manifest.json` que tenga su `.txt` en
   `datos-lee/txt/`, más los posts de las series de `config.json` (`qoq`).
   Corrérlo de nuevo solo cuando cambie eso.
3. `python3 matriz/recalibrar.py` actualiza el registro de instrumentos, con
   sus pesos y umbrales.
4. `python3 matriz/proponer_cruces.py` escribe `propuestas.json`.
5. En el taller, **propuestas de la matriz**: aceptás (con emergente), rechazás
   o retipás cada una. Después **guardar decisiones**: con el token va
   directo a `sitio/matriz/decisiones.json` en el repo (si no, se descarga).
   Si cerrás el taller sin guardar, las decisiones se pierden (el navegador avisa).
6. Otra vez `recalibrar.py` (las decisiones mueven pesos y umbrales) y
   `proponer_cruces.py` (no vuelve a proponer lo decidido ni lo parecido a un
   rechazo).
7. `python3 matriz/calcular_recorridos.py` cada vez que cambian las
   diagonales. `matriz.html` muestra el grafo y los recorridos.

## Automático: el workflow «Matriz»

`.github/workflows/matriz.yml` corre el bucle (índice, `recalibrar.py`,
`proponer_cruces.py` con el modelo de `config.json` y
`calcular_recorridos.py`) todos los días a las 06:23 UTC, cada vez que
entran decisiones nuevas (`decisiones.json`) y a mano, desde Actions →
«Matriz» → Run workflow. Guarda solo `sitio/matriz/`. `cache-matriz/`
queda en la caché de Actions, nunca en el repo.

El universo es todo el cuerpo: los PDF del manifest con su `.txt` en
`datos-lee` (estén o no en línea) y, con `universo.posts_publicados`, todos
los posteos de texto marcados «mostrar en el sitio web».

`matriz.html` (solo para la autora) dibuja, además de las diagonales:

- las **propuestas** (con `mostrar_propuestas: true`), punteadas;
- las **relaciones entre obras de la lectura del Cowork**
  (`relaciones.json`), en ámbar, con un control para ver solo las más
  fuertes.

Cada capa tiene su interruptor.

## Lectura del Cowork (matriz por criterios)

`python3 matriz/cowork.py` (solo Python 3, un par de minutos) lee
`datos-lee/txt`, los informes por dimensión y el glosario de
`datos-lee/cowork`, y las obras de `sitio/obras`. Escribe:

- `relaciones.json`: la matriz entre obras. Cada criterio de los informes
  (tema, género, técnica, estilo, figura, concepto, lateral…) que nombra dos
  obras suma un poco en esa dimensión; se acumulan. También suman la
  reescritura literal y la secuencia de blogs. Incluye la lista de criterios
  con sus palabras ancla y los pares que parecen versiones del mismo texto.
- `propuestas-cowork.json`: sugerencias **desde el cuerpo actual** (posteos
  de texto en línea, o con categoría "cuerpo") hacia el archivo (los PDFs) y
  hacia partes anteriores: por criterio (palabra ancla), tramo literal o
  léxico raro compartido. Entre obras del archivo no se sugiere nada.

Corrélo de nuevo cuando subas partes u obras. El detalle está en el
encabezado del script.

## Nombres de ahora (`vigencia.py`)

Varios textos que lee el Cowork cambiaron de nombre o de forma: «sí teoría»
está en el posteo *pop*, «sí» en *.*, «dos puntos» en *:*, y los PDF de
*Términos y condiciones*, *Ni-ni*, *no teoría*, *potencial*, *De repetir* y
*Tuyo siempre* se ocultaron porque su texto se publicó escrito.
`python3 matriz/vigencia.py` decide, para cada texto de `datos-lee/txt`, en
qué posteo en línea vive (por su nombre, o porque la mitad de su texto está
ahí) o si no vive en ninguno. `cowork.py` e `indexar_pasajes.py` lo usan:
las sugerencias, las relaciones y los pasajes van con el nombre de ahora, y
nada apunta a un texto que no está en el sitio. Los poemarios quedan como
estaban. `equivalencias.json` manda sobre el cálculo.

`vigencia.json` también marca la **papelera ociosa** (lo que se puede borrar
sin perder nada) y los **textos que faltarían subir** (con las páginas del
PDF que no aparecen en ningún posteo). Los dos se ven en el taller, en
«guardadas»; desde ahí se borra de la papelera, con confirmación. Ningún
script borra nada.

## Qué hace falta instalar

- `indexar_pasajes.py`, `recalibrar.py` y `calcular_recorridos.py`: solo
  Python 3 (probado con 3.11), sin paquetes extra.
- `proponer_cruces.py` necesita `numpy` y un backend de embeddings:

  | backend | instalación | para qué |
  |---|---|---|
  | `sentence-transformers` (el de `config.json`) | `pip install numpy sentence-transformers` | el real: un modelo multilingüe que corre en tu máquina, sin API. La primera vez baja el modelo de Hugging Face (una sola vez; queda en la caché de Hugging Face, fuera del repo). |
  | `spacy-es-lg` | `pip install numpy spacy` y `python -m spacy download es_core_news_lg` | sustituto: promedio de vectores de palabras en español. Es el que se usó en la prueba de humo porque esta máquina no puede bajar modelos de Hugging Face. |
  | `hash` | `pip install numpy` | trivial y léxico por construcción: solo sirve para probar que el pipeline corre. |

  Se elige en `config.json` (`backend`, `modelo`) o por comando:
  `python3 matriz/proponer_cruces.py --backend spacy-es-lg`.

Nada de esto usa la API de Claude ni ningún servicio pago.

Opciones de `proponer_cruces.py`: `--dry-run` (no escribe) y `--muestra N`
(imprime N propuestas al azar con su explicación).

## config.json

- `universo.pdfs_manifest`: indexar los PDF del manifest que tengan `.txt` en
  `datos-lee`.
- `universo.series` / `universo.posts`: posts que entran (por serie o por id).
- `backend`, `modelo`: ver arriba.
- `mostrar_propuestas`: `false` = las propuestas se ven solo en el taller. Con
  `true`, `matriz.html` también las muestra, marcadas como propuestas.
- `pasaje_palabras_minimas`: páginas o párrafos más cortos no se indexan.
- `propuestas_por_instrumento`, `max_por_par_de_sitios`, `max_por_pasaje`,
  `max_por_obra`: límites de cantidad y de variedad, por instrumento.
  `max_por_obra` (cuántas propuestas de un mismo instrumento pueden tocar una
  obra, de origen o de destino) es opcional: sin él no hay tope por obra.
- `propuestas_total` (opcional): cuántas propuestas en total. Se reparten
  según el peso de cada instrumento (`instrumentos.json`), así sumar
  instrumentos no suma propuestas; cada uno queda entre
  `propuestas_minimas_por_instrumento` (5) y `propuestas_por_instrumento`.
  Sin él, cada instrumento propone hasta `propuestas_por_instrumento`.
- `instrumentos_sin_propuestas`: ids de instrumentos que no proponen nada
  (siguen valiendo en sus diagonales).
- `umbral_inicial`: puntaje mínimo para proponer mientras un instrumento no
  tiene decisiones (escala de percentiles, de 0 a 1).
- `robustez_minima`: cuánto tiene que sostenerse el parecido al sacar las
  palabras compartidas con el emergente.
- `solape_lexico_maximo`: cuántas palabras pueden compartir origen y destino.

## Cómo se calcula

Las fórmulas están escritas y comentadas en el encabezado de cada script:

- `proponer_cruces.py`: activación contra el perfil del instrumento (sus
  emergentes), percentil por semilla, robustez léxica, solape del par,
  puntaje total y los seis descartes.
- `recalibrar.py`: peso (saturación, dispersión, precisión) y umbral por
  instrumento y por tipo de relación.
- `calcular_recorridos.py`: la regla de encadenamiento y los cuatro criterios.

## Problemas comunes

- **"Falta el paquete numpy"** (u otro): instalalo como dice el mensaje.
- **"Falta cache-matriz/pasajes.json"**: corré antes `indexar_pasajes.py`.
- **El taller dice que no pudo leer `matriz/propuestas.json`**: corré
  `proponer_cruces.py` y abrí el taller con servidor local
  (`python3 -m http.server` desde `sitio/`).
- **Cambiaste de backend**: las propuestas cambian. El id de una propuesta
  depende solo del par de pasajes y del instrumento, así que si el mismo par
  vuelve a salir, tu decisión sigue valiendo.

## Anexo metodológico (`anexo/`)

Recorrido de análisis del 30/09, documentado en `anexo/ANEXO.md`:
conceptos diagonales de la autora → expansión estructural sobre sus nodos
aledaños → medida del cuerpo con los criterios que teorizan las últimas
obras (IIN de no teoría, curvatura del quantum, costo de integración,
hiperespecificidad, al-menos-dos). Los resultados están fijos en
`anexo/datos/` y los muestra `matriz-anexo.html` (enlace «anexo» en la
matriz). No los procesa la plataforma: se recalculan a mano con
`anexo/scripts/correr.sh`. Las obras se fechan con la cronología de la
autora (`anexo/CRONOLOGIA.md`, guardada tal cual) vía `anexo/scripts/fechas.py`.

## Superficie relacional (`superficie/`)

Índice fijo que arma `anexo/scripts/superficie.py` (lo corre `correr.sh`,
al final): léxico con vecinos estructurales, núcleos y nodos convergentes,
los pasajes fechados con sus claves, y el perfil de operadores y firmas por
período. Lo lee `matriz-superficie.js` en el taller («superficie
relacional»): la selección, el capítulo o la obra contra todo el cuerpo.
Ver «La superficie relacional» en `anexo/ANEXO.md`.

Se rearma sola con el workflow «Superficie» (`.github/workflows/superficie.yml`)
cuando cambian `lemas.json`, una obra, los `.txt` de `datos-lee` o los
scripts del anexo, y los lunes; también a mano, desde Actions. Así el índice
lematiza igual que el taller.

## Lematización

Las tres lematizaciones (`diagonal.js`, `matriz-superficie.js` y
`anexo/scripts/lematica.py`) siguen el mismo orden:

1. `lemas.json` → `formas`: lo que decidiste vos. Manda siempre.
2. Los irregulares de siempre (es → ser, tiene → tener…).
3. `lemas-auto.json`: el lema de un diccionario del español (`simplemma`),
   para cada forma del cuerpo que conoce. Lo arma `sitio/lemas_auto.py`
   (y el workflow «Superficie»); no se edita a mano. Si su lema está en tus
   formas, sigue hasta el tuyo. No junta femenino y masculino.
4. Las reglas generales, para lo que el diccionario no conoce.

`python3 tests/test_lematizacion.py` (desde la raíz) comprueba que las tres
dan lo mismo.
