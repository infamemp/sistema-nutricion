"""
Conversion entre medidas caseras y gramos.

Marifer prescribe en tazas, piezas y cucharadas. La BAM da valores por
100 g. Este modulo es el puente.

REGLA IMPORTANTE: los gramos son solo para calculo interno. El paciente
siempre ve la medida casera, nunca el gramaje.
"""

import json
import os
import unicodedata

RUTA = os.path.join(os.path.dirname(__file__), "datos", "medidas_caseras.json")

_tabla = None


def _normalizar(texto):
    if not texto:
        return ""
    sin_acentos = unicodedata.normalize("NFD", str(texto))
    sin_acentos = "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")
    return sin_acentos.lower().strip()


def cargar():
    global _tabla
    if _tabla is None:
        with open(RUTA, encoding="utf-8") as f:
            _tabla = json.load(f)
    return _tabla


# Palabras que no aportan a la identificacion del alimento.
# Sin esto, "espinaca cruda" no encuentra "espinaca cruda" si la IA
# escribe "espinacas crudas" o "espinaca fresca".
PALABRAS_IGNORABLES = {
    "de", "del", "la", "el", "los", "las", "con", "sin", "al", "a",
    "en", "y", "o", "un", "una", "fresco", "fresca", "frescos", "frescas",
    "natural", "naturales", "picado", "picada", "picados", "picadas",
    "rebanado", "rebanada", "rebanadas", "entero", "entera", "enteros",
    "enteras", "grande", "chico", "chica", "mediano", "mediana",
    "asado", "asada", "asados", "asadas", "plancha", "vapor",
    "salteado", "salteada", "salteados", "salteadas", "hervido", "hervida",
    "tostado", "tostada", "tostados", "tostadas", "molido", "molida",
    "deshebrado", "deshebrada", "desmenuzado", "desmenuzada",
}


def _palabras_clave(texto):
    """Extrae las palabras que si identifican al alimento."""
    palabras = _normalizar(texto).replace(",", " ").split()
    return [p.rstrip("s") for p in palabras if p not in PALABRAS_IGNORABLES and len(p) > 2]


def buscar_alimento(nombre):
    """
    Busca un alimento en la tabla de medidas. Devuelve su entrada o None.

    Tolera variaciones de la IA: "espinacas crudas frescas" encuentra
    "espinaca cruda", y "pechuga de pollo a la plancha" encuentra
    "pechuga de pollo".
    """
    tabla = cargar()["alimentos"]
    consulta = _normalizar(nombre)

    if consulta in tabla:
        return tabla[consulta]

    # Coincidencias por substring: cuando varias claves caben dentro de
    # la consulta (ej. "pescado" Y "tilapia" caben ambas en "filete de
    # pescado blanco (tilapia o similar)"), hay que preferir la mas
    # especifica (la clave mas larga), no la primera que aparezca en el
    # archivo. Antes de este ajuste, "pescado" (generica) ganaba sobre
    # "tilapia" (especifica) solo por estar antes en el JSON.
    candidatas = [clave for clave in tabla if _normalizar(clave) in consulta]
    if candidatas:
        # Mas especifica = mas larga. En caso de empate en longitud
        # (ej. "pescado" y "tilapia" miden lo mismo), se prefiere la
        # entrada curada con 'buscar_como', en vez de un cajon generico.
        def _especificidad(clave):
            tiene_buscar_como = 1 if "buscar_como" in tabla[clave] else 0
            return (len(_normalizar(clave)), tiene_buscar_como)

        mas_especifica = max(candidatas, key=_especificidad)
        return tabla[mas_especifica]

    for clave in tabla:
        if consulta in _normalizar(clave):
            return tabla[clave]

    # Busqueda por palabras clave, ignorando plurales y preparaciones.
    # Se queda con la coincidencia mas especifica, es decir, la que
    # comparte mas palabras con la consulta.
    palabras_consulta = set(_palabras_clave(nombre))
    if not palabras_consulta:
        return None

    mejor = None
    mejor_puntaje = 0

    for clave in tabla:
        palabras_clave_tabla = set(_palabras_clave(clave))
        if not palabras_clave_tabla:
            continue

        comunes = palabras_consulta & palabras_clave_tabla
        if not comunes:
            continue

        # Todas las palabras de la entrada deben estar en la consulta,
        # para no confundir "aceite de oliva" con "aceite de aguacate".
        if palabras_clave_tabla.issubset(palabras_consulta):
            puntaje = len(palabras_clave_tabla) * 10 + len(comunes)
            if puntaje > mejor_puntaje:
                mejor = tabla[clave]
                mejor_puntaje = puntaje

    return mejor


def a_gramos(nombre_alimento, medida):
    """
    Convierte una medida casera a gramos.

    Ejemplos:
      a_gramos("aguacate", "1/3 de aguacate")  -> 67
      a_gramos("arroz cocido", "1/2 taza")     -> 79
      a_gramos("pechuga de pollo", "1 pechuga") -> 120

    Devuelve (gramos, exacto). Si exacto es False, el valor es una
    estimacion derivada, no una medida registrada directamente.
    """
    entrada = buscar_alimento(nombre_alimento)
    if not entrada:
        return None, False

    medida_norm = _normalizar(medida)

    usuales = entrada.get("porciones_usuales", {})
    for texto, gramos in usuales.items():
        if _normalizar(texto) == medida_norm:
            return gramos, True

    for texto, gramos in usuales.items():
        if _normalizar(texto) in medida_norm or medida_norm in _normalizar(texto):
            return gramos, True

    equivalencias = {
        "taza": "taza_g",
        "1 taza": "taza_g",
        "pieza": "pieza_g",
        "1 pieza": "pieza_g",
        "cucharada": "cucharada_g",
        "cucharadita": "cucharadita_g",
        "rebanada": "rebanada_g",
        "filete": "filete_g",
        "scoop": "scoop_g",
        "paquetito": "paquetito_g",
    }

    for texto, campo in equivalencias.items():
        if texto in medida_norm and campo in entrada:
            return entrada[campo], True

    fracciones = {
        "1/2": 0.5, "media": 0.5, "medio": 0.5,
        "1/3": 0.333, "tercio": 0.333,
        "1/4": 0.25, "cuarto": 0.25,
        "3/4": 0.75,
        "2": 2, "3": 3, "4": 4,
    }

    for frac, factor in fracciones.items():
        if frac in medida_norm:
            for texto, campo in equivalencias.items():
                if texto in medida_norm and campo in entrada:
                    return round(entrada[campo] * factor), False

    if "taza_g" in entrada:
        return entrada["taza_g"], False
    if "pieza_g" in entrada:
        return entrada["pieza_g"], False

    return None, False


def nutrientes_de_porcion(nombre_alimento, medida, datos_bam):
    """
    Dado un alimento, su medida casera, y sus datos nutricionales por
    100 g (de la BAM o el USDA), calcula los nutrientes de esa porcion.

    Ejemplo: si la BAM dice que la pechuga de pollo tiene 31 g de
    proteina por 100 g, y la medida es "1 pechuga" (120 g), devuelve
    37.2 g de proteina.
    """
    gramos, exacto = a_gramos(nombre_alimento, medida)

    if gramos is None:
        return None

    factor = gramos / 100.0

    campos = [
        "energia_kcal", "proteina_g", "carbohidratos_g", "grasa_g",
        "fibra_g", "grasa_saturada_g", "azucares_g",
    ]

    resultado = {
        "alimento": nombre_alimento,
        "medida": medida,
        "gramos": gramos,
        "gramos_exactos": exacto,
    }

    for campo in campos:
        valor = datos_bam.get(campo)
        resultado[campo] = round(valor * factor, 1) if valor is not None else None

    return resultado


def alimentos_registrados():
    return sorted(cargar()["alimentos"].keys())


def total_alimentos():
    return len(cargar()["alimentos"])


def termino_para_bam(nombre_alimento):
    """
    Devuelve el termino con el que hay que buscar este alimento en la BAM.

    Resuelve el problema critico de crudo contra cocido: el arroz crudo
    tiene 363 kcal por 100 g y el cocido 123. Si el sistema busca el
    termino equivocado, el calculo sale al triple sin ninguna senal de
    error.

    Si el alimento tiene el campo "buscar_como", se usa ese. Si no,
    se usa el nombre tal cual.
    """
    entrada = buscar_alimento(nombre_alimento)
    if entrada and "buscar_como" in entrada:
        return entrada["buscar_como"]
    return nombre_alimento


def estado_alimento(nombre_alimento):
    """Devuelve 'crudo', 'cocido' o None si no esta especificado."""
    entrada = buscar_alimento(nombre_alimento)
    if entrada:
        return entrada.get("estado")
    return None


def buscar_en_bam(nombre_alimento, modulo_bam):
    """
    Busca un alimento en la BAM usando el termino correcto segun su
    estado. Es la forma segura de hacerlo, en lugar de buscar con el
    nombre coloquial.

    Uso:
      import bam, medidas
      datos = medidas.buscar_en_bam("arroz cocido", bam)
    """
    termino = termino_para_bam(nombre_alimento)
    resultados = modulo_bam.buscar_palabras(termino, limite=1)
    return resultados[0] if resultados else None


def verificar_sensatez(nutrientes):
    """
    Chequeo de sensatez sobre una porcion calculada. Devuelve una lista
    de advertencias, vacia si todo se ve razonable.

    Mismo principio que el chequeo del InBody: si un valor es absurdo,
    mejor avisar que aceptarlo callado.
    """
    avisos = []

    if not nutrientes:
        return ["No se pudo calcular la porcion"]

    gramos = nutrientes.get("gramos")
    kcal = nutrientes.get("energia_kcal")
    prot = nutrientes.get("proteina_g")

    if gramos and kcal:
        kcal_por_gramo = kcal / gramos
        if kcal_por_gramo > 9.5:
            avisos.append(
                "Densidad calorica imposible (" + str(round(kcal_por_gramo, 1))
                + " kcal/g). Ningun alimento supera 9 kcal/g, que es grasa pura."
            )
        elif kcal_por_gramo > 6:
            avisos.append(
                "Densidad calorica muy alta (" + str(round(kcal_por_gramo, 1))
                + " kcal/g). Verificar si el alimento deberia estar cocido."
            )

    if prot is not None and gramos:
        if prot > gramos * 0.9:
            avisos.append("La proteina excede el peso del alimento, dato incorrecto")

    if not nutrientes.get("gramos_exactos"):
        avisos.append("El peso es una estimacion derivada, no una medida registrada")

    return avisos
