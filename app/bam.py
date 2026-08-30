"""
Base de Alimentos de Mexico (BAM) version 18.1.1, 2021.

Fuente principal de alimentos genericos mexicanos.

Cita obligatoria:
  Ramirez Silva, I.; Barragan-Vazquez, S.; Rodriguez Ramirez, S.;
  Rivera Dommarco, J.A.; Mejia-Rodriguez, F.; Barquera Cervera, S.;
  Tolentino Mayo, L.; Flores Aldana, M.; Villalpando Hernandez, S.;
  Ancira Moreno, M.; et al. Base de Alimentos de Mexico (BAM):
  Compilacion de la Composicion de los Alimentos Frecuentemente
  Consumidos en el pais, Version 18.1.1, 2021.

Proyecto conjunto del INCMNSZ y el INSP, con participacion de la
Universidad Iberoamericana y el CIAD.

Ventajas sobre las fuentes en linea:
- Archivo local, sin API, sin limites de velocidad, sin internet.
- 2045 alimentos genericos mexicanos, incluyendo preparaciones
  tradicionales (tinga, cecina en jitomate, atoles) y alimentos
  regionales (quelites, papaloquelite, tejocote, chinchayote).
- Valores por 100 g de porcion comestible.
"""

import json
import os
import unicodedata

RUTA_DATOS = os.path.join(os.path.dirname(__file__), "datos", "alimentos_bam.json")

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


def obtener_por_codigo(codigo):
    """Devuelve un alimento por su codigo BAM."""
    for a in _cargar():
        if a.get("codigo") == str(codigo):
            return _limpiar(a)
    return None


def _limpiar(alimento):
    """Devuelve una copia sin los campos internos de busqueda."""
    return {k: v for k, v in alimento.items() if not k.startswith("_")}


def total_alimentos():
    return len(_cargar())
