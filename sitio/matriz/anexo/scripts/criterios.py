"""Aplica los cinco criterios a todas las obras y escribe criterios.json.
Las definiciones están en criterios_base.py."""
from _rutas import RAIZ  # rutas y carpeta de trabajo
import json, re, collections, statistics
from lematica import clave, cuenta, norm
from criterios_base import *  # noqa: F401,F403

# ── textos ──
textos = {}
for slug, m in META.items():
    f = m.get('fuente', '')
    try:
        textos[slug] = texto_post(f) if f.endswith('.json') else texto_pdf(f)
    except Exception as e:
        print('sin texto', slug, e, file=sys.stderr)

# ── léxico por obra (para costo e hiperespecificidad) ──
lem_obra = {}
for s, t in textos.items():
    lem_obra[s] = collections.Counter(norm(clave(w)) for w in re.findall(r"[^\W\d_]+", t) if cuenta(w))
n_obras = len(lem_obra)
en_cuantas = collections.Counter()
for c in lem_obra.values():
    en_cuantas.update(set(c))
ESTANDAR = {w for w, n in en_cuantas.items() if n >= n_obras / 2}
print('estándar endógeno:', len(ESTANDAR), 'lemas', file=sys.stderr)

# ── legitimación por la matriz (propuestas en main) ──
prop = json.load(open(RAIZ + 'sitio/matriz/propuestas.json'))['propuestas']
toca = collections.Counter()
for p in prop:
    toca[p['origen']['sitio']] += 1
    toca[p['destino']['sitio']] += 1

res = {}
for s, t in textos.items():
    vs = [medir_ventana(t[a:b]) for a, b in ventanas(t)]
    vs = [v for v in vs if v]
    if not vs:
        continue
    prom = {k: statistics.mean(v[k] for v in vs) for k in vs[0]}
    # cq sobre la obra entera
    ntok = len(re.findall(r"[^\W\d_]+", t))
    punt = len(re.findall(r"[^\w\s]+", t))
    lineas = len(cortes_de_linea(t)) if not META[s].get('fuente', '').endswith('.json') else len(re.findall(r'[^\n]\n[^\n]', t))
    parr = len(re.findall(r'\n\s*\n', t))
    huecos = len(HUECO.findall(t))
    cq = (punt + lineas + parr + huecos) / max(1, ntok - 1)
    c = lem_obra[s]; tot = sum(c.values())
    costo = sum(v for w, v in c.items() if w not in ESTANDAR) / tot
    hiper = sum(v for w, v in c.items() if en_cuantas[w] == 1) / tot
    hiper_tipos = [w for w, v in c.most_common() if en_cuantas[w] == 1][:12]
    lang = idioma(t)
    pl = len((PL_EN if lang == 'en' else PL_ES).findall(t)); sg = len((SG_EN if lang == 'en' else SG_ES).findall(t))
    dos = min(pl, sg) / max(pl, sg) if max(pl, sg) else 0
    res[s] = {'titulo': META[s]['titulo'], 'serie': (re.search(r'txt/([^/]+)-txt', META[s].get('fuente', '')) or [None, 'posteos'])[1],
              'idioma': lang, 'ventanas': len(vs), 'tokens': ntok, **{k: round(v, 4) for k, v in prom.items()},
              'IIN_max': round(max(v['IIN'] for v in vs), 2), 'IIN_min': round(min(v['IIN'] for v in vs), 2),
              'ventanas_IIN_bajo_1': sum(1 for v in vs if v['IIN'] < 1),
              'cq': round(cq, 4), 'huecos': huecos, 'costo': round(costo, 4), 'hiper': round(hiper, 4), 'hiper_tipos': hiper_tipos,
              'plural': pl, 'singular': sg, 'dos': round(dos, 3), 'P_plural': round(pl / max(1, pl + sg), 3),
              'propuestas': toca.get(s, 0), 'pasajes': META[s].get('pasajes', 0)}
json.dump(res, open('criterios.json', 'w'), ensure_ascii=False, indent=1)
print(f"{'obra':32s} {'ser':9s} {'TTR':>5s} {'inst':>5s} {'Eg':>6s} {'Ef':>6s} {'Esint':>6s} {'DRI':>5s} {'IIN':>5s} {'cq':>5s} {'costo':>5s} {'hiper':>5s} {'dos':>4s} {'%pl':>4s} {'prop':>4s}")
for s, r in sorted(res.items(), key=lambda x: -x[1]['IIN']):
    print(f"{r['titulo'][:32]:32s} {r['serie'][:9]:9s} {r['TTR']:.3f} {r['TTRinst']:.3f} {r['Eg']:.4f} {r['Ef']:.4f} {r['Esint']:.4f} {r['DRI']:.3f} {r['IIN']:5.2f} {r['cq']:.3f} {r['costo']:.3f} {r['hiper']:.3f} {r['dos']:.2f} {r['P_plural']:.2f} {r['propuestas']:4d} {r['idioma']}")
