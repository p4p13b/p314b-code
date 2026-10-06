import _rutas  # noqa: F401  (rutas y carpeta de trabajo)
import re
MARCAS = [
    (re.compile(r'(?<=[a-záéíóúñ,;]\s)Nadie\b'), 'NADIECONCEPTO'),       # Nadie con mayúscula a mitad de frase
    (re.compile(r'\b(el|del|al|su|un|ese|este|propio|mi|tu|sus|los|cada)\s+sí\b', re.I), r'\1 SICONCEPTO'),
]


def marcar(t):
    for rx, rep in MARCAS:
        t = rx.sub(rep, t)
    return t


SEMILLAS = {
    'Nadie': {'nadieconcepto', 'nadidad', 'nadiedad', 'nadico', 'nadica', 'nadieca', 'nadieco', 'nadismo'},
    'mismidad': {'mismidad', 'mismidades', 'mismizar', 'mismizacion', 'mismica', 'mismico', 'mismeidad', 'mismizarse'},
    'indiferir': {'indiferir', 'indiferirse', 'indiferibl', 'indiferibilidad'},
    'discernir': {'discernir', 'discernimiento', 'indiscernible', 'indiscernibilidad', 'indiscernibl'},
    'identidad': {'identidad', 'identico', 'identica', 'identitar', 'identitario'},
    'objetivar': {'objetivar', 'objetivacion', 'objetividad', 'objetivable'},
    'instrumental': {'instrumental', 'instrumentacion', 'instrumentalidad', 'instrumentabilidad', 'instrumentalizacion'},
    'devenir': {'devenir', 'devin', 'devino', 'deviniente', 'deven', 'devenirse'},
    'el sí': {'siconcepto'},
    'Rimbaud': {'rimbaud', 'pagano', 'pagana', 'nobleza', 'mueca'},
}
