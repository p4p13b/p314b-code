#!/bin/sh
# Anexo metodológico de la matriz: recalcula todo y deja los datos en
# ../datos/. Lo corre el workflow «Superficie» (.github/workflows/superficie.yml)
# cuando cambian los lemas, las obras o el cuerpo, y una vez por semana;
# también se puede correr a mano, desde cualquier carpeta. Necesita
# cache-matriz/pasajes.json (matriz/indexar_pasajes.py), sitio/lemas-auto.json
# (sitio/lemas_auto.py; sin él, solo reglas) y numpy + networkx (pypdf opcional, para la metadata de los PDF). Tarda unos 10 minutos (casi todo es estructural.py).
set -e
cd "$(dirname "$0")"
python3 duplicados.py            # pasajes repetidos entre libros
python3 lematica.py corpus.pkl   # lemas con las reglas de la página + lemas.json
python3 estructural.py 6         # perfiles de contexto y 6 particiones en mitades
python3 consenso.py 0.6          # núcleos estables por consenso
python3 palabra.py               # palabra, emergentes, obras en diagonal, testigos
python3 acunadas.py              # acuñaciones raras por núcleo
python3 fechas.py                # fechas de cada obra (CRONOLOGIA.md + metadata de los PDF)
python3 criterios.py             # los cinco criterios sobre cada obra
python3 calibrar.py              # calibración sobre C.1, secciones, correlaciones
python3 genealogia.py            # fase 4: gestación de +0 en el tiempo
python3 vectores.py              # fase 5: vectores de los nodos convergentes
python3 emergencia.py            # fase 6: conceptos, operadores, diagonales e instrumentos sin semillas
python3 categorias.py            # fase 7: las propuestas reducidas a tipos de relación, examen de los instrumentos, herramientas
python3 cutup.py                 # fase 8: Aire en la cuerda y De embriaguez y pathos (el cut-up) contra lo anterior y lo posterior
python3 exportar.py              # ../datos/*.json (lo que lee matriz-anexo.html)
python3 superficie.py            # ../../superficie/*.json (lo que lee el taller: superficie relacional)
