"""
Motor de reglas clinicas.

Lee reglas_clinicas.json y calcula los objetivos nutricionales de un
paciente concreto. Es el puente entre el criterio de Marifer y lo que
la IA va a proponer.

Principio de diseno: este modulo NO decide nada por su cuenta. Todos los
numeros vienen del archivo de configuracion, que Marifer puede ajustar
sin tocar codigo.
"""

import json
import os

RUTA_REGLAS = os.path.join(os.path.dirname(__file__), "datos", "reglas_clinicas.json")

_reglas = None


def cargar():
    global _reglas
    if _reglas is None:
        with open(RUTA_REGLAS, encoding="utf-8") as f:
            _reglas = json.load(f)
    return _reglas


def objetivo_proteina(peso_kg, usa_glp1=False, redondear=True):
    """
    Calcula el rango de proteina diaria segun el peso y si el paciente
    usa GLP-1. Aplica el piso absoluto no negociable.

    Devuelve un diccionario con el rango, el objetivo sugerido y la
    distribucion por comida.
    """
    r = cargar()["proteina"]

    perfil = r["con_glp1"] if usa_glp1 else r["sin_glp1"]

    minimo = peso_kg * perfil["g_por_kg_min"]
    maximo = peso_kg * perfil["g_por_kg_max"]

    piso = r["piso_absoluto_g"]
    aplico_piso = minimo < piso

    if aplico_piso:
        minimo = piso
        if maximo < piso:
            maximo = piso

    objetivo = (minimo + maximo) / 2

    if redondear:
        minimo = round(minimo)
        maximo = round(maximo)
        objetivo = round(objetivo / 5) * 5

    dist = r["distribucion"]
    por_comida = objetivo / dist["comidas_principales"]

    return {
        "peso_kg": peso_kg,
        "usa_glp1": usa_glp1,
        "rango_min_g": minimo,
        "rango_max_g": maximo,
        "objetivo_g": objetivo,
        "piso_aplicado": aplico_piso,
        "comidas_principales": dist["comidas_principales"],
        "g_por_comida": round(por_comida),
        "g_por_comida_sugerido_min": dist["g_por_comida_min"],
        "g_por_comida_sugerido_max": dist["g_por_comida_max"],
        "requiere_colacion_proteica": por_comida > dist["g_por_comida_max"],
        "justificacion": perfil["justificacion"],
    }


def objetivos_diarios(peso_kg, usa_glp1=False, es_deportista=False, esta_embarazada=False):
    """
    Devuelve el conjunto completo de objetivos del dia para un paciente.
    Esto es lo que se le pasa a la IA como marco para armar la dieta.
    """
    r = cargar()

    fruta = r["fruta"]
    caso_especial = es_deportista or esta_embarazada
    max_fruta = (
        fruta["piezas_max_dia_casos_especiales"] if caso_especial
        else fruta["piezas_max_dia"]
    )

    return {
        "proteina": objetivo_proteina(peso_kg, usa_glp1),
        "verdura": {
            "tazas_minimas": r["verdura"]["tazas_minimas_dia"],
            "distribuir": r["verdura"]["distribuir_en_el_dia"],
        },
        "fruta": {
            "piezas_max": max_fruta,
            "caso_especial_aplicado": caso_especial,
            "preferidas": fruta["preferidas"],
        },
        "grasa": {
            "porciones": r["grasa"]["porciones_ideales_dia"],
            "preferidas": r["grasa"]["preferidas"],
            "excluidas": r["grasa"]["excluidas"],
        },
        "carbohidrato": {
            "equivalentes_por_comida_min": r["carbohidrato"]["equivalentes_por_comida_min"],
            "equivalentes_por_comida_max": r["carbohidrato"]["equivalentes_por_comida_max"],
            "preferidos": r["carbohidrato"]["preferidos"],
        },
        "calidad": {
            "principio": r["calidad_de_alimentos"]["principio"],
            "evitar": r["calidad_de_alimentos"]["evitar_siempre"],
        },
        "contar_calorias": r["calorias"]["contar"],
    }


def alimento_permitido(nombre_alimento):
    """
    Verifica si un alimento choca con las reglas de calidad o con las
    exclusiones de grasa. Devuelve (permitido, motivo).
    """
    r = cargar()
    nombre = nombre_alimento.lower()

    for excluido in r["grasa"]["excluidas"]:
        if excluido.lower() in nombre:
            return False, "Excluido por criterio de la nutrióloga: " + excluido

    for evitar in r["calidad_de_alimentos"]["evitar_siempre"]:
        palabras = evitar.lower().split()
        if any(p in nombre for p in palabras if len(p) > 4):
            return False, "Choca con la regla de calidad: " + evitar

    return True, None


def jerarquia():
    """Devuelve el orden de prioridad de las reglas, para el prompt de la IA."""
    return cargar()["jerarquia_de_decision"]


def resumen_para_prompt(peso_kg, usa_glp1=False, es_deportista=False, esta_embarazada=False):
    """
    Genera un texto legible con los objetivos del paciente, listo para
    inyectar en el prompt de la IA.
    """
    o = objetivos_diarios(peso_kg, usa_glp1, es_deportista, esta_embarazada)
    p = o["proteina"]

    lineas = []
    lineas.append("OBJETIVOS DEL PACIENTE (peso " + str(peso_kg) + " kg)")
    lineas.append("")
    lineas.append("Proteína: " + str(p["objetivo_g"]) + " g al día "
                  "(rango " + str(p["rango_min_g"]) + " a " + str(p["rango_max_g"]) + " g)")
    lineas.append("  Distribuir en " + str(p["comidas_principales"]) + " comidas de "
                  + str(p["g_por_comida"]) + " g aproximadamente")
    if p["piso_aplicado"]:
        lineas.append("  NOTA: se aplicó el piso mínimo de 60 g, no negociable")
    if p["requiere_colacion_proteica"]:
        lineas.append("  NOTA: el objetivo excede 30 g por comida, agregar colación con proteína")

    lineas.append("")
    lineas.append("Verdura: mínimo " + str(o["verdura"]["tazas_minimas"]) + " tazas al día, distribuidas")
    lineas.append("Fruta: máximo " + str(o["fruta"]["piezas_max"]) + " piezas al día, de bajo índice glucémico")
    lineas.append("Grasa: " + str(o["grasa"]["porciones"]) + " porciones de grasa saludable")
    lineas.append("Carbohidrato: " + str(o["carbohidrato"]["equivalentes_por_comida_min"])
                  + " a " + str(o["carbohidrato"]["equivalentes_por_comida_max"])
                  + " equivalentes por comida, según el caso")
    lineas.append("")
    lineas.append("CALIDAD: " + o["calidad"]["principio"])
    lineas.append("Evitar siempre: " + ", ".join(o["calidad"]["evitar"]))
    lineas.append("")
    lineas.append("NO contar ni mostrar calorías.")

    return "\n".join(lineas)
