"""
Cliente de USDA FoodData Central.

Fuente secundaria para alimentos genericos que la BAM no cubre bien
(salmon, quinoa, kale, pistaches, y en general alimentos no mexicanos).

Notas de la API (verificadas ago 2026):
- Los datos estan en dominio publico (CC0), uso comercial permitido.
- Requiere API key gratuita de api.data.gov/signup.
- Limite: 1000 consultas por hora por IP.
- Se filtra a Foundation y SR Legacy, que son los alimentos genericos
  analizados en laboratorio. Se excluye Branded (productos de marca),
  porque para eso ya usamos OpenFoodFacts.
- Los valores vienen por 100 g en Foundation y SR Legacy.
- Los nutrientes se identifican por numero, no por nombre.

IMPORTANTE: la API key nunca va en el codigo ni en el repositorio.
Se lee de la variable de entorno USDA_API_KEY, definida en el archivo
.env del servidor.
"""

import os
import json
import urllib.request
import urllib.parse

BASE = "https://api.nal.usda.gov/fdc/v1"

# Identificadores de nutriente de FoodData Central.
# Se usa nutrientId (estable) en lugar de nutrientNumber, porque el
# endpoint de busqueda devuelve la numeracion antigua ("431") mientras
# que el de detalle usa la moderna ("1008"). El nutrientId es el mismo
# en ambos.
NUTRIENTES = {
    1008: "energia_kcal",
    1003: "proteina_g",
    1005: "carbohidratos_g",
    1004: "grasa_g",
    1079: "fibra_g",
    2000: "azucares_g",
    1258: "grasa_saturada_g",
    1253: "colesterol_mg",
    1087: "calcio_mg",
    1089: "hierro_mg",
    1093: "sodio_mg",
}


def _api_key():
    clave = os.environ.get("USDA_API_KEY")
    if not clave:
        raise RuntimeError(
            "Falta la variable de entorno USDA_API_KEY. "
            "Obtener una clave gratuita en https://api.data.gov/signup"
        )
    return clave


def _peticion(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SistemaNutricion/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _normalizar(alimento):
    resultado = {
        "codigo": str(alimento.get("fdcId")),
        "nombre": alimento.get("description"),
        "tipo_dato": alimento.get("dataType"),
        "fuente": "USDA",
    }

    for clave in NUTRIENTES.values():
        resultado[clave] = None

    for n in alimento.get("foodNutrients", []):
        # El endpoint de busqueda pone el id en "nutrientId";
        # el de detalle lo anida en n["nutrient"]["id"].
        nid = n.get("nutrientId")
        if nid is None:
            nid = n.get("nutrient", {}).get("id")

        if nid in NUTRIENTES:
            valor = n.get("value")
            if valor is None:
                valor = n.get("amount")
            if valor is not None:
                resultado[NUTRIENTES[nid]] = float(valor)

    return resultado


def buscar(termino, limite=10):
    """
    Busca alimentos genericos (Foundation y SR Legacy).
    No incluye productos de marca; para eso usar el modulo openfoodfacts.
    """
    params = urllib.parse.urlencode({
        "api_key": _api_key(),
        "query": termino,
        "dataType": "Foundation,SR Legacy",
        "pageSize": limite,
    })
    url = BASE + "/foods/search?" + params

    datos = _peticion(url)
    return [_normalizar(a) for a in datos.get("foods", [])]


def obtener_por_id(fdc_id):
    """Devuelve el detalle completo de un alimento por su identificador."""
    params = urllib.parse.urlencode({"api_key": _api_key()})
    url = BASE + "/food/" + str(fdc_id) + "?" + params
    return _normalizar(_peticion(url))


def tiene_datos_completos(alimento):
    """
    Verifica que el alimento traiga los macronutrientes.

    La energia NO se exige: algunos registros Foundation del USDA la
    dejan en null aunque si traigan proteina, carbohidratos y grasa. Un
    caso real: las pepitas de calabaza. Exigirla descartaba datos
    perfectamente utiles para verificar la proteina, que es lo que nos
    importa.
    """
    esenciales = ["proteina_g", "carbohidratos_g", "grasa_g"]
    return all(alimento.get(c) is not None for c in esenciales)


def tiene_energia(alimento):
    """Para cuando si se necesita el dato calorico."""
    return alimento.get("energia_kcal") is not None
