"""Rutas del anexo. Los scripts escriben sus intermedios en
cache-matriz/anexo/ (fuera del repo) y leen el índice de pasajes de
cache-matriz/pasajes.json (lo arma matriz/indexar_pasajes.py)."""
import os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(AQUI, '..', '..', '..', '..')) + os.sep
TRABAJO = os.path.join(RAIZ, 'cache-matriz', 'anexo')
DATOS = os.path.join(AQUI, '..', 'datos')
os.makedirs(TRABAJO, exist_ok=True)
os.chdir(TRABAJO)
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)
