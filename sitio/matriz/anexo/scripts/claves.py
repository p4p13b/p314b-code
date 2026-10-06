"""De la clave de obra al sitio.

Los pasajes se agrupan por `obra_clave` (sale del título: une el PDF y el
posteo de una misma obra), pero `meta.sitios` de pasajes.json está por
sitio (el slug del taller). Casi siempre coinciden; cuando el título no es
el slug (primera-osicion se titula «pop», cero «beta», 1-0-2-1 «1021»),
buscar la clave en `meta.sitios` da KeyError. Esto arma un diccionario
para buscar por cualquiera de las dos."""


def meta_por_clave(P):
    sitios = P['meta']['sitios']
    meta = dict(sitios)
    for p in P['pasajes']:
        if p['obra_clave'] not in meta and p['sitio'] in sitios:
            meta[p['obra_clave']] = sitios[p['sitio']]
    return meta
