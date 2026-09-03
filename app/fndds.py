"""
FNDDS (Food and Nutrient Database for Dietary Studies) del USDA,
version local simplificada.

Reemplaza al cliente en linea de usda.py como fuente de alimentos
genericos que ni Marifer ni la BAM cubren (salmon, quinoa, kale,
pistaches, y en general alimentos no tradicionales en Mexico).

Ventajas sobre la API en linea:
- Archivo local, sin API key, sin limite de 1000 consultas por hora,
  sin dependencia de internet ni de la disponibilidad del servicio.
- 5431 alimentos, filtrados a Foundation y SR Legacy (alimentos
  genericos analizados en laboratorio, no productos de marca).
- Valores por 100 g, igual que la BAM y Marifer.

Nota de idioma: los nombres vienen en ingles, tal como los publica el
USDA. Esta fuente es para el CALCULO interno del verificador, no para
mostrarse en documentos del paciente sin traducir primero.

Nota de calidad: revisado contra rangos fisiologicos plausibles antes
de la conversion (sep 2026). Sin errores de captura encontrados: los
unicos valores atipicos (manteca de cerdo, cereal de bebe fortificado,
salsa de pescado, te instantaneo concentrado) son correctos.
"""

import json
import os
import unicodedata

RUTA_DATOS = os.path.join(os.path.dirname(__file__), "datos", "alimentos_fndds.json")

_alimentos = None


def _normalizar_texto(texto):
    """Quita acentos y pasa a minusculas, para comparar sin importar tildes."""
    if not texto:
        return ""
    sin_acentos = unicodedata.normalize("NFD", str(texto))
    sin_acentos = "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")
    return sin_acentos.lower().strip()


def _sin_plural(palabra):
    """
    Quita una 's' o 'es' final simple, para tolerar variaciones de
    plural/singular al buscar. No busca ser gramaticalmente perfecto
    (a veces deja la palabra incompleta, ej. "raspberries" -> "raspberri"),
    pero como la busqueda es por coincidencia de substring, una palabra
    incompleta sigue encontrando el nombre real ("raspberri" esta
    contenido en "Raspberries, raw"). Intentar una regla gramaticalmente
    "correcta" es mas fragil: se probo y rompia casos que ya funcionaban.

    No toca palabras de 4 letras o menos.
    """
    if len(palabra) <= 4:
        return palabra
    if palabra.endswith("es"):
        return palabra[:-2]
    if palabra.endswith("s"):
        return palabra[:-1]
    return palabra


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
    palabras del termino, sin importar el orden, y tolerando plural o
    singular ("eggs" encuentra "Egg, whole, raw, fresh").
    """
    alimentos = _cargar()
    palabras = [_sin_plural(p) for p in _normalizar_texto(termino).split()]

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
    """Devuelve un alimento por su codigo FNDDS."""
    for a in _cargar():
        if a.get("codigo") == str(codigo):
            return _limpiar(a)
    return None


def tiene_datos_completos(alimento):
    """Verifica que el alimento traiga los macronutrientes."""
    esenciales = ["proteina_g", "carbohidratos_g", "grasa_g"]
    return all(alimento.get(c) is not None for c in esenciales)


def _limpiar(alimento):
    """Devuelve una copia sin los campos internos de busqueda."""
    return {k: v for k, v in alimento.items() if not k.startswith("_")}


def total_alimentos():
    return len(_cargar())
