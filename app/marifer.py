"""
Base de datos de alimentos de Marifer.

Fuente primaria de alimentos genericos del sistema. Reemplaza a la BAM
como primera fuente de consulta.

Origen: base de equivalencias propia de la nutriologa, clasificada segun
el Sistema Mexicano de Alimentos Equivalentes (SMAE) -- cada alimento
trae su grupo real (AOAMBG, CerealesSG, Frutas, etc.), su porcion casera
tipica, y sus valores nutricionales calculados por 100 g de porcion neta
para poder escalar a cualquier cantidad.

2342 alimentos, sin internet, sin limites.

Nota de calidad: el campo hierro_mg viene anulado (None) en ~967
alimentos porque el dato original tenia errores de captura (valores
fisiologicamente imposibles). Ver conversacion de migracion para detalle.
Cualquier campo en None significa "sin dato confiable", nunca cero.
"""

import json
import os
import unicodedata

RUTA_DATOS = os.path.join(os.path.dirname(__file__), "datos", "alimentos_marifer.json")

_alimentos = None


def _normalizar_texto(texto):
    """Quita acentos y pasa a minusculas, para comparar sin importar tildes."""
    if not texto:
        return ""
    sin_acentos = unicodedata.normalize("NFD", str(texto))
    sin_acentos = "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")
    return sin_acentos.lower().strip()


def _cargar():
    global _alimentos
    if _alimentos is None:
        with open(RUTA_DATOS, encoding="utf-8") as f:
            _alimentos = json.load(f)
        for a in _alimentos:
            a["_busqueda"] = _normalizar_texto(a.get("nombre"))
    return _alimentos


def buscar(termino, limite=10):
    """
    Busca alimentos por nombre. Devuelve los resultados ordenados:
    primero las coincidencias exactas, luego las que empiezan igual,
    y al final las que contienen el termino en cualquier parte.
    """
    alimentos = _cargar()
    consulta = _normalizar_texto(termino)

    if not consulta:
        return []

    exactos = []
    empiezan = []
    contienen = []

    for a in alimentos:
        nombre = a["_busqueda"]
        if nombre == consulta:
            exactos.append(a)
        elif nombre.startswith(consulta):
            empiezan.append(a)
        elif consulta in nombre:
            contienen.append(a)

    resultados = exactos + empiezan + contienen
    return [_limpiar(a) for a in resultados[:limite]]


def buscar_palabras(termino, limite=10):
    """
    Busqueda mas flexible: encuentra alimentos que contengan todas las
    palabras del termino, sin importar el orden.
    Util para "pollo pechuga" o "frijol negro cocido".
    """
    alimentos = _cargar()
    palabras = _normalizar_texto(termino).split()

    if not palabras:
        return []

    coincidencias = []
    for a in alimentos:
        nombre = a["_busqueda"]
        if all(p in nombre for p in palabras):
            coincidencias.append(a)

    coincidencias.sort(key=lambda a: len(a["_busqueda"]))
    return [_limpiar(a) for a in coincidencias[:limite]]


def buscar_por_categoria(categoria, limite=50):
    """
    Devuelve alimentos de un grupo SMAE especifico (ej. "Frutas",
    "AOAMBG", "CerealesSG"). Util para verificador.py y reglas.py
    cuando necesiten razonar sobre el grupo de equivalencia real.
    """
    alimentos = _cargar()
    cat_normalizada = _normalizar_texto(categoria)

    coincidencias = [
        a for a in alimentos
        if _normalizar_texto(a.get("categoria")) == cat_normalizada
    ]
    return [_limpiar(a) for a in coincidencias[:limite]]


def categorias_disponibles():
    """Lista las categorias SMAE unicas presentes en la base."""
    alimentos = _cargar()
    return sorted({a.get("categoria") for a in alimentos if a.get("categoria")})


def _limpiar(alimento):
    """Devuelve una copia sin los campos internos de busqueda."""
    return {k: v for k, v in alimento.items() if not k.startswith("_")}


def total_alimentos():
    return len(_cargar())
