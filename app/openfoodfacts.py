"""
Cliente de OpenFoodFacts para el sistema de nutricion.

Notas de la API (verificadas en la documentacion oficial, ago 2026):
- No requiere API key ni registro para lectura.
- El User-Agent descriptivo es OBLIGATORIO, sin el se corre el riesgo de
  ser bloqueado por parecer un bot.
- La busqueda por texto libre solo funciona en el endpoint v1
  (/cgi/search.pl con json=1). El v2 no soporta full-text.
- Instancia por pais: mx.openfoodfacts.org da mejor cobertura de
  productos mexicanos que world.openfoodfacts.org.
- Licencia de los datos: Open Database License (ODbL).
"""

import urllib.request
import urllib.parse
import json

USER_AGENT = "SistemaNutricionMariferUtrilla/1.0 (contacto@mafernut.com)"
BASE_MX = "https://mx.openfoodfacts.org"
BASE_WORLD = "https://world.openfoodfacts.org"

CAMPOS = "code,product_name,product_name_es,brands,quantity,serving_size,nutriments,countries_tags"

NUTRIENTES = {
    "energia_kcal": "energy-kcal_100g",
    "proteina_g": "proteins_100g",
    "carbohidratos_g": "carbohydrates_100g",
    "azucares_g": "sugars_100g",
    "grasa_g": "fat_100g",
    "grasa_saturada_g": "saturated-fat_100g",
    "fibra_g": "fiber_100g",
    "sodio_mg": "sodium_100g",
}


def _peticion(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _normalizar(producto):
    """Convierte un producto crudo de la API a nuestro formato interno."""
    nutr = producto.get("nutriments", {})

    nombre = (
        producto.get("product_name_es")
        or producto.get("product_name")
        or "Sin nombre"
    )

    resultado = {
        "codigo": producto.get("code"),
        "nombre": nombre,
        "marca": producto.get("brands"),
        "cantidad": producto.get("quantity"),
        "porcion": producto.get("serving_size"),
        "fuente": "openfoodfacts",
    }

    for clave_nuestra, clave_off in NUTRIENTES.items():
        valor = nutr.get(clave_off)
        resultado[clave_nuestra] = float(valor) if valor is not None else None

    # OFF guarda sodio en gramos, lo pasamos a mg
    if resultado["sodio_mg"] is not None:
        resultado["sodio_mg"] = round(resultado["sodio_mg"] * 1000, 1)

    return resultado


def buscar(termino, limite=5, solo_mexico=True):
    """
    Busca alimentos por texto libre.
    Devuelve una lista de diccionarios normalizados.
    """
    base = BASE_MX if solo_mexico else BASE_WORLD
    params = urllib.parse.urlencode({
        "search_terms": termino,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": limite,
        "fields": CAMPOS,
    })
    url = base + "/cgi/search.pl?" + params

    datos = _peticion(url)
    productos = datos.get("products", [])

    return [_normalizar(p) for p in productos]


def obtener_por_codigo(codigo):
    """Busca un producto por su codigo de barras."""
    url = BASE_WORLD + "/api/v2/product/" + str(codigo) + ".json?fields=" + CAMPOS
    datos = _peticion(url)

    if datos.get("status") != 1:
        return None

    return _normalizar(datos.get("product", {}))


def tiene_datos_completos(alimento):
    """
    Verifica si un alimento trae los macronutrientes basicos.
    Util para descartar registros incompletos de la base colaborativa.
    """
    esenciales = ["energia_kcal", "proteina_g", "carbohidratos_g", "grasa_g"]
    return all(alimento.get(c) is not None for c in esenciales)
