# pulenta

Lo que queda de pulenta es lo que usa el sitio: las familias de palabras y
la fecha de escritura de cada obra. La herramienta de análisis de PDF
(Vite + D3 + pdf.js) y sus documentos se borraron el 05/10/2026 porque no
influían en el sitio; siguen en el historial de git.

## Qué hay

- `scripts/familias.py`: arma las familias de palabras («el lema une, el uso
  separa») y una ficha por obra. Lo corre el workflow `superficie.yml`
  (también a mano: `python3 pulenta/scripts/familias.py`) y escribe en
  `datos/`.
- `datos/familias.json`: lo lee `sitio/parientes.py` (parientes y mismizar
  en la lectura).
- `datos/obras.json`: la fecha de escritura de cada obra; lo lee
  `sitio/publicados.py`.
- `datos/familias-revision.csv`: una fila por miembro, con columnas vacías
  para la decisión de la autora. Lo reescribe `familias.py` en cada corrida.

Lo que este script toma del sitio está en [`../INTERFAZ.md`](../INTERFAZ.md).
