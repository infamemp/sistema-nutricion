"""
Generador de planes tecnicos de alimentacion.

Es la capa de ANALISIS de la arquitectura de dos motores. Junta todo lo
construido en las fases anteriores y le pide a Gemini un plan tecnico
estructurado:

  Expediente del paciente   (base de datos)
  + Reglas clinicas         (reglas.py, criterios de Marifer)
  + Knowledgebase           (knowledgebase.py, fuentes del caso)
  + Datos de alimentos      (bam.py, medidas.py)
  -> PLAN TECNICO EN JSON

Ese plan NO es para el paciente. Es el insumo que Claude convierte
despues en un documento con la voz de Marifer.

Principio que gobierna este modulo: la IA razona sobre el caso concreto,
no copia plantillas. Ver docs/APRENDIZAJE_CONTINUO.md.
"""

import json

import gemini
import reglas
import medidas
import verificador
import knowledgebase as kb


# Mapa de padecimientos a temas de la knowledgebase.
# Se usa para seleccionar las fuentes relevantes al caso.
PADECIMIENTOS_A_TEMAS = {
    "obesidad": ["obesidad"],
    "sobrepeso": ["obesidad"],
    "diabetes": ["diabetes"],
    "diabetes tipo 2": ["diabetes"],
    "prediabetes": ["resistencia_insulina", "diabetes"],
    "resistencia a la insulina": ["resistencia_insulina"],
    "sop": ["sop", "resistencia_insulina"],
    "sindrome de ovario poliquistico": ["sop", "resistencia_insulina"],
    "endometriosis": ["endometriosis"],
    "fertilidad": ["fertilidad"],
    "infertilidad": ["fertilidad"],
    "embarazo": ["embarazo"],
    "menopausia": ["menopausia", "salud_hormonal"],
    "hormonal": ["salud_hormonal"],
    "tiroides": ["salud_hormonal"],
}


def temas_del_caso(padecimientos, usa_glp1=False):
    """Traduce los padecimientos del paciente a temas de la knowledgebase."""
    temas = []

    for p in padecimientos or []:
        p_norm = p.lower().strip()
        for clave, valores in PADECIMIENTOS_A_TEMAS.items():
            if clave in p_norm:
                for t in valores:
                    if t not in temas:
                        temas.append(t)

    if usa_glp1 and "glp1" not in temas:
        temas.append("glp1")

    return temas or ["obesidad"]


def _tabla_de_pesos():
    """
    Arma la tabla de pesos reales para inyectar en el prompt.

    Sin esto, la IA estima los gramajes de memoria y se equivoca. Un caso
    real detectado: dijo que 2 rebanadas de pechuga de pavo pesan 60 g,
    cuando pesan 24 g. Eso inflaba la proteina al doble.
    """
    tabla = medidas.cargar()["alimentos"]
    lineas = []

    for nombre in sorted(tabla.keys()):
        entrada = tabla[nombre]
        partes_alimento = []

        usuales = entrada.get("porciones_usuales", {})
        for texto, gramos in usuales.items():
            partes_alimento.append(texto + " = " + str(gramos) + " g")

        for campo, etiqueta in [
            ("taza_g", "1 taza"),
            ("pieza_g", "1 pieza"),
            ("rebanada_g", "1 rebanada"),
            ("cucharada_g", "1 cda"),
            ("cucharadita_g", "1 cdita"),
            ("filete_g", "1 filete"),
            ("scoop_g", "1 scoop"),
            ("paquetito_g", "1 paquetito"),
        ]:
            if campo in entrada:
                texto = etiqueta + " = " + str(entrada[campo]) + " g"
                if texto not in partes_alimento:
                    partes_alimento.append(texto)

        if partes_alimento:
            linea = "  " + nombre + ": " + " | ".join(partes_alimento)
            if entrada.get("nota"):
                linea += "  [" + entrada["nota"] + "]"
            lineas.append(linea)

    return "\n".join(lineas)


def verificar_cantidades(plan):
    """
    Revisa las cantidades del plan contra la tabla de pesos y devuelve
    una lista de discrepancias.

    No corrige nada, solo reporta. La correccion es decision humana o
    de una regeneracion.
    """
    problemas = []
    tabla = medidas.cargar()["alimentos"]

    opciones = plan.get("opciones_por_tiempo", {})
    for tiempo, lista in opciones.items():
        for i, opcion in enumerate(lista or []):
            for al in opcion.get("alimentos", []) or []:
                nombre = al.get("alimento", "")
                cantidad = al.get("cantidad", "")
                if not nombre or not cantidad:
                    continue

                gramos, exacto = medidas.a_gramos(nombre, cantidad)
                if gramos is None:
                    entrada = medidas.buscar_alimento(nombre)
                    if entrada is None:
                        problemas.append({
                            "tiempo": tiempo,
                            "opcion": i + 1,
                            "alimento": nombre,
                            "cantidad": cantidad,
                            "tipo": "alimento_no_en_tabla",
                            "detalle": "No esta en la tabla de pesos, no se pudo verificar",
                        })

    return problemas


def _seccion_expediente(paciente, historia, medicion):
    """Arma el bloque del expediente para el prompt."""
    lineas = ["DATOS DEL PACIENTE", ""]

    if paciente:
        lineas.append("Sexo: " + str(paciente.get("sexo") or "no especificado"))
        if paciente.get("edad"):
            lineas.append("Edad: " + str(paciente["edad"]) + " anos")

    if medicion:
        lineas.append("")
        lineas.append("MEDICION MAS RECIENTE")
        for campo, etiqueta in [
            ("peso", "Peso (kg)"),
            ("imc", "IMC"),
            ("porcentaje_grasa", "Grasa corporal (%)"),
            ("masa_grasa_kg", "Masa grasa (kg)"),
            ("mme", "Masa muscular esqueletica (kg)"),
            ("grasa_visceral", "Grasa visceral"),
        ]:
            valor = medicion.get(campo)
            if valor is not None:
                lineas.append("  " + etiqueta + ": " + str(valor))

    if historia:
        lineas.append("")
        lineas.append("HISTORIA CLINICA")

        bloques = [
            ("Objetivos del paciente", ["objetivo_que_espera", "objetivo_importante"]),
            ("Padecimientos", ["padecimientos_diagnosticados"]),
            ("Tratamiento medico actual", ["tratamiento_medico_actual"]),
            ("Medicamentos", ["medicamentos"]),
            ("Suplementos", ["suplementos"]),
            ("Alergias", ["alergias"]),
            ("Intolerancias", ["intolerancias"]),
            ("Alimentos que evita", ["alimentos_evitar"]),
            ("Restricciones por eleccion", ["restricciones_eleccion"]),
            ("Que come normalmente", ["recordatorio_desayuno", "recordatorio_comida",
                                      "recordatorio_cena", "recordatorio_snacks"]),
            ("Quien cocina", ["quien_cocina"]),
            ("Hidratacion", ["hidratacion"]),
            ("Ejercicio", ["ejercicio_rutina"]),
            ("Sueno", ["sueno"]),
            ("Historia de peso", ["peso_maximo", "peso_minimo", "dietas_previas"]),
        ]

        for etiqueta, campos in bloques:
            valores = [str(historia.get(c)) for c in campos if historia.get(c)]
            if valores:
                lineas.append("  " + etiqueta + ": " + " | ".join(valores))

        sintomas = []
        for campo, nombre in [
            ("sint_gastrointestinal", "gastrointestinales"),
            ("sint_distension", "distension"),
            ("sint_hormigueo", "hormigueo"),
            ("sint_caida_pelo", "caida de pelo"),
            ("sint_unas_debiles", "unas debiles"),
            ("sint_dolor_cabeza", "dolor de cabeza"),
            ("sint_memoria", "memoria"),
            ("sint_fatiga", "fatiga"),
            ("sint_piel_seca", "piel seca"),
            ("sint_acantosis", "acantosis nigricans"),
            ("sint_otro", "otros"),
        ]:
            if historia.get(campo):
                sintomas.append(nombre + ": " + str(historia[campo]))
        if sintomas:
            lineas.append("  Sintomas: " + " | ".join(sintomas))

    return "\n".join(lineas)


ESQUEMA_PLAN = """{
  "resumen_del_caso": "2 o 3 frases sobre la situacion del paciente y el enfoque elegido",
  "banderas_clinicas": [
    {"tipo": "medicamento | padecimiento | laboratorio | sintoma",
     "detalle": "que se detecto",
     "implicacion_nutricional": "que significa para el plan",
     "accion": "que hace el plan al respecto"}
  ],
  "objetivos_del_plan": ["objetivo 1", "objetivo 2"],
  "objetivo_proteina_g": 0,
  "distribucion_proteina": {"desayuno_g": 0, "comida_g": 0, "cena_g": 0, "colacion_g": 0},
  "estructura_diaria": {
    "tiempos_de_comida": ["desayuno", "colacion", "comida", "cena"],
    "verdura_tazas": 0,
    "fruta_piezas": 0,
    "grasa_porciones": 0,
    "carbohidrato_equivalentes_por_comida": 0
  },
  "opciones_por_tiempo": {
    "desayuno": [
      {"descripcion": "TODOS los alimentos CON SU CANTIDAD, en medidas caseras mexicanas",
       "alimentos": [{"alimento": "nombre del alimento", "cantidad": "medida casera exacta"}],
       "proteina_estimada_g": 0}
    ],
    "colacion": [],
    "comida": [],
    "cena": []
  },
  "recomendaciones": ["recomendacion practica 1", "recomendacion 2"],
  "suplementacion_sugerida": [
    {"suplemento": "nombre", "dosis": "cantidad", "momento": "cuando", "motivo": "por que"}
  ],
  "notas_para_la_nutriologa": ["algo que conviene que revise o considere"],
  "advertencias": ["si algo del expediente requiere atencion medica, no nutricional"]
}"""


def construir_prompt(paciente, historia, medicion, padecimientos=None,
                     usa_glp1=False, es_deportista=False, esta_embarazada=False,
                     opciones_previas=None, retroalimentacion_followup=None, incluir_kb=True):
    """
    Arma el prompt completo para Gemini.
    """
    peso = None
    if medicion:
        peso = medicion.get("peso")
    if not peso and historia:
        peso = historia.get("peso_actual")

    if not peso:
        raise ValueError("No hay peso registrado. Es indispensable para calcular la proteina.")

    partes = []

    partes.append(
        "Eres el motor de analisis nutricional de la consulta de Marifer Utrilla, "
        "nutriologa en Puebla, Mexico, especializada en obesidad, diabetes, "
        "resistencia a la insulina, SOP, endometriosis, salud hormonal, fertilidad "
        "y embarazo.\n\n"
        "Tu trabajo es ANALIZAR el caso y producir un PLAN TECNICO en JSON. "
        "No escribes para el paciente; otro sistema se encarga de la redaccion final. "
        "Tu salida es un documento de trabajo para la nutriologa.\n\n"
        "REGLA CENTRAL: razonas sobre este caso concreto. No aplicas plantillas ni "
        "repites formulas genericas. Cada paciente es distinto y el plan debe "
        "reflejar su situacion particular, sus preferencias y sus restricciones."
    )

    partes.append("\n\n" + ("=" * 70) + "\n")
    partes.append(_seccion_expediente(paciente, historia, medicion))

    partes.append("\n\n" + ("=" * 70) + "\n")
    partes.append("CRITERIOS DE PRESCRIPCION DE LA NUTRIOLOGA\n")
    partes.append("Estos criterios son de ella y no se negocian.\n\n")
    partes.append(reglas.resumen_para_prompt(
        peso, usa_glp1=usa_glp1,
        es_deportista=es_deportista,
        esta_embarazada=esta_embarazada,
    ))

    partes.append("\n\nJERARQUIA DE DECISION, en orden de prioridad:\n")
    for regla in reglas.jerarquia():
        partes.append("  " + regla + "\n")

    r = reglas.cargar()
    partes.append("\nGRASAS PERMITIDAS: " + ", ".join(r["grasa"]["preferidas"]))
    partes.append("\nGRASAS EXCLUIDAS por criterio de la nutriologa: "
                  + ", ".join(r["grasa"]["excluidas"]))
    partes.append("\nFRUTAS PREFERIDAS: " + ", ".join(r["fruta"]["preferidas"]))
    partes.append("\nCARBOHIDRATOS PREFERIDOS: " + ", ".join(r["carbohidrato"]["preferidos"]))

    if "carnes_frias" in r:
        cf = r["carnes_frias"]
        partes.append("\n\nCARNES FRIAS, distincion con criterio:")
        partes.append("\n  Evitar: " + ", ".join(cf["evitar"]["alimentos"]))
        partes.append("\n  Aceptables: " + ", ".join(cf["aceptables_con_criterio"]["alimentos"]))
        partes.append("\n  " + cf["regla"])

    if "principio_de_practicidad_sobre_pureza" in r:
        pp = r["principio_de_practicidad_sobre_pureza"]
        partes.append("\n\nPRINCIPIO DE PRACTICIDAD SOBRE PUREZA:\n  " + pp["regla"])
        partes.append("\n  " + pp["motivo"])
        partes.append("\n  " + pp["aplicacion"])

    if opciones_previas or retroalimentacion_followup:
        partes.append("\n\n" + ("=" * 70) + "\n")
        partes.append("CONTINUIDAD CON EL PLAN ANTERIOR\n")
        partes.append(
            "Lo siguiente es INFORMACION DE CONTEXTO, no una instruccion de repetir "
            "ni de evitar. Usa tu criterio clinico igual que con el resto del "
            "expediente: a veces lo correcto es mantener una opcion que le funciono "
            "bien al paciente y solo ajustar porciones para el nuevo objetivo; otras "
            "veces, sobre todo si hubo dificultad o disgusto, lo correcto es cambiar "
            "de fondo. Decide caso por caso.\n\n"
        )

        if retroalimentacion_followup:
            partes.append("COMO LE FUE AL PACIENTE CON EL PLAN ANTERIOR (ultimo seguimiento):\n")
            etiquetas = {
                "que_le_gusto": "Que le gusto",
                "que_no_le_gusto": "Que no le gusto",
                "cambios_que_hizo": "Cambios que hizo por su cuenta",
                "en_que_puede_mejorar": "En que puede mejorar",
                "ajustes_acordados": "Ajustes ya acordados con la nutriologa",
            }
            for campo, etiqueta in etiquetas.items():
                valor = retroalimentacion_followup.get(campo)
                if valor:
                    partes.append("  " + etiqueta + ": " + str(valor) + "\n")
            partes.append("\n")

        if opciones_previas:
            partes.append("OPCIONES YA PRESCRITAS ANTERIORMENTE:\n\n")
            for o in opciones_previas[:30]:
                partes.append("  - " + str(o) + "\n")

    if incluir_kb:
        temas = temas_del_caso(padecimientos, usa_glp1)
        contexto = kb.contexto_para_caso(temas, max_fuentes=3)
        if contexto["total"] > 0:
            partes.append("\n\n" + ("=" * 70) + "\n")
            partes.append("CONOCIMIENTO CLINICO DE REFERENCIA\n")
            partes.append("Fuentes seleccionadas para este caso. Las de nivel A tienen "
                          "mayor autoridad clinica que las de nivel B.\n")
            partes.append(contexto["texto"])

    partes.append("\n\n" + ("=" * 70) + "\n")
    partes.append(
        "INSTRUCCIONES DE SALIDA\n\n"
        "Devuelve unicamente un JSON que siga exactamente este esquema:\n\n"
        + ESQUEMA_PLAN +
        "\n\nReglas para llenarlo:\n"
        "\nCANTIDADES, LA REGLA MAS IMPORTANTE:\n"
        "TODO alimento que aparezca en una opcion DEBE llevar su cantidad. "
        "El paciente tiene que saber exactamente cuanto comer de cada cosa. "
        "Una descripcion sin cantidades es inservible y sera rechazada.\n\n"
        "MAL (no hagas esto):\n"
        "  'Huevos a la mexicana con frijoles refritos y aguacate'\n"
        "  'Tinga de pechuga de pollo con nopales y tostadas horneadas'\n\n"
        "BIEN (haz esto):\n"
        "  '3 huevos a la mexicana, 1/3 de taza de frijoles refritos (60 g aprox) "
        "en 1 cdita de aceite de oliva, 1/3 de aguacate y 2 tortillas de maiz'\n"
        "  '3/4 de taza de tinga de pechuga de pollo (120 g aprox), 2 nopales "
        "asados, 3 tostadas horneadas y 1/3 de aguacate'\n\n"
        "Cada alimento del campo 'alimentos' debe repetir esa cantidad en su "
        "campo 'cantidad'. La descripcion y la lista de alimentos deben coincidir.\n\n"
        "\nPESOS REALES, NO LOS ESTIMES:\n"
        "Abajo tienes la tabla de pesos del sistema. Es la referencia "
        "autoritativa. NO calcules gramajes de memoria: un error tipico es "
        "decir que 2 rebanadas de pechuga de pavo pesan 60 g cuando pesan 24. "
        "\nSI UN ALIMENTO NO ESTA EN LA TABLA:\n"
        "Preferentemente elige otro que si este, porque el sistema solo puede "
        "verificar los que conoce. Si de verdad necesitas usarlo, hazlo pero "
        "avisa en notas_para_la_nutriologa con esta forma: 'El alimento X no "
        "esta en la tabla de pesos del sistema, su gramaje es estimado y "
        "conviene verificarlo.' Nunca inventes un peso sin avisar.\n\n"
        + _tabla_de_pesos() +
        "\n\nPRACTICIDAD, TAN IMPORTANTE COMO LA EXACTITUD:\n"
        "El paciente va a preparar esto en su cocina, no en un laboratorio. "
        "Una cantidad correcta pero impracticable no sirve.\n\n"
        "1) ALIMENTOS ENTEROS NO SE FRACCIONAN. Los que vienen en unidades "
        "indivisibles se prescriben completos o no se prescriben. Nadie parte "
        "un huevo a la mitad, ni guarda media lata de atun abierta, ni deja "
        "1.5 tostadas en un paquete abierto que se pone aguado.\n"
        "   MAL: '2.5 huevos', 'media lata de atun', '1.5 tostadas salmas'\n"
        "   BIEN: '3 huevos', '1 lata de atun', '1 paquetito de salmas'\n"
        "   Aplica a: huevos, latas, paquetitos de salmas, piezas de fruta, "
        "filetes, tortillas, rebanadas de pan, scoops de proteina.\n"
        "   Si el calculo da una fraccion, redondea a la unidad entera mas "
        "cercana y ajusta el resto de la comida para compensar.\n\n"
        "2) DOBLE REFERENCIA EN LO QUE SE SIRVE A OJO. Nadie mide la tinga o "
        "un bistec con taza medidora, pero con una referencia visual mas el "
        "gramaje aproximado si puede calcular.\n"
        "   MAL: '3/4 de taza de tinga'\n"
        "   BIEN: '3/4 de taza de tinga de pollo (120 g aprox)'\n"
        "   Aplica a: guisados, carnes, cereales cocidos, leguminosas, "
        "verduras cocidas, quesos. Es decir, todo lo que se sirve a ojo.\n\n"
        "3) Las cantidades van en medidas caseras mexicanas: taza, media taza, "
        "1/3 de taza, cucharada (cda), cucharadita (cdita), pieza, rebanada, "
        "paquetito, filete, scoop. La proteina animal siempre lleva ademas su "
        "gramaje.\n\n"
        "Fracciones que SI son practicas porque el alimento se divide bien: "
        "1/3 de aguacate, 1/2 taza de arroz, 1/2 platano, 1/4 de taza de "
        "frutos secos.\n"
        "- Usa alimentos reales de la cocina mexicana. Nada de ultraprocesados.\n"
        "- Propon entre 3 y 4 opciones por tiempo de comida, variadas entre si.\n"
        "\nPORCIONES, NO TE PASES:\n"
        "Cada comida principal debe quedar entre 25 y 30 g de proteina, y las "
        "colaciones entre 15 y 25 g. Es el rango que prescribe la nutriologa.\n"
        "Una comida de 45 o 50 g de proteina desbarata la distribucion del dia "
        "y es mas comida de la que el paciente va a terminar.\n\n"
        "Antes de cerrar cada opcion, suma mentalmente la proteina de sus "
        "alimentos usando la tabla de pesos. Si te pasas del rango, REDUCE las "
        "porciones de proteina animal, que es de donde viene el grueso:\n"
        "  - 120 g de pechuga de pollo dan unos 27 g de proteina, no pongas 150\n"
        "  - 3 huevos dan unos 19 g, no agregues ademas queso y pavo\n"
        "  - Una sola fuente de proteina animal por comida suele bastar\n\n"
        "Regla practica: si una opcion lleva dos fuentes de proteina animal "
        "(carne mas queso, huevo mas jamon), probablemente te pasaste.\n\n"
        "- No inventes cantidades desproporcionadas. Verifica que la suma de "
        "proteina se acerque al objetivo.\n"
        "- Respeta las alergias, intolerancias y alimentos que el paciente evita.\n"
        "- Si detectas algo que requiere atencion medica y no nutricional, "
        "ponlo en advertencias. Nunca diagnostiques.\n"
        "- No cuentes ni menciones calorias."
    )

    return "".join(partes)


def generar_plan(paciente, historia, medicion, padecimientos=None,
                 usa_glp1=False, es_deportista=False, esta_embarazada=False,
                 opciones_previas=None, retroalimentacion_followup=None, incluir_kb=True):
    """
    Genera el plan tecnico completo para un paciente.
    Devuelve el plan como diccionario, mas metadatos del proceso.
    """
    prompt = construir_prompt(
        paciente, historia, medicion,
        padecimientos=padecimientos,
        usa_glp1=usa_glp1,
        es_deportista=es_deportista,
        esta_embarazada=esta_embarazada,
        opciones_previas=opciones_previas,
        retroalimentacion_followup=retroalimentacion_followup,
        incluir_kb=incluir_kb,
    )

    plan = gemini.generar_json(prompt)

    # La aritmetica la hace el sistema, no la IA. Se recalcula la proteina
    # de cada opcion desde la BAM y el USDA, y se sobrescribe lo que estimo
    # el modelo. La estimacion original queda guardada para auditoria.
    correcciones = verificador.recalcular_plan(plan)

    objetivo = plan.get("objetivo_proteina_g")
    reporte = verificador.verificar_plan(plan, objetivo_proteina_g=objetivo)
    reporte["correcciones_aplicadas"] = correcciones

    return {
        "plan": plan,
        "verificacion": reporte,
        "meta": {
            "modelo": gemini.MODELO_ANALISIS,
            "tamano_prompt_kb": len(prompt) // 1024,
            "temas_kb": temas_del_caso(padecimientos, usa_glp1),
            "incluyo_kb": incluir_kb,
        },
    }
