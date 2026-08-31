"""
Acceso a la knowledgebase clinica.

19 extracciones de libros y guias clinicas, evaluadas y clasificadas por
nivel de autoridad. Detalle en docs/KNOWLEDGEBASE.md.

Proposito: cuando la IA genere una dieta, entregarle el conocimiento de
las fuentes relevantes al caso, no las 19 completas. Un paciente con SOP
recibe las fuentes de SOP; uno con endometriosis, las de endometriosis.
"""

import json
import os
import unicodedata

CARPETA = os.path.join(os.path.dirname(__file__), "datos", "knowledgebase")
RUTA_INDICE = os.path.join(os.path.dirname(__file__), "datos", "kb_indice.json")

_indice = None
_cache_contenido = {}


def _normalizar(texto):
    if not texto:
        return ""
    sin_acentos = unicodedata.normalize("NFD", str(texto))
    sin_acentos = "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")
    return sin_acentos.lower().strip()


def cargar_indice():
    global _indice
    if _indice is None:
        with open(RUTA_INDICE, encoding="utf-8") as f:
            _indice = json.load(f)
    return _indice


def fuentes_por_tema(tema):
    """
    Devuelve las fuentes relevantes para un tema clinico, ordenadas por
    nivel de autoridad (primero las de nivel A).

    Temas disponibles: obesidad, diabetes, resistencia_insulina, sop,
    endometriosis, fertilidad, embarazo, salud_hormonal, menopausia, glp1.
    """
    indice = cargar_indice()
    tema_norm = _normalizar(tema)

    coincidencias = [
        f for f in indice["fuentes"]
        if tema_norm in [_normalizar(t) for t in f["temas"]]
    ]

    coincidencias.sort(key=lambda f: (f["nivel"], f["archivo"]))
    return coincidencias


def leer_fuente(archivo):
    """Lee el contenido completo de una fuente. Usa cache en memoria."""
    if archivo in _cache_contenido:
        return _cache_contenido[archivo]

    ruta = os.path.join(CARPETA, archivo)
    if not os.path.exists(ruta):
        return None

    with open(ruta, encoding="utf-8") as f:
        contenido = f.read()

    _cache_contenido[archivo] = contenido
    return contenido


def contexto_para_caso(temas, solo_nivel_a=False, max_fuentes=4):
    """
    Arma el bloque de conocimiento para inyectar en el prompt de la IA,
    a partir de los temas clinicos del paciente.

    Ejemplo: contexto_para_caso(["sop", "resistencia_insulina"])

    Devuelve un diccionario con las fuentes seleccionadas y el texto
    concatenado listo para el prompt.
    """
    if isinstance(temas, str):
        temas = [temas]

    seleccionadas = []
    vistos = set()

    for tema in temas:
        for f in fuentes_por_tema(tema):
            if f["archivo"] in vistos:
                continue
            if solo_nivel_a and f["nivel"] != "A":
                continue
            seleccionadas.append(f)
            vistos.add(f["archivo"])

    seleccionadas.sort(key=lambda f: f["nivel"])
    seleccionadas = seleccionadas[:max_fuentes]

    bloques = []
    for f in seleccionadas:
        contenido = leer_fuente(f["archivo"])
        if not contenido:
            continue
        encabezado = (
            "FUENTE: " + f["titulo"] + "\n"
            "Autor: " + f["autor"] + " (" + str(f["ano"]) + ")\n"
            "Nivel de autoridad: " + f["nivel"] + "\n"
        )
        if f.get("nota"):
            encabezado += "Nota: " + f["nota"] + "\n"
        bloques.append(encabezado + "\n" + contenido)

    return {
        "fuentes": seleccionadas,
        "total": len(seleccionadas),
        "texto": "\n\n" + ("=" * 70) + "\n\n".join(bloques),
    }


def temas_disponibles():
    """Lista todos los temas clinicos cubiertos por la knowledgebase."""
    indice = cargar_indice()
    temas = set()
    for f in indice["fuentes"]:
        temas.update(f["temas"])
    return sorted(temas)


def resumen():
    """Estado de la knowledgebase, para diagnostico."""
    indice = cargar_indice()
    fuentes = indice["fuentes"]

    por_nivel = {}
    for f in fuentes:
        por_nivel[f["nivel"]] = por_nivel.get(f["nivel"], 0) + 1

    archivos_presentes = 0
    for f in fuentes:
        if os.path.exists(os.path.join(CARPETA, f["archivo"])):
            archivos_presentes += 1

    return {
        "total_fuentes": len(fuentes),
        "archivos_presentes": archivos_presentes,
        "por_nivel": por_nivel,
        "temas": len(temas_disponibles()),
    }
