"""
Redactor del documento del paciente.

Es la capa de REDACCION de la arquitectura de dos motores. Toma el plan
tecnico que produjo Gemini, ya verificado, y lo convierte en el documento
que va a leer el paciente, escrito con la voz de Marifer.

Division de trabajo:
  Gemini  -> analiza, calcula, decide que prescribir
  Sistema -> verifica los numeros contra la BAM y el USDA
  Claude  -> escribe el documento final

Claude NO calcula ni cambia cantidades. Si recibe 27 g de proteina en el
desayuno, escribe 27 g. Su unico trabajo es la redaccion.

El contrato de estilo vive en datos/estilo/STYLE_SPEC.md, derivado de 24
documentos reales de la nutriologa.
"""

import json
import os

import claude_api

RUTA_ESTILO = os.path.join(
    os.path.dirname(__file__), "datos", "estilo", "STYLE_SPEC.md"
)

_estilo = None


def cargar_estilo():
    """Lee el contrato de estilo. Se cachea en memoria."""
    global _estilo
    if _estilo is None:
        with open(RUTA_ESTILO, encoding="utf-8") as f:
            _estilo = f.read()
    return _estilo


def _sistema():
    """
    Instrucciones de rol y estilo. Van en el campo 'system' de la API
    porque aplican a toda la respuesta, no a un mensaje puntual.
    """
    return (
        "Escribes documentos de nutricion para los pacientes de Marifer "
        "Utrilla, nutriologa en Puebla, Mexico.\n\n"
        "Tu unico trabajo es la REDACCION. El analisis clinico y los "
        "calculos ya estan hechos y verificados. NO cambies cantidades, NO "
        "recalcules proteinas, NO agregues ni quites alimentos. Si el plan "
        "dice 27 g, escribes 27 g.\n\n"
        "Lo que si haces: escribir en la voz de Marifer, con su vocabulario, "
        "sus construcciones y su tono. El paciente debe reconocer a su "
        "nutriologa en cada linea.\n\n"
        "A continuacion, el contrato de estilo completo. Cumplelo al pie de "
        "la letra.\n\n"
        + ("=" * 70) + "\n\n"
        + cargar_estilo()
    )


def _resumen_del_plan(plan):
    """Extrae del plan tecnico solo lo que necesita el redactor."""
    partes = []

    if plan.get("objetivos_del_plan"):
        partes.append("OBJETIVOS DEL PLAN:")
        for o in plan["objetivos_del_plan"]:
            partes.append("  - " + str(o))
        partes.append("")

    prot = plan.get("objetivo_proteina_g")
    dist = plan.get("distribucion_proteina") or {}
    if prot:
        partes.append("META DE PROTEINA (dato interno, NO lo escribas en el "
                      "documento): " + str(prot) + " g al dia")
        partes.append("")

    est = plan.get("estructura_diaria") or {}
    if est:
        partes.append("ESTRUCTURA DEL DIA:")
        if est.get("verdura_tazas"):
            partes.append("  Verdura: " + str(est["verdura_tazas"]) + " tazas")
        if est.get("fruta_piezas"):
            partes.append("  Fruta: " + str(est["fruta_piezas"]) + " piezas")
        if est.get("grasa_porciones"):
            partes.append("  Grasa: " + str(est["grasa_porciones"]) + " porciones")
        partes.append("")

    partes.append("OPCIONES POR TIEMPO DE COMIDA")
    partes.append("Estas son las opciones ya calculadas y verificadas.")
    partes.append("Escribelas con el estilo de Marifer, sin cambiar cantidades.")
    partes.append("")

    for tiempo, opciones in (plan.get("opciones_por_tiempo") or {}).items():
        if not opciones:
            continue
        partes.append(tiempo.upper())
        for i, o in enumerate(opciones, 1):
            partes.append("  Opcion " + str(i) + ":")
            partes.append("    " + str(o.get("descripcion", "")))
        partes.append("")

    if plan.get("recomendaciones"):
        partes.append("RECOMENDACIONES A INCLUIR:")
        for r in plan["recomendaciones"]:
            partes.append("  - " + str(r))
        partes.append("")

    if plan.get("suplementacion_sugerida"):
        partes.append("SUPLEMENTACION:")
        for s in plan["suplementacion_sugerida"]:
            linea = "  - " + str(s.get("suplemento", ""))
            if s.get("dosis"):
                linea += ", " + str(s["dosis"])
            if s.get("momento"):
                linea += ", " + str(s["momento"])
            partes.append(linea)
        partes.append("")

    return "\n".join(partes)


ESQUEMA_DOCUMENTO = """{
  "objetivos_clave": ["objetivo redactado en su estilo", "otro"],
  "suplementacion": ["suplemento con dosis y momento, como lo escribiria ella"],
  "menu": {
    "desayuno": {
      "encabezado": "instruccion breve, ej. 'Elige una opcion y acompana con cafe o te sin azucar'",
      "opciones": ["opcion 1 redactada", "opcion 2 redactada"]
    },
    "colacion": {"encabezado": "", "opciones": []},
    "comida": {"encabezado": "", "opciones": []},
    "cena": {"encabezado": "", "opciones": []}
  },
  "recomendaciones": ["recomendacion redactada en su voz"],
  "cierre": "una o dos frases finales, si aplica"
}"""


def redactar(plan, nombre_paciente=None, idioma="es"):
    """
    Convierte el plan tecnico en el documento del paciente.

    Devuelve un diccionario con las secciones ya redactadas, listo para
    pasar al generador de PDF.
    """
    prompt_partes = []

    prompt_partes.append(
        "Redacta el documento de alimentacion para este paciente.\n\n"
    )

    if nombre_paciente:
        prompt_partes.append("Paciente: " + nombre_paciente + "\n\n")

    if plan.get("resumen_del_caso"):
        prompt_partes.append(
            "CONTEXTO DEL CASO (para que entiendas el enfoque, NO lo copies "
            "al documento):\n" + str(plan["resumen_del_caso"]) + "\n\n"
        )

    prompt_partes.append(("=" * 70) + "\n\n")
    prompt_partes.append(_resumen_del_plan(plan))

    prompt_partes.append("\n" + ("=" * 70) + "\n\n")
    prompt_partes.append(
        "INSTRUCCIONES\n\n"
        "Devuelve un JSON con esta estructura:\n\n"
        + ESQUEMA_DOCUMENTO +
        "\n\nReglas:\n"
        "- Las cantidades del plan se copian TAL CUAL. No las cambies.\n"
        "- Agrega la sazon y preparacion que caracteriza a Marifer: 'con "
        "limon, sal, pimienta y ajo', 'a la plancha', 'al gusto'.\n"
        "- Los encabezados de cada tiempo llevan su bebida de acompanamiento "
        "cuando aplique: 'acompana con agua de jamaica sin azucar', 'con te "
        "de canela sin endulzar'.\n"
        "- Puedes nombrar las opciones cuando tenga sentido: 'Bowl de "
        "salmon', 'Avotoast', 'Ensalada de atun'.\n"
        "- Frases cortas y directas. Nada de parrafos largos.\n"
        "- NUNCA escribas los gramos totales de proteina de una comida. "
        "Nada de 'Proteina: 30 g' al final de una opcion. El calculo es "
        "interno, de verificacion para la nutriologa, y el paciente no lo "
        "necesita. Lo unico que puede llevar gramos es la porcion de un "
        "alimento concreto, como '120 g de pechuga de pollo'.\n"
        "- Sin frases motivacionales genericas.\n"
        "- Sin calorias ni macros, salvo la proteina en gramos.\n"
    )

    if idioma == "en":
        prompt_partes.append(
            "\n- El paciente habla ingles. Traduce el documento al ingles, "
            "manteniendo los nombres de alimentos mexicanos en espanol "
            "(nopales, salmas, tinga) con una breve aclaracion si hace falta.\n"
        )

    prompt = "".join(prompt_partes)

    documento = claude_api.generar_json(
        prompt,
        sistema=_sistema(),
    )

    return {
        "documento": documento,
        "meta": {
            "modelo": claude_api.MODELO_REDACCION,
            "tamano_prompt_kb": len(prompt) // 1024,
            "idioma": idioma,
        },
    }
