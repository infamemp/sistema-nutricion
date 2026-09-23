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
            lineas.append("Edad: " + str(paciente["edad"]) + " años")
        if paciente.get("estatura"):
            lineas.append("Estatura: " + str(paciente["estatura"]) + " cm")
        if paciente.get("motivo_consulta"):
            lineas.append("Motivo de consulta: " + str(paciente["motivo_consulta"]))

    if medicion:
        lineas.append("")
        titulo = "MEDICIÓN MÁS RECIENTE"
        if medicion.get("fecha_medicion"):
            titulo += " (" + str(medicion["fecha_medicion"])[:10] + ")"
        lineas.append(titulo)
        for campo, etiqueta in [
            ("peso", "Peso (kg)"),
            ("imc", "IMC"),
            ("porcentaje_grasa", "Grasa corporal (%)"),
            ("masa_grasa_kg", "Masa grasa (kg)"),
            ("mme", "Masa muscular esquelética (kg)"),
            ("grasa_visceral", "Grasa visceral"),
            ("tasa_metabolica_basal", "Tasa metabólica basal (kcal, dato interno)"),
        ]:
            valor = medicion.get(campo)
            if valor is not None:
                lineas.append("  " + etiqueta + ": " + str(valor))

    if historia:
        lineas.append("")
        lineas.append("HISTORIA CLÍNICA")

        bloques = [
            ("Objetivos del paciente", ["objetivo_que_espera", "objetivo_importante"]),
            ("Plazo que espera", ["objetivo_tiempo"]),
            ("Padecimientos", ["padecimientos_diagnosticados"]),
            ("Cirugías", ["cirugias"]),
            ("Tratamiento médico actual", ["tratamiento_medico_actual"]),
            ("Medicamentos", ["medicamentos"]),
            ("Suplementos", ["suplementos"]),
            ("Alergias", ["alergias"]),
            ("Intolerancias", ["intolerancias"]),
            ("Alimentos que evita", ["alimentos_evitar"]),
            ("Restricciones por elección", ["restricciones_eleccion"]),
            ("Qué come normalmente", ["recordatorio_desayuno", "recordatorio_comida",
                                      "recordatorio_cena", "recordatorio_snacks"]),
            ("Quién cocina", ["quien_cocina"]),
            ("Hidratación", ["hidratacion"]),
            ("Ejercicio", ["ejercicio_rutina"]),
            ("Sueño", ["sueno"]),
            ("Alcohol", ["alcohol"]),
            ("Tabaco", ["tabaco"]),
            ("Nivel de estrés (1 a 10)", ["nivel_estres"]),
            ("Historia de peso", ["peso_maximo", "peso_minimo", "edad_inicio_sobrepeso",
                                  "dietas_previas"]),
        ]

        for etiqueta, campos in bloques:
            valores = [str(historia.get(c)) for c in campos if historia.get(c)]
            if valores:
                lineas.append("  " + etiqueta + ": " + " | ".join(valores))

        antecedentes = []
        for campo, nombre in [
            ("antecedente_diabetes", "diabetes"),
            ("antecedente_obesidad", "obesidad"),
            ("antecedente_tiroides", "tiroides"),
            ("antecedente_hipertension", "hipertensión"),
            ("antecedente_cardiovascular", "cardiovascular"),
            ("antecedente_cancer", "cáncer"),
            ("antecedente_otros", "otros"),
        ]:
            if historia.get(campo):
                antecedentes.append(nombre + ": " + str(historia[campo]))
        if antecedentes:
            lineas.append("  Antecedentes familiares: " + " | ".join(antecedentes))

        gineco = []
        for campo, nombre in [
            ("gineco_menarca", "menarca"),
            ("gineco_ciclo", "ciclo"),
            ("gineco_anticonceptivo", "anticonceptivo"),
            ("gineco_embarazos", "embarazos"),
            ("gineco_busca_embarazo", "busca embarazo"),
            ("gineco_menopausia", "menopausia"),
        ]:
            if historia.get(campo):
                gineco.append(nombre + ": " + str(historia[campo]))
        if gineco:
            lineas.append("  Ginecológico: " + " | ".join(gineco))

        sintomas = []
        for campo, nombre in [
            ("sint_gastrointestinal", "gastrointestinales"),
            ("sint_distension", "distensión"),
            ("sint_hormigueo", "hormigueo"),
            ("sint_caida_pelo", "caída de pelo"),
            ("sint_unas_debiles", "uñas débiles"),
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
            lineas.append("  Síntomas: " + " | ".join(sintomas))

    return "\n".join(lineas)


def _seccion_seguimiento(retroalimentacion_followup=None, notas_paciente=None):
    """
    Arma el bloque de lo que se recabó en la consulta de seguimiento y en
    la bitácora de notas del paciente. Es la información NUEVA del caso:
    sin ella, la IA no tiene motivo para cambiar el plan.
    Devuelve texto vacío si no hay nada que agregar.
    """
    partes = []

    if retroalimentacion_followup:
        f = retroalimentacion_followup
        titulo = "ÚLTIMA CONSULTA DE SEGUIMIENTO"
        detalles = []
        if f.get("numero_consulta"):
            detalles.append("consulta " + str(f["numero_consulta"]))
        if f.get("fecha_consulta"):
            detalles.append(str(f["fecha_consulta"])[:10])
        if detalles:
            titulo += " (" + ", ".join(detalles) + ")"
        partes.append(titulo + "\n")

        etiquetas = [
            ("porcentaje_apego", "Apego al plan anterior (%)"),
            ("promedio_dias_ejercicio", "Promedio de días de ejercicio por semana"),
            ("que_le_gusto", "Qué le gustó del plan anterior"),
            ("que_no_le_gusto", "Qué no le gustó"),
            ("cambios_que_hizo", "Cambios que hizo por su cuenta"),
            ("en_que_puede_mejorar", "En qué puede mejorar"),
            ("estatus_tratamiento_medico", "Estatus del tratamiento médico"),
            ("ajustes_acordados", "Ajustes ya acordados con la nutrióloga"),
            ("notas_libres", "Observaciones de la nutrióloga en esta consulta"),
        ]
        for campo, etiqueta in etiquetas:
            valor = f.get(campo)
            if valor is not None and valor != "":
                partes.append("  " + etiqueta + ": " + str(valor) + "\n")

    if notas_paciente:
        if partes:
            partes.append("\n")
        partes.append("NOTAS DE LA NUTRIÓLOGA SOBRE ESTE PACIENTE (la más reciente primero)\n")
        for n in notas_paciente:
            fecha = str(n.get("fecha") or "")[:10]
            texto = str(n.get("texto") or "").strip()
            if texto:
                partes.append("  - " + (fecha + ": " if fecha else "") + texto + "\n")

    if not partes:
        return ""

    return (
        "Lo siguiente es información nueva o actualizada del caso. Tiene "
        "prioridad sobre lo que diga la historia clínica cuando se contradigan, "
        "porque es más reciente. Úsala para adecuar el plan.\n\n"
        + "".join(partes)
    )


def _fecha_corta(f):
    """AAAA-MM-DD de un datetime, date o texto ISO."""
    return str(f)[:10] if f else ""


def _dias_entre(a, b):
    """Dias entre dos fechas (datetime o date); None si falta alguna."""
    if not a or not b:
        return None
    try:
        da = a.date() if hasattr(a, "date") and callable(a.date) else a
        db = b.date() if hasattr(b, "date") and callable(b.date) else b
        return (db - da).days
    except Exception:
        return None


def _delta(actual, previo):
    """Diferencia con signo y un decimal, ej. '-1.4' o '+0.2'."""
    if actual is None or previo is None:
        return None
    d = round(float(actual) - float(previo), 1)
    if d == 0:
        return "sin cambio"
    return ("+" if d > 0 else "\u2212") + str(abs(d))


def _seccion_evolucion(evolucion):
    """
    Bloque "Qué cambió": compara la medición actual contra la anterior y la
    inicial, y muestra la tendencia de apego y ejercicio de los últimos
    seguimientos. Las cifras las calcula el sistema, no la IA, para que
    sean exactas. Devuelve texto vacío si no hay nada que mostrar.

    evolucion = {
        "mediciones": [ {fecha_medicion, peso, porcentaje_grasa, ...}, ... ]
                      en orden cronológico (la última es la actual),
        "seguimientos": [ {numero_consulta, fecha_consulta,
                           porcentaje_apego, promedio_dias_ejercicio}, ... ]
                      en orden cronológico,
    }
    """
    if not evolucion:
        return ""

    lineas = []
    mediciones = [m for m in (evolucion.get("mediciones") or []) if m]

    if len(mediciones) == 1:
        lineas.append("Solo hay una medición registrada ("
                      + _fecha_corta(mediciones[0].get("fecha_medicion"))
                      + "); todavía no hay evolución que comparar.")
    elif len(mediciones) > 1:
        actual = mediciones[-1]
        inicial = mediciones[0]
        # La anterior es la más reciente de un DÍA distinto al de la actual,
        # para no comparar contra una captura duplicada del mismo día.
        anterior = None
        for m in reversed(mediciones[:-1]):
            if _fecha_corta(m.get("fecha_medicion")) != _fecha_corta(actual.get("fecha_medicion")):
                anterior = m
                break

        dias_ant = _dias_entre(anterior.get("fecha_medicion"), actual.get("fecha_medicion")) if anterior else None
        dias_ini = _dias_entre(inicial.get("fecha_medicion"), actual.get("fecha_medicion"))

        encabezado = "Mediciones registradas: " + str(len(mediciones))
        encabezado += " | inicial " + _fecha_corta(inicial.get("fecha_medicion"))
        if anterior:
            encabezado += " | anterior " + _fecha_corta(anterior.get("fecha_medicion"))
        encabezado += " | actual " + _fecha_corta(actual.get("fecha_medicion"))
        lineas.append(encabezado)

        for campo, etiqueta in [
            ("peso", "Peso (kg)"),
            ("porcentaje_grasa", "Grasa corporal (%)"),
            ("masa_grasa_kg", "Masa grasa (kg)"),
            ("mme", "Masa muscular esquelética (kg)"),
            ("grasa_visceral", "Grasa visceral"),
        ]:
            valor = actual.get(campo)
            if valor is None:
                continue
            linea = "  " + etiqueta + ": " + str(valor)
            if anterior:
                d = _delta(valor, anterior.get(campo))
                if d is not None:
                    linea += " | vs anterior: " + d
                    if dias_ant is not None:
                        linea += " en " + str(dias_ant) + " días"
            if inicial is not actual and inicial is not anterior:
                d = _delta(valor, inicial.get(campo))
                if d is not None:
                    linea += " | vs inicial: " + d
                    if dias_ini is not None:
                        linea += " en " + str(dias_ini) + " días"
            lineas.append(linea)

    seguimientos = [s for s in (evolucion.get("seguimientos") or []) if s]
    apegos = [s.get("porcentaje_apego") for s in seguimientos if s.get("porcentaje_apego") is not None]
    ejercicio = [s.get("promedio_dias_ejercicio") for s in seguimientos
                 if s.get("promedio_dias_ejercicio") is not None]
    if apegos:
        lineas.append("Apego al plan en los últimos seguimientos (%): "
                      + " \u2192 ".join(str(round(a)) for a in apegos))
    if ejercicio:
        lineas.append("Días de ejercicio por semana en los últimos seguimientos: "
                      + " \u2192 ".join(str(e) for e in ejercicio))

    if not lineas:
        return ""

    return (
        "Cifras calculadas por el sistema a partir del expediente; son exactas, "
        "no las recalcules.\n\n"
        + "\n".join(lineas)
        + "\n\nEsta evolución es el insumo principal para decidir qué ajustar. "
        "Identifica qué indica (avance, estancamiento, pérdida de masa muscular, "
        "aumento de grasa visceral, apego bajo o en descenso, etc.) y ajusta el "
        "plan en consecuencia. Un plan que no responde a la evolución del "
        "paciente no sirve.\n"
    )


# ---------------------------------------------------------------------
# CONTINUIDAD CON EL PLAN ANTERIOR (candado anti-copia)
# Marifer elige el modo antes de generar; el sistema verifica despues,
# con codigo y no con la IA, cuantas opciones se repitieron.
# ---------------------------------------------------------------------

MODOS_CONTINUIDAD = {
    "mantener": "Mantener",
    "renovar": "Renovar",
    "nuevo": "Menú nuevo",
}

_INSTRUCCION_MODO = {
    "mantener": (
        "MODO ELEGIDO POR LA NUTRIÓLOGA: MANTENER. El plan le está funcionando al "
        "paciente. Conserva las opciones del plan anterior y ajusta solo lo "
        "indispensable: porciones si cambió el objetivo, lo que no le gustó, y lo "
        "que la información nueva pida cambiar. Registra cada ajuste."
    ),
    "renovar": (
        "MODO ELEGIDO POR LA NUTRIÓLOGA: RENOVAR. Conserva lo que le funcionó al "
        "paciente, pero incluye AL MENOS 1 opción nueva en CADA tiempo de comida "
        "(desayuno, colación, comida y cena)."
    ),
    "nuevo": (
        "MODO ELEGIDO POR LA NUTRIÓLOGA: MENÚ NUEVO. La mayoría de las opciones de "
        "cada tiempo de comida deben ser nuevas. Conserva COMO MÁXIMO 1 opción por "
        "tiempo de comida, y solo si el paciente dijo explícitamente que le gustó. "
        "Puedes reutilizar alimentos que el paciente disfruta, pero en "
        "preparaciones o combinaciones distintas."
    ),
}

_PALABRAS_VACIAS = set("""
de del la las el los y o u con sin en a al por para su sus un una unos unas
taza tazas cda cdas cdita cditas cucharada cucharadas cucharadita cucharaditas
pieza piezas rebanada rebanadas filete filetes lata latas paquetito paquetitos
scoop g gr gramos kg ml aprox aproximadamente media medio mitad mitades tercio
cuarto cuartos entero enteros entera enteras al gusto natural sin azucar
acompanado acompanada acompanados acompanadas servido servida preparado preparada
opcion elige mas
""".split())


def _sin_acentos(texto):
    import unicodedata
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _palabras_clave(texto):
    """Palabras que identifican una opcion: alimentos y preparaciones,
    sin cantidades, medidas ni conectores."""
    import re
    t = _sin_acentos(texto)
    t = re.sub(r"[^a-z\s]", " ", t)
    palabras = set()
    for p in t.split():
        if len(p) < 3 or p in _PALABRAS_VACIAS:
            continue
        # plural simple: "huevos" y "huevo" cuentan igual
        if p.endswith("es") and len(p) > 5:
            p = p[:-2]
        elif p.endswith("s") and len(p) > 4:
            p = p[:-1]
        palabras.add(p)
    return palabras


def _parecido(a, b):
    """Indice de Jaccard entre las palabras clave de dos opciones (0 a 1)."""
    pa, pb = _palabras_clave(a), _palabras_clave(b)
    if not pa or not pb:
        return 0.0
    return len(pa & pb) / len(pa | pb)


# A partir de este parecido, una opcion cuenta como repetida del plan
# anterior (misma combinacion, aunque cambien cantidades o un detalle menor).
UMBRAL_REPETIDA = 0.6

_NOMBRES_TIEMPO = {
    "desayuno": "Desayuno", "colacion": "Colación", "comida": "Comida", "cena": "Cena",
}


def comparar_con_anterior(menu_nuevo, opciones_previas, modo="renovar"):
    """
    Compara las opciones del menu nuevo contra las del plan anterior, por
    tiempo de comida. No usa IA.

    menu_nuevo: {"desayuno": {"opciones": [...]}, ...}  (documento redactado)
    opciones_previas: {"desayuno": [...], ...}
    Devuelve un resumen con el total repetido y las alertas segun el modo.
    """
    resultado = {"modo": modo, "total": 0, "repetidas": 0, "por_tiempo": {}, "alertas": []}
    if not opciones_previas:
        return resultado

    for tiempo, datos in (menu_nuevo or {}).items():
        nuevas = (datos or {}).get("opciones", []) or []
        previas = opciones_previas.get(tiempo) or []
        repetidas = []
        for op in nuevas:
            if any(_parecido(op, pr) >= UMBRAL_REPETIDA for pr in previas):
                repetidas.append(op)
        total = len(nuevas)
        resultado["total"] += total
        resultado["repetidas"] += len(repetidas)
        resultado["por_tiempo"][tiempo] = {
            "total": total,
            "repetidas": repetidas,
            "nuevas": total - len(repetidas),
        }

        nombre = _NOMBRES_TIEMPO.get(tiempo, tiempo)
        if not previas or not total:
            continue
        if modo == "renovar" and len(repetidas) == total:
            resultado["alertas"].append(nombre + ": sin opciones nuevas (el modo Renovar pide al menos 1).")
        elif modo == "nuevo" and len(repetidas) > 1:
            resultado["alertas"].append(
                nombre + ": " + str(len(repetidas)) + " opciones repetidas "
                "(el modo Menú nuevo permite como máximo 1)."
            )

    return resultado


def comparar_tablas_porciones(doc_nuevo, tablas_anteriores):
    """
    Compara, sin IA, las tablas de la Tabla de Porciones nueva contra las
    aprobadas antes: que alimento se agrego o se quito por tabla, y si la
    meta de proteina cambio. A diferencia del Menu, repetir alimentos aqui
    es normal (es una lista de referencia); lo que importa es que la meta
    se actualice y que se reflejen los cambios pedidos.
    """
    resultado = {"meta_cambio": None, "por_tabla": {}}
    if not tablas_anteriores:
        return resultado

    meta_antes = (tablas_anteriores.get("meta_proteina") or "").strip()
    meta_ahora = (doc_nuevo.get("meta_proteina") or "").strip()
    if meta_antes and meta_ahora and meta_antes != meta_ahora:
        resultado["meta_cambio"] = {"antes": meta_antes, "ahora": meta_ahora}

    nombres = {
        "tabla_proteinas": "Proteínas",
        "tabla_carbohidratos": "Carbohidratos",
        "tabla_grasas": "Grasas",
    }
    for campo, etiqueta in nombres.items():
        anterior = tablas_anteriores.get(campo)
        nueva = doc_nuevo.get(campo)
        lista_antes = anterior if isinstance(anterior, list) else (anterior or {}).get("alimentos", [])
        lista_ahora = nueva if isinstance(nueva, list) else (nueva or {}).get("alimentos", [])
        if not lista_antes and not lista_ahora:
            continue
        nombres_antes = {_sin_acentos(f.get("alimento", "")).strip() for f in lista_antes if f.get("alimento")}
        nombres_ahora = {_sin_acentos(f.get("alimento", "")).strip() for f in lista_ahora if f.get("alimento")}
        agregados = [f.get("alimento") for f in lista_ahora
                     if _sin_acentos(f.get("alimento", "")).strip() not in nombres_antes]
        retirados = [f.get("alimento") for f in lista_antes
                     if _sin_acentos(f.get("alimento", "")).strip() not in nombres_ahora]
        if agregados or retirados:
            resultado["por_tabla"][etiqueta] = {"agregados": agregados, "retirados": retirados}

    return resultado


ESQUEMA_PLAN = """{
  "resumen_del_caso": "2 o 3 frases sobre la situación del paciente y el enfoque elegido",
  "banderas_clinicas": [
    {"tipo": "medicamento | padecimiento | laboratorio | sintoma",
     "detalle": "qué se detectó",
     "implicacion_nutricional": "qué significa para el plan",
     "accion": "qué hace el plan al respecto"}
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
  "recomendaciones": ["recomendación práctica 1", "recomendación 2"],
  "suplementacion_sugerida": [
    {"suplemento": "nombre", "dosis": "cantidad", "momento": "cuando", "motivo": "por qué"}
  ],
  "cambios_vs_plan_anterior": [
    {"aspecto": "suplementación | objetivos | desayuno | colación | comida | cena | recomendaciones",
     "cambio": "qué se cambió, se agregó o se quitó",
     "motivo": "por qué, ligado a un dato concreto: evolución, seguimiento, laboratorio, nota o decisión de la nutrióloga"}
  ],
  "notas_para_la_nutriologa": ["algo que conviene que revise o considere"],
  "advertencias": ["si algo del expediente requiere atención médica, no nutricional"]
}"""


def construir_prompt(paciente, historia, medicion, padecimientos=None,
                     usa_glp1=False, es_deportista=False, esta_embarazada=False,
                     opciones_previas=None, retroalimentacion_followup=None,
                     analisis_laboratorio=None, incluir_kb=True, notas_paciente=None,
                     evolucion=None, plan_anterior=None, decisiones_nutriologa=None,
                     modo_continuidad="renovar"):
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
        "Eres el motor de análisis nutricional de la consulta de Marifer Utrilla, "
        "nutrióloga en Puebla, México, especializada en obesidad, diabetes, "
        "resistencia a la insulina, SOP, endometriosis, salud hormonal, fertilidad "
        "y embarazo.\n\n"
        "Tu trabajo es ANALIZAR el caso y producir un PLAN TÉCNICO en JSON. "
        "No escribes para el paciente; otro sistema se encarga de la redacción final. "
        "Tu salida es un documento de trabajo para la nutrióloga.\n\n"
        "REGLA CENTRAL: razonas sobre este caso concreto. No aplicas plantillas ni "
        "repites fórmulas genéricas. Cada paciente es distinto y el plan debe "
        "reflejar su situación particular, sus preferencias y sus restricciones."
    )

    texto_evolucion = _seccion_evolucion(evolucion)
    if texto_evolucion:
        partes.append("\n\n" + ("=" * 70) + "\n")
        partes.append("QUÉ CAMBIÓ: EVOLUCIÓN DEL PACIENTE\n")
        partes.append(texto_evolucion)
        partes.append("Explica en resumen_del_caso, en una frase, qué indica la "
                      "evolución y cómo responde el plan.\n")

    if decisiones_nutriologa:
        partes.append("\n\n" + ("=" * 70) + "\n")
        partes.append("DECISIONES DE LA NUTRIÓLOGA: OBLIGATORIAS\n")
        partes.append(
            "Son indicaciones que la nutrióloga dio al ajustar planes anteriores de "
            "este paciente. Son decisiones clínicas suyas y se respetan SIEMPRE: el "
            "plan nuevo no puede contradecirlas. Van en orden cronológico; si dos se "
            "contradicen, manda la más reciente. Si con la información nueva crees que "
            "alguna debería cambiar, NO la cambies: mantenla y explica tu sugerencia "
            "en notas_para_la_nutriologa. Ejemplo: si ella indicó agregar un "
            "suplemento, ese suplemento aparece en suplementacion_sugerida; si indicó "
            "quitarlo, no aparece.\n\n"
        )
        for d in decisiones_nutriologa:
            etiqueta = "Versión " + str(d.get("version", "?"))
            if d.get("fecha"):
                etiqueta += " (" + _fecha_corta(d["fecha"]) + ")"
            partes.append("  - " + etiqueta + ": " + str(d.get("instruccion", "")).strip() + "\n")

    partes.append("\n\n" + ("=" * 70) + "\n")
    partes.append(_seccion_expediente(paciente, historia, medicion))

    partes.append("\n\n" + ("=" * 70) + "\n")
    partes.append("CRITERIOS DE PRESCRIPCIÓN DE LA NUTRIÓLOGA\n")
    partes.append("Estos criterios son de ella y no se negocian.\n\n")
    partes.append(reglas.resumen_para_prompt(
        peso, usa_glp1=usa_glp1,
        es_deportista=es_deportista,
        esta_embarazada=esta_embarazada,
    ))

    partes.append("\n\nJERARQUÍA DE DECISIÓN, en orden de prioridad:\n")
    for regla in reglas.jerarquia():
        partes.append("  " + regla + "\n")

    r = reglas.cargar()
    partes.append("\nGRASAS PERMITIDAS: " + ", ".join(r["grasa"]["preferidas"]))
    partes.append("\nGRASAS EXCLUIDAS por criterio de la nutrióloga: "
                  + ", ".join(r["grasa"]["excluidas"]))
    partes.append("\nFRUTAS PREFERIDAS: " + ", ".join(r["fruta"]["preferidas"]))
    partes.append("\nCARBOHIDRATOS PREFERIDOS: " + ", ".join(r["carbohidrato"]["preferidos"]))

    if "carnes_frias" in r:
        cf = r["carnes_frias"]
        partes.append("\n\nCARNES FRÍAS, distinción con criterio:")
        partes.append("\n  Evitar: " + ", ".join(cf["evitar"]["alimentos"]))
        partes.append("\n  Aceptables: " + ", ".join(cf["aceptables_con_criterio"]["alimentos"]))
        partes.append("\n  " + cf["regla"])

    if "principio_de_practicidad_sobre_pureza" in r:
        pp = r["principio_de_practicidad_sobre_pureza"]
        partes.append("\n\nPRINCIPIO DE PRACTICIDAD SOBRE PUREZA:\n  " + pp["regla"])
        partes.append("\n  " + pp["motivo"])
        partes.append("\n  " + pp["aplicacion"])

    seguimiento = _seccion_seguimiento(retroalimentacion_followup, notas_paciente)
    if seguimiento:
        partes.append("\n\n" + ("=" * 70) + "\n")
        partes.append("INFORMACIÓN DE SEGUIMIENTO\n")
        partes.append(seguimiento)

    if plan_anterior or opciones_previas:
        partes.append("\n\n" + ("=" * 70) + "\n")
        titulo = "PLAN ANTERIOR APROBADO"
        if plan_anterior and plan_anterior.get("version"):
            titulo += " (versión " + str(plan_anterior["version"]) + ")"
        partes.append(titulo + "\n")
        partes.append(
            "Es el plan que la nutrióloga aprobó y que el paciente siguió. El plan "
            "nuevo parte de aquí y se adecua a lo que cambió (evolución, seguimiento, "
            "notas, laboratorio). Copiarlo sin cambios no es aceptable, y cambiarlo "
            "todo sin motivo tampoco: puedes conservar lo que al paciente le funcionó "
            "(reajustando porciones si hace falta) y debes cambiar lo que no funcionó "
            "o lo que la información nueva pide cambiar.\n\n"
            "REGISTRA CADA CAMBIO en cambios_vs_plan_anterior: qué cambió y por qué, "
            "con un motivo concreto del expediente. Esto incluye la suplementación: "
            "no quites, agregues ni cambies un suplemento sin registrarlo ahí.\n\n"
        )
        partes.append(_INSTRUCCION_MODO.get(modo_continuidad, _INSTRUCCION_MODO["renovar"]) + "\n")
        partes.append(
            "Una opción nueva es una combinación distinta, no la misma opción con "
            "otra cantidad o con un ingrediente menor cambiado. En cualquier modo "
            "se respetan las decisiones de la nutrióloga, las alergias, "
            "intolerancias y alimentos que el paciente evita. Registra también en "
            "cambios_vs_plan_anterior, en una sola entrada con aspecto 'continuidad', "
            "qué opciones conservaste y por qué.\n\n"
        )

        if plan_anterior:
            for campo, etiqueta in [
                ("suplementacion", "Suplementación vigente"),
                ("objetivos_clave", "Objetivos"),
                ("recomendaciones", "Recomendaciones"),
            ]:
                valores = plan_anterior.get(campo) or []
                if valores:
                    partes.append(etiqueta.upper() + ":\n")
                    for v in valores:
                        partes.append("  - " + str(v) + "\n")
                    partes.append("\n")

        if opciones_previas:
            partes.append("OPCIONES DE MENÚ DEL PLAN ANTERIOR:\n")
            if isinstance(opciones_previas, dict):
                for tiempo, lista in opciones_previas.items():
                    if not lista:
                        continue
                    partes.append("  " + _NOMBRES_TIEMPO.get(tiempo, tiempo).upper() + ":\n")
                    for o in lista[:8]:
                        partes.append("    - " + str(o) + "\n")
            else:
                for o in opciones_previas[:30]:
                    partes.append("  - " + str(o) + "\n")

    if analisis_laboratorio:
        partes.append("\n\n" + ("=" * 70) + "\n")
        partes.append("ANÁLISIS DE LABORATORIO\n")
        partes.append(
            "La nutrióloga revisó explícitamente este resultado y decidió incluirlo "
            "para este plan. Tómalo en cuenta al definir el enfoque, las banderas "
            "clínicas (tipo 'laboratorio' si aplica), y cualquier ajuste nutricional "
            "relevante. No diagnostiques ni sugieras un padecimiento, solo la "
            "implicación nutricional.\n\n"
        )
        partes.append(str(analisis_laboratorio) + "\n")

    if incluir_kb:
        temas = temas_del_caso(padecimientos, usa_glp1)
        contexto = kb.contexto_para_caso(temas, max_fuentes=3)
        if contexto["total"] > 0:
            partes.append("\n\n" + ("=" * 70) + "\n")
            partes.append("CONOCIMIENTO CLÍNICO DE REFERENCIA\n")
            partes.append("Fuentes seleccionadas para este caso. Las de nivel A tienen "
                          "mayor autoridad clínica que las de nivel B.\n")
            partes.append(contexto["texto"])

    partes.append("\n\n" + ("=" * 70) + "\n")
    partes.append(
        "INSTRUCCIONES DE SALIDA\n\n"
        "Devuelve únicamente un JSON que siga exactamente este esquema:\n\n"
        + ESQUEMA_PLAN +
        "\n\nIMPORTANTE: escribe todo el texto en español correcto, con acentos "
        "y tildes donde corresponda (opción, proteína, día, según, más, "
        "nutrióloga, etc.), y usa la ñ cuando corresponda (año, tamaño, etc.). "
        "No generes texto sin acentos.\n"
        + "\\n\\nSOBRE 'cambios_vs_plan_anterior': solo tiene sentido si este prompt te compartió un plan o tabla anterior más arriba. Si no te compartió ninguno (es la primera vez que este paciente recibe este documento, o no hay versión aprobada previa), déjalo como una lista vacía []: no hay nada que comparar, y no hay 'cambio' en aplicar por primera vez una preferencia del seguimiento.\\n" +
        "\n\nReglas para llenarlo:\n"
        "\nCANTIDADES, LA REGLA MÁS IMPORTANTE:\n"
        "TODO alimento que aparezca en una opción DEBE llevar su cantidad. "
        "El paciente tiene que saber exactamente cuánto comer de cada cosa. "
        "Una descripción sin cantidades es inservible y será rechazada.\n\n"
        "MAL (no hagas esto):\n"
        "  'Huevos a la mexicana con frijoles refritos y aguacate'\n"
        "  'Tinga de pechuga de pollo con nopales y tostadas horneadas'\n\n"
        "BIEN (haz esto):\n"
        "  '3 huevos a la mexicana, 1/3 de taza de frijoles refritos (60 g aprox) "
        "en 1 cdita de aceite de oliva, 1/3 de aguacate y 2 tortillas de maíz'\n"
        "  '3/4 de taza de tinga de pechuga de pollo (120 g aprox), 2 nopales "
        "asados, 3 tostadas horneadas y 1/3 de aguacate'\n\n"
        "Cada alimento del campo 'alimentos' debe repetir esa cantidad en su "
        "campo 'cantidad'. La descripción y la lista de alimentos deben coincidir.\n\n"
        "\nPESOS REALES, NO LOS ESTIMES:\n"
        "Abajo tienes la tabla de pesos del sistema. Es la referencia "
        "autoritativa. NO calcules gramajes de memoria: un error típico es "
        "decir que 2 rebanadas de pechuga de pavo pesan 60 g cuando pesan 24. "
        "\nSI UN ALIMENTO NO ESTÁ EN LA TABLA:\n"
        "Preferentemente elige otro que sí esté, porque el sistema solo puede "
        "verificar los que conoce. Si de verdad necesitas usarlo, hazlo pero "
        "avisa en notas_para_la_nutriologa con esta forma: 'El alimento X no "
        "está en la tabla de pesos del sistema, su gramaje es estimado y "
        "conviene verificarlo.' Nunca inventes un peso sin avisar.\n\n"
        + _tabla_de_pesos() +
        "\n\nPRACTICIDAD, TAN IMPORTANTE COMO LA EXACTITUD:\n"
        "El paciente va a preparar esto en su cocina, no en un laboratorio. "
        "Una cantidad correcta pero impracticable no sirve.\n\n"
        "1) ALIMENTOS ENTEROS NO SE FRACCIONAN. Los que vienen en unidades "
        "indivisibles se prescriben completos o no se prescriben. Nadie parte "
        "un huevo a la mitad, ni guarda media lata de atún abierta, ni deja "
        "1.5 tostadas en un paquete abierto que se pone aguado.\n"
        "   MAL: '2.5 huevos', 'media lata de atún', '1.5 tostadas salmas'\n"
        "   BIEN: '3 huevos', '1 lata de atún', '1 paquetito de salmas'\n"
        "   Aplica a: huevos, latas, paquetitos de salmas, piezas de fruta, "
        "filetes, tortillas, rebanadas de pan, scoops de proteína.\n"
        "   Si el cálculo da una fracción, redondea a la unidad entera más "
        "cercana y ajusta el resto de la comida para compensar.\n\n"
        "2) DOBLE REFERENCIA EN LO QUE SE SIRVE A OJO. Nadie mide la tinga o "
        "un bistec con taza medidora, pero con una referencia visual más el "
        "gramaje aproximado sí puede calcular.\n"
        "   MAL: '3/4 de taza de tinga'\n"
        "   BIEN: '3/4 de taza de tinga de pollo (120 g aprox)'\n"
        "   Aplica a: guisados, carnes, cereales cocidos, leguminosas, "
        "verduras cocidas, quesos. Es decir, todo lo que se sirve a ojo.\n\n"
        "3) Las cantidades van en medidas caseras mexicanas: taza, media taza, "
        "1/3 de taza, cucharada (cda), cucharadita (cdita), pieza, rebanada, "
        "paquetito, filete, scoop. La proteína animal siempre lleva además su "
        "gramaje.\n\n"
        "Fracciones que SÍ son prácticas porque el alimento se divide bien: "
        "1/3 de aguacate, 1/2 taza de arroz, 1/2 plátano, 1/4 de taza de "
        "frutos secos.\n"
        "- Usa alimentos reales de la cocina mexicana. Nada de ultraprocesados.\n"
        "- Propón entre 3 y 4 opciones por tiempo de comida, variadas entre sí.\n"
        "\nPORCIONES, NO TE PASES:\n"
        "Cada comida principal debe quedar entre 25 y 30 g de proteína, y las "
        "colaciones entre 15 y 25 g. Es el rango que prescribe la nutrióloga.\n"
        "Una comida de 45 o 50 g de proteína desbarata la distribución del día "
        "y es más comida de la que el paciente va a terminar.\n\n"
        "Antes de cerrar cada opción, suma mentalmente la proteína de sus "
        "alimentos usando la tabla de pesos. Si te pasas del rango, REDUCE las "
        "porciones de proteína animal, que es de donde viene el grueso:\n"
        "  - 120 g de pechuga de pollo dan unos 27 g de proteína, no pongas 150\n"
        "  - 3 huevos dan unos 19 g, no agregues además queso y pavo\n"
        "  - Una sola fuente de proteína animal por comida suele bastar\n\n"
        "Regla práctica: si una opción lleva dos fuentes de proteína animal "
        "(carne más queso, huevo más jamón), probablemente te pasaste.\n\n"
        "- No inventes cantidades desproporcionadas. Verifica que la suma de "
        "proteína se acerque al objetivo.\n"
        "- Respeta las alergias, intolerancias y alimentos que el paciente evita.\n"
        "- Si detectas algo que requiere atención médica y no nutricional, "
        "ponlo en advertencias. Nunca diagnostiques.\n"
        "- No cuentes ni menciones calorías."
    )

    return "".join(partes)


def generar_plan(paciente, historia, medicion, padecimientos=None,
                 usa_glp1=False, es_deportista=False, esta_embarazada=False,
                 opciones_previas=None, retroalimentacion_followup=None,
                 analisis_laboratorio=None, incluir_kb=True, notas_paciente=None,
                 evolucion=None, plan_anterior=None, decisiones_nutriologa=None,
                 modo_continuidad="renovar"):
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
        analisis_laboratorio=analisis_laboratorio,
        incluir_kb=incluir_kb,
        notas_paciente=notas_paciente,
        evolucion=evolucion,
        plan_anterior=plan_anterior,
        decisiones_nutriologa=decisiones_nutriologa,
        modo_continuidad=modo_continuidad,
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


def construir_prompt_porciones(paciente, historia, medicion, incluir_ejemplos, padecimientos=None,
                               usa_glp1=False, es_deportista=False, esta_embarazada=False, incluir_kb=True,
                               retroalimentacion_followup=None, notas_paciente=None,
                               analisis_laboratorio=None, evolucion=None,
                               tablas_anteriores=None, decisiones_nutriologa=None):
    """
    Arma el prompt para la "Tabla de Porciones": un formato de prescripcion
    mas simple que el menu completo, para pacientes que no quieren un menu
    armado, solo un marco de referencia de cuanta proteina, carbohidrato y
    grasa consumir, y arman su propia comida.

    A diferencia del menu (construir_prompt), este documento sale directo
    de Gemini sin pasar por Claude: es mas tabla de datos que redaccion, no
    necesita "voz".
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
        "Eres el motor de análisis nutricional de la consulta de Marifer Utrilla, "
        "nutrióloga en Puebla, México, especializada en obesidad, diabetes, "
        "resistencia a la insulina, SOP, endometriosis, salud hormonal, fertilidad "
        "y embarazo.\n\n"
        "Tu trabajo es generar una 'TABLA DE PORCIONES': un formato de prescripción "
        "más simple que un menú armado. Es para pacientes que no quieren recibir "
        "opciones de comida ya combinadas, solo quieren saber cuántos gramos de "
        "proteína, carbohidrato y grasa consumir por comida, y ellos arman su "
        "propio plato con esa referencia.\n\n"
        "REGLA CENTRAL: razonas sobre este caso concreto, no aplicas una plantilla "
        "genérica. El paciente y sus restricciones son los que determinan qué "
        "alimentos incluir en cada tabla."
    )

    texto_evolucion = _seccion_evolucion(evolucion)
    if texto_evolucion:
        partes.append("\n\n" + ("=" * 70) + "\n")
        partes.append("QUÉ CAMBIÓ: EVOLUCIÓN DEL PACIENTE\n")
        partes.append(texto_evolucion)

    if decisiones_nutriologa:
        partes.append("\n\n" + ("=" * 70) + "\n")
        partes.append("DECISIONES DE LA NUTRIÓLOGA: OBLIGATORIAS\n")
        partes.append(
            "Son indicaciones que la nutrióloga dio al ajustar planes anteriores de "
            "este paciente. Son decisiones clínicas suyas y se respetan SIEMPRE. Van "
            "en orden cronológico; si dos se contradicen, manda la más reciente. Si "
            "con la información nueva crees que alguna debería cambiar, NO la "
            "cambies: mantenla y explica tu sugerencia en notas_para_la_nutriologa.\n\n"
        )
        for d in decisiones_nutriologa:
            etiqueta = "Versión " + str(d.get("version", "?"))
            if d.get("fecha"):
                etiqueta += " (" + _fecha_corta(d["fecha"]) + ")"
            partes.append("  - " + etiqueta + ": " + str(d.get("instruccion", "")).strip() + "\n")

    if tablas_anteriores:
        partes.append("\n\n" + ("=" * 70) + "\n")
        partes.append("TABLA DE PORCIONES ANTERIOR APROBADA\n")
        partes.append(
            "Es la tabla que la nutrióloga aprobó y que el paciente ya usa como "
            "referencia. Repetir un alimento no es un problema, es normal en este "
            "formato. Lo que sí debes hacer es AJUSTAR lo que la información nueva "
            "pida: actualizar la meta de proteína si cambió el peso o el objetivo, "
            "quitar alimentos que el paciente dijo que no le gustan o no tolera, y "
            "agregar los que reporte que sí disfruta. Copiar la tabla sin revisar "
            "nada tampoco es aceptable.\n\n"
            "REGISTRA CADA CAMBIO en cambios_vs_plan_anterior: qué cambió y por qué, "
            "con un motivo concreto del expediente.\n\n"
        )
        if tablas_anteriores.get("meta_proteina"):
            partes.append("Meta anterior: " + str(tablas_anteriores["meta_proteina"]) + "\n\n")
        for campo, etiqueta in [
            ("tabla_proteinas", "PROTEÍNAS"), ("tabla_carbohidratos", "CARBOHIDRATOS"),
            ("tabla_grasas", "GRASAS"),
        ]:
            datos = tablas_anteriores.get(campo)
            lista = datos if isinstance(datos, list) else (datos or {}).get("alimentos", [])
            if lista:
                partes.append(etiqueta + ": " + ", ".join(
                    str(f.get("alimento", "")) for f in lista if f.get("alimento")) + "\n")

    partes.append("\n\n" + ("=" * 70) + "\n")
    partes.append(_seccion_expediente(paciente, historia, medicion))

    partes.append("\n\n" + ("=" * 70) + "\n")
    partes.append("CRITERIOS DE PRESCRIPCIÓN DE LA NUTRIÓLOGA\n")
    partes.append("Estos criterios son de ella y no se negocian.\n\n")
    partes.append(reglas.resumen_para_prompt(
        peso, usa_glp1=usa_glp1,
        es_deportista=es_deportista,
        esta_embarazada=esta_embarazada,
    ))

    r = reglas.cargar()
    partes.append("\nGRASAS PERMITIDAS: " + ", ".join(r["grasa"]["preferidas"]))
    partes.append("\nGRASAS EXCLUIDAS por criterio de la nutrióloga: "
                  + ", ".join(r["grasa"]["excluidas"]))
    partes.append("\nFRUTAS PREFERIDAS: " + ", ".join(r["fruta"]["preferidas"]))
    partes.append("\nCARBOHIDRATOS PREFERIDOS: " + ", ".join(r["carbohidrato"]["preferidos"]))

    seguimiento = _seccion_seguimiento(retroalimentacion_followup, notas_paciente)
    if seguimiento:
        partes.append("\n\n" + ("=" * 70) + "\n")
        partes.append("INFORMACIÓN DE SEGUIMIENTO\n")
        partes.append(seguimiento)

    if analisis_laboratorio:
        partes.append("\n\n" + ("=" * 70) + "\n")
        partes.append("ANÁLISIS DE LABORATORIO\n")
        partes.append(
            "La nutrióloga revisó explícitamente este resultado y decidió incluirlo "
            "para este plan. Tómalo en cuenta al elegir los alimentos de cada tabla. "
            "No diagnostiques ni sugieras un padecimiento, solo la implicación "
            "nutricional.\n\n"
        )
        partes.append(str(analisis_laboratorio) + "\n")

    if incluir_kb:
        temas = temas_del_caso(padecimientos, usa_glp1)
        contexto = kb.contexto_para_caso(temas, max_fuentes=3)
        if contexto["total"] > 0:
            partes.append("\n\n" + ("=" * 70) + "\n")
            partes.append("CONOCIMIENTO CLÍNICO DE REFERENCIA\n")
            partes.append(contexto["texto"])

    partes.append("\n\n" + ("=" * 70) + "\n")
    partes.append("TABLA DE PESOS DEL SISTEMA, REFERENCIA AUTORITATIVA\n")
    partes.append("NO calcules gramajes de memoria, usa esta tabla:\n\n")
    partes.append(_tabla_de_pesos())

    if incluir_ejemplos:
        instruccion_ejemplos = (
            "Es la PRIMERA VEZ que este paciente recibe una Tabla de Porciones. "
            "Incluye en el campo \"ejemplos\" tres combinaciones reales de plato "
            "(desayuno, comida, cena) que usen las tres tablas juntas, para que "
            "el paciente entienda cómo se ve una comida armada con este sistema."
        )
    else:
        instruccion_ejemplos = (
            "Este paciente YA ha usado el formato de Tabla de Porciones antes. "
            "NO incluyas ejemplos de comidas armadas esta vez: el campo "
            "\"ejemplos\" debe ir como null."
        )

    partes.append("\n\n" + ("=" * 70) + "\n")
    partes.append(
        "INSTRUCCIONES DE SALIDA\n\n"
        "Devuelve ÚNICAMENTE un JSON con este esquema exacto, sin texto fuera del JSON:\n\n"
        "{\n"
        '  "meta_proteina": "texto tipo \'Meta: 25 g de proteína por comida (4 veces al día) = 100g de proteína diaria.\'",\n'
        '  "instruccion_general": "texto tipo \'Elige 1 opción en desayuno, comida y cena + 1 colación.\'",\n'
        '  "tabla_proteinas": [\n'
        '    {"alimento": "nombre del alimento", "cantidad": "medida casera y/o gramos, ej. \'90 g\' o \'1 lata de 140g\'"}\n'
        "  ],\n"
        '  "objetivo_distribucion": ["Desayuno: 1 opción", "Comida: 1 opción", "Cena: 1 opción", "Colación: ..."],\n'
        '  "tabla_carbohidratos": {\n'
        '    "instruccion": "texto tipo \'Desayuno: 2 opciones (ejemplo: 1 tortilla + 1/2 taza de papaya)...\'",\n'
        '    "alimentos": [{"alimento": "...", "cantidad": "medida casera SIN gramos, ej. \'1 a 2 piezas\' o \'1/2 taza\'"}]\n'
        "  },\n"
        '  "tabla_grasas": {\n'
        '    "instruccion": "texto tipo \'GRASAS: 3 PORCIONES AL DÍA DISTRIBUIDAS\'",\n'
        '    "alimentos": [{"alimento": "...", "cantidad": "medida casera SIN gramos, ej. \'10 piezas\' o \'1 cucharadita\'"}]\n'
        "  },\n"
        '  "nota_verduras": "texto recomendando tazas de verdura al día, repartidas en las comidas",\n'
        '  "metas_diarias": ["3 porciones buenas de proteína", "2-3 frutas", "3-4 tazas de verduras", "2-3 L de agua", "Fuerza X veces/semana", "X pasos diarios"],\n'
        '  "ejemplos": {"desayuno": ["..."], "comida": ["..."], "cena": ["..."]},\n'
        '  "cambios_vs_plan_anterior": [\n'
        '    {"aspecto": "meta_proteina | tabla_proteinas | tabla_carbohidratos | tabla_grasas",\n'
        '     "cambio": "qué se cambió, agregó o quitó",\n'
        '     "motivo": "por qué, ligado a un dato concreto: evolución, seguimiento, laboratorio, nota o decisión de la nutrióloga"}\n'
        "  ],\n"
        '  "notas_para_la_nutriologa": ["algo que conviene que revise o considere"]\n'
        "}\n\n"
        "IMPORTANTE: escribe todo el texto en español correcto, con acentos y "
        "tildes donde corresponda (proteína, colación, día, opción, después, "
        "según, etc.). No generes texto sin acentos.\n"
        + "\\n\\nSOBRE 'cambios_vs_plan_anterior': solo tiene sentido si este prompt te compartió un plan o tabla anterior más arriba. Si no te compartió ninguno (es la primera vez que este paciente recibe este documento, o no hay versión aprobada previa), déjalo como una lista vacía []: no hay nada que comparar, y no hay 'cambio' en aplicar por primera vez una preferencia del seguimiento.\\n" + "\n"
        + instruccion_ejemplos + "\n\n"
        "FORMATO DE CANTIDAD SEGÚN LA TABLA (esto es distinto para cada una):\n"
        "- tabla_proteinas: la cantidad SIEMPRE lleva su gramaje (ej. '120 g', "
        "'1 lata de 140 g'), además de la medida casera si aplica. Esto no cambia, "
        "la proteína sí necesita precisarse en gramos.\n"
        "- tabla_carbohidratos y tabla_grasas: la cantidad NUNCA lleva gramos ni "
        "menciona el tamaño de empaque comercial (paquetito, bolsa). Usa "
        "únicamente la medida casera que el paciente puede contar sin báscula: "
        "pieza, taza, cucharada o cucharadita. Motivo: el gramo invita al "
        "paciente a pesar su porción, y una variación normal de peso (una "
        "almendra un poco más grande, un aguacate un poco más chico) no cambia "
        "el resultado de la dieta, pero sí genera angustia innecesaria si el "
        "número exacto no cuadra en la báscula.\n"
        "   MAL: 'Almendras - 10 piezas (10 a 12 g)', "
        "'Salmas - 1 paquetito = 30 g (5 piezas)', 'Arroz - 1/2 taza (79 a 98 g)'\n"
        "   BIEN: 'Almendras - 10 piezas', 'Salmas - 5 piezas', "
        "'Tortilla de maíz - 1 a 2 piezas', 'Arroz - 1/2 taza'\n\n"
        "REGLA DE PORCIONES: cada renglón de tabla_proteinas debe aportar "
        "aproximadamente la misma cantidad de proteína por porción (la que "
        "definas en meta_proteina, dividida entre el número de comidas). Usa "
        "la tabla de pesos de arriba para las conversiones, nunca inventes "
        "un gramaje.\n\n"
        "- Usa alimentos reales de la cocina mexicana, nada de ultraprocesados.\n"
        "- Respeta alergias, intolerancias, y alimentos que el paciente evita.\n"
        "- No cuentes ni menciones calorías."
    )

    return "".join(partes)


def generar_tabla_porciones(paciente, historia, medicion, incluir_ejemplos, padecimientos=None,
                            usa_glp1=False, es_deportista=False, esta_embarazada=False, incluir_kb=True,
                            retroalimentacion_followup=None, notas_paciente=None,
                            analisis_laboratorio=None, evolucion=None,
                            tablas_anteriores=None, decisiones_nutriologa=None):
    """
    Genera una Tabla de Porciones. A diferencia de generar_plan(), el
    resultado de Gemini se usa directo como documento final, sin pasar por
    Claude (es tabla de datos, no redaccion).

    Verifica cada renglon de tabla_proteinas contra la base de datos
    nutricional real (BAM/USDA), igual que se hace con el menu, pero sin
    ajustar automaticamente la cantidad: solo reporta si algo no se pudo
    verificar, para que la nutriologa lo revise.
    """
    prompt = construir_prompt_porciones(
        paciente, historia, medicion, incluir_ejemplos,
        padecimientos=padecimientos,
        usa_glp1=usa_glp1,
        es_deportista=es_deportista,
        esta_embarazada=esta_embarazada,
        incluir_kb=incluir_kb,
        retroalimentacion_followup=retroalimentacion_followup,
        notas_paciente=notas_paciente,
        analisis_laboratorio=analisis_laboratorio,
        evolucion=evolucion,
        tablas_anteriores=tablas_anteriores,
        decisiones_nutriologa=decisiones_nutriologa,
    )

    documento = gemini.generar_json(prompt)

    problemas = []
    for fila in documento.get("tabla_proteinas", []) or []:
        nutrientes, problema = verificador.nutrientes_de_alimento(fila.get("alimento", ""), fila.get("cantidad", ""))
        if problema:
            problemas.append({"alimento": fila.get("alimento"), "cantidad": fila.get("cantidad"), "detalle": problema})
        else:
            fila["proteina_verificada_g"] = round(nutrientes["proteina_g"], 1)

    confiable = len(problemas) == 0

    return {
        "documento": documento,
        "verificacion": {"confiable": confiable, "problemas": problemas},
        "meta": {
            "modelo": gemini.MODELO_ANALISIS,
            "tamano_prompt_kb": len(prompt) // 1024,
        },
    }
