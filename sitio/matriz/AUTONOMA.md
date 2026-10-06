# La matriz autónoma

Diseño corto de la expansión autónoma de la matriz: qué criterios salen del
corpus, cómo se marca el origen de cada relación o categoría, y qué queda
para después. El cálculo está en `autonoma.py`; la página que lo muestra es
`matriz-autonoma.html` (enlace «autónoma» en la matriz).

## El problema

Hasta ahora la matriz deriva casi todo de tus definiciones: las propuestas
de `proponer_cruces.py` se parecen al perfil de tus instrumentos (tus
emergentes), y `recorridos.json` encadena tus diagonales. Es una matriz
guiada. Lo que falta es una capa que no parta de vos: relaciones que el
corpus sostiene aunque nadie las haya visto, guardadas aparte para que no
se lean como tuyas.

## Tres orígenes, nunca mezclados

| origen | qué es | dónde vive | quién lo escribe |
|---|---|---|---|
| `autora` | declarado: diagonales, emergentes, instrumentos, decisiones sobre propuestas | `acciones.json`, `diagonales.json`, `matriz/instrumentos.json`, `matriz/decisiones.json` | vos |
| `matriz:instrumentos` | derivado desde tus instrumentos: propone, no decide | `matriz/propuestas.json` | `proponer_cruces.py` |
| `matriz:corpus` | derivado solo del corpus, sin ninguna lista tuya | `matriz/autonoma.json` | `autonoma.py` |
| `lector` | derivado del recorrido de los visitantes | todavía no existe | (más adelante) |

Reglas:

- Cada origen tiene su archivo. Ningún script de la matriz escribe en los
  tuyos, y `autonoma.py` no escribe en ningún otro de la matriz.
- Lo derivado lleva su origen en `meta.origen` y su estatuto
  (`derivado-matriz`): es una lectura, no una definición.
- Cuando una propuesta de la matriz la aceptás con tu emergente, pasa a
  ser tuya (`autora`), como hoy. Lo autónomo no se acepta ni se rechaza
  en esta primera versión: se mira.
- El cruce con lo tuyo se hace **al final** y solo marca coincidencias
  («ya la tendiste», «coincide con tu instrumento X»). Nunca entra en el
  cálculo.

## Qué criterios salen del corpus

Ninguno es una etiqueta de afuera. Todos se miden contra el propio
material:

1. **Asociación**: dos palabras (lemas) se asocian si aparecen juntas entre
   las claves de un mismo pasaje más de lo que el azar daría, en pasajes de
   al menos tres obras distintas. Un tic de una sola obra no es una
   relación del corpus.
2. **Categoría**: un grupo de palabras que se asocian entre sí más que con
   el resto (comunidades del grafo de asociaciones).
3. **Nombre**: la palabra más central del grupo, en la forma en que más
   aparece en tus textos. Si una categoría se llama «coax» es porque
   «coax» es lo que la sostiene en el corpus, no porque alguien la bautizó.
4. **Significatividad**: cuántas veces más pasajes activan la categoría que
   conjuntos al azar de palabras de frecuencia parecida. Lo que no supera
   dos veces el azar no queda.
5. **Modo**: «sonoro» si la mitad del grupo rima (sin contar sufijos ni
   infinitivos), «de sentido» si no. El corpus agrupa por eco tanto como
   por tema, y la matriz lo distingue sola.
6. **Relación entre obras**: dos obras se relacionan por las categorías que
   comparten, con más peso las categorías más específicas (las que están en
   pocas obras).

La entrada es la superficie relacional (`matriz/superficie/`), que ya
lematiza igual que el taller con `lemas.json` y `lemas-auto.json`. Es lo
único tuyo que toca el cálculo: cómo se juntan las formas de una palabra,
no qué significa.

## Primera vuelta: lo que hay

Con el corpus actual (`autonoma.json`, 2026-10-04): 55 categorías y 160
relaciones entre obras; **120 de esas relaciones unen obras que nunca
uniste con una diagonal** (sobre todo entre los poemarios: El Hecho, Cuerpo,
Torción, 112412, 594960, 3rd Comment). Las de los textos teóricos (no
teoría, Términos y condiciones, Potencial de repente…, dos puntos) sí
coinciden con tus diagonales, lo que sirve de control: donde vos tendiste,
la matriz también encuentra.

Solo 3 de las 55 categorías coinciden con un instrumento o concepto
diagonal tuyo (mismidad, imposibilidad, indeterminación). Las demás son
del corpus: «coax» (rana, chicharra, brekekex, Aristófanes, grillo),
«jinetes» (caballo, corcel, crin, ceroico), «arco» (carcaj, cupido, psique,
Filoctetes), «oficio» (artificio, ficticio: sonora), etc.

## Límites de esta versión

- **Solo castellano.** Los pasajes en inglés (unos 1800), francés e
  italiano agrupan por idioma y no por sentido; quedan contados en
  `meta.pasajes_por_lengua`, para una vuelta propia con sus palabras
  vacías.
- **Solo nivel obra** en las relaciones: todavía no propone cruces de
  pasaje a pasaje. Los ejemplos de cada categoría sí son pasajes.
- **No se decide nada.** No hay aceptar ni rechazar sobre lo autónomo.

## Lo que sigue

1. **Pasaje a pasaje**: que una categoría autónoma pueda proponer anclas
   concretas (con origen `matriz:corpus`), separadas en el taller de las
   propuestas que salen de tus instrumentos.
2. **Otras lenguas**: la misma vuelta para los pasajes en inglés y francés.
3. **Lectores** (origen `lector`): ya se juntan dos fuentes, solo legibles
   con tu token: la huella colectiva (`/api/huella`, pares [de, a]
   anónimos) y los registros por texto (`/api/lectura`: segundos, tipo de
   interacción, hora, zona, clima). Cuando haya volumen, un script aparte
   (no este) los lee como otra fuente de asociación —dos textos se asocian
   si los lectores pasan de uno a otro, o hacen lo mismo en los dos, más de
   lo que daría el azar— y escribe `matriz/lectores.json`, con el mismo
   cruce final contra lo tuyo y contra lo de la matriz. Los nombres de esas
   categorías saldrían de los comentarios que los lectores dejen marcados
   para la matriz.
4. **Comparar los tres**: en la página, una misma obra vista desde los tres
   orígenes (lo que tendiste, lo que encuentra el corpus, por dónde pasan
   los lectores).
