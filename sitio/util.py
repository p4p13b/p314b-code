"""Funciones chicas que usan varios scripts de sitio/ (y matriz/comun.py).

Estaban copiadas en cada script: leer JSON, cargar/guardar JSON, slugify y
bloque_de. Una sola versión, para que un ajuste no deje a un script
distinto de los otros.
"""
import json
import os
import re
import unicodedata


def leer(ruta, defecto=None):
    """JSON de ruta, o defecto si no existe o está roto."""
    try:
        with open(ruta, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return defecto


def cargar_json(path, default):
    """JSON de path, o default si no existe (un JSON roto sí falla)."""
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return default


def guardar_json(path, data, crear_carpeta=False):
    if crear_carpeta:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def slugify(s):
    """Minúsculas, sin tildes, solo [a-z0-9] y guiones; '' si no queda nada."""
    s = unicodedata.normalize('NFD', (s or '').lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def bloque_de(body, m):
    """El bloque (párrafo, ítem, cita o título) que contiene la marca m."""
    aperturas = list(re.finditer(r'<(p|li|blockquote|h[1-6])\b[^>]*>', body[:m.start()], re.I))
    if not aperturas:
        return body
    ab = aperturas[-1]
    cierre = body.find('</%s>' % ab.group(1).lower(), m.end())
    return body[ab.start(): cierre if cierre >= 0 else len(body)]
