"""
Verificador nutricional de planes.

Responde la pregunta que ningun otro modulo respondia: los numeros que
declara la IA, son ciertos?

El problema que resuelve: cuando Gemini dice que un desayuno tiene 32 g
de proteina, ese numero era una estimacion suya. Nadie lo comprobaba
contra datos reales. Este modulo lo calcula desde la BAM y lo compara.

Es el mismo principio que ya aplicamos con los gramos: si el sistema
tiene el dato, hay que usarlo, no dejar que la IA lo infiera.

Filosofia: NO corrige, REPORTA. La correccion es decision de la
nutriologa o de una regeneracion. El verificador nunca cambia una dieta
en silencio.
"""

import bam
import fndds
import marifer
import medidas


# Tolerancia antes de marcar una discrepancia de proteina.
# 15% es razonable: las porciones caseras tienen variacion natural.
TOLERANCIA_PROTEINA = 0.15

# Diferencia minima en gramos para que valga la pena reportar.
# Debajo de esto el error es irrelevante en la practica.
UMBRAL_GRAMOS_PROTEINA = 4


# Cache de consultas a FNDDS. Aunque ya es local (sin limite de API),
# se conserva para no repetir la busqueda en el mismo proceso.
_cache_fndds = {}


# Proteina maxima esperada por 100 g, segun el tipo de alimento.
# Sirve para detectar cuando la busqueda devolvio un alimento equivocado.
# Caso real: buscar "pimiento" en la BAM devolvia "QUESO PIMIENTO", con
# 22 g de proteina por 100 g. Un pimiento tiene menos de 1 g.
TECHOS_PROTEINA = {
    "verdura": 5,
    "fruta": 3,
    "grasa": 25,
    "cereal": 15,
}

CLASIFICACION = {
    "verdura": [
        "pimiento", "jitomate", "cebolla", "calabacita", "lechuga",
        "espinaca", "acelga", "kale", "arugula", "champinones", "nopales",
        "ejotes", "esparragos", "chayote", "zanahoria", "pepino", "col",
        "coliflor", "betabel", "jicama", "verdura", "brocoli",
    ],
    "fruta": [
        "manzana", "platano", "papaya", "fresas", "blueberries", "uvas",
        "pera", "naranja", "mandarina", "guayaba", "kiwi", "melon",
        "sandia", "durazno", "ciruela", "frambuesas", "moras", "fruta",
    ],
    "grasa": ["aceite", "aguacate", "mayonesa"],
}


def _clasificar(nombre):
    n = nombre.lower()
    for categoria, palabras in CLASIFICACION.items():
        if any(p in n for p in palabras):
            return categoria
    return None


def _dato_sospechoso(nombre, datos):
    """
    Detecta cuando la fuente devolvio un alimento que no corresponde.

    Devuelve un mensaje si algo no cuadra, o None si se ve razonable.
    """
    categoria = _clasificar(nombre)
    if not categoria:
        return None

    techo = TECHOS_PROTEINA.get(categoria)
    proteina = datos.get("proteina_g")

    if techo and proteina is not None and proteina > techo:
        return (
            "La fuente devolvio '" + str(datos.get("nombre"))
            + "' con " + str(proteina) + " g de proteina por 100 g. "
            "Demasiado para un alimento del grupo " + categoria
            + ". Probablemente no es el alimento correcto."
        )

    return None


def _buscar_datos_nutricionales(nombre, entrada_medidas):
    """
    Busca los datos nutricionales de un alimento en la fuente correcta.

    Jerarquia (final tras migracion Marifer + FNDDS, sep 2026):
      1. MARIFER, base de equivalencias propia de la nutriologa
      2. BAM, para alimentos genericos mexicanos que Marifer no cubre
      3. FNDDS, para los que ninguna de las dos anteriores cubre
         (quinoa, pistaches, pepitas, pan de masa madre y otros no
         tradicionales en Mexico). Reemplaza a la API en linea de USDA:
         mismo origen de datos, ahora local y sin limite de consultas.

    La tabla de medidas indica con 'buscar_en': 'usda' cuales van directo
    a FNDDS, para no gastar una busqueda fallida en las fuentes locales
    en espanol. El nombre del campo se conserva ('usda'/'buscar_como_usda')
    para no tener que tocar medidas_caseras.json en esta migracion.
    """
    prefiere_fndds = entrada_medidas.get("buscar_en") == "usda"

    if not prefiere_fndds:
        datos = medidas.buscar_en_bam(nombre, marifer)
        if datos:
            return datos, "MARIFER"

        datos = medidas.buscar_en_bam(nombre, bam)
        if datos:
            return datos, "BAM"

    termino_fndds = entrada_medidas.get("buscar_como_usda")
    if not termino_fndds:
        return None, None

    if termino_fndds in _cache_fndds:
        return _cache_fndds[termino_fndds], "FNDDS"

    resultados = fndds.buscar_palabras(termino_fndds, limite=1)
    if resultados and fndds.tiene_datos_completos(resultados[0]):
        _cache_fndds[termino_fndds] = resultados[0]
        return resultados[0], "FNDDS"

    return None, None


def nutrientes_de_alimento(nombre, cantidad):
    """
    Calcula los nutrientes reales de un alimento en una cantidad dada,
    consultando la BAM o el USDA segun corresponda.

    Devuelve (nutrientes, problema). Si problema no es None, el calculo
    no se pudo completar y hay que reportarlo.
    """
    entrada_medidas = medidas.buscar_alimento(nombre)
    if entrada_medidas is None:
        return None, "no_esta_en_tabla_de_medidas"

    # Cafe, tes, agua de sabor sin azucar, suplementos como creatina o
    # electrolitos. No aportan nutrientes relevantes, no tiene sentido
    # buscarlos ni contarlos como falla de verificacion.
    if entrada_medidas.get("sin_aporte_nutricional"):
        return {
            "nombre": nombre,
            "gramos": 0,
            "energia_kcal": 0,
            "proteina_g": 0,
            "carbohidratos_g": 0,
            "grasa_g": 0,
            "fuente": "sin_aporte",
            "nombre_en_fuente": nombre,
            "peso_exacto": True,
        }, None

    gramos, exacto = medidas.a_gramos(nombre, cantidad)
    if gramos is None:
        return None, "no_se_pudo_convertir_la_medida"

    datos, fuente = _buscar_datos_nutricionales(nombre, entrada_medidas)
    if datos is None:
        return None, "sin_datos_nutricionales"

    sospecha = _dato_sospechoso(nombre, datos)
    if sospecha:
        return None, "dato_sospechoso: " + sospecha

    nutrientes = medidas.nutrientes_de_porcion(nombre, cantidad, datos)
    if nutrientes is None:
        return None, "no_se_pudo_calcular"

    nutrientes["nombre_en_fuente"] = datos.get("nombre")
    nutrientes["fuente"] = fuente
    nutrientes["peso_exacto"] = exacto

    return nutrientes, None


def verificar_opcion(opcion):
    """
    Verifica una opcion de comida: suma la proteina real de sus alimentos
    y la compara con la que declaro la IA.
    """
    alimentos = opcion.get("alimentos") or []
    declarada = opcion.get("proteina_estimada_g")

    proteina_real = 0.0
    kcal_real = 0.0
    verificados = 0
    sin_verificar = []

    for al in alimentos:
        nombre = al.get("alimento", "")
        cantidad = al.get("cantidad", "")
        if not nombre or not cantidad:
            continue

        nutrientes, problema = nutrientes_de_alimento(nombre, cantidad)

        if problema:
            sin_verificar.append({
                "alimento": nombre,
                "cantidad": cantidad,
                "motivo": problema,
            })
            continue

        if nutrientes.get("proteina_g") is not None:
            proteina_real += nutrientes["proteina_g"]
        if nutrientes.get("energia_kcal") is not None:
            kcal_real += nutrientes["energia_kcal"]
        verificados += 1

    total_alimentos = len([a for a in alimentos if a.get("alimento")])
    cobertura = verificados / total_alimentos if total_alimentos else 0

    resultado = {
        "descripcion": opcion.get("descripcion", "")[:80],
        "proteina_declarada_g": declarada,
        "proteina_calculada_g": round(proteina_real, 1),
        "kcal_calculadas": round(kcal_real),
        "alimentos_verificados": verificados,
        "alimentos_totales": total_alimentos,
        "cobertura": round(cobertura, 2),
        "sin_verificar": sin_verificar,
        "alertas": [],
    }

    if cobertura < 0.6:
        resultado["alertas"].append({
            "nivel": "alto",
            "tipo": "cobertura_insuficiente",
            "detalle": "Solo se pudo verificar " + str(verificados) + " de "
                       + str(total_alimentos) + " alimentos. El calculo de "
                       "proteina no es confiable.",
        })

    if declarada is not None and cobertura >= 0.6:
        diferencia = abs(proteina_real - declarada)
        margen = declarada * TOLERANCIA_PROTEINA

        if diferencia > margen and diferencia > UMBRAL_GRAMOS_PROTEINA:
            nivel = "alto" if diferencia > declarada * 0.3 else "medio"
            resultado["alertas"].append({
                "nivel": nivel,
                "tipo": "proteina_no_coincide",
                "detalle": "La IA declaro " + str(declarada) + " g pero el "
                           "calculo real da " + str(round(proteina_real, 1))
                           + " g. Diferencia de " + str(round(diferencia, 1)) + " g.",
            })

    return resultado


def recalcular_plan(plan):
    """
    Sustituye los numeros que estimo la IA por los calculados desde las
    fuentes de datos.

    Por que existe: los modelos de lenguaje no son confiables sumando.
    Pueden elegir bien los alimentos y las cantidades, pero la aritmetica
    la hace Python, que no se equivoca.

    Deja constancia de lo que declaro la IA en 'proteina_declarada_por_ia'
    para poder auditar despues, pero el numero que vale es el calculado.

    Solo sobrescribe cuando la cobertura de verificacion es suficiente.
    Si no se pudieron verificar los alimentos, deja el valor de la IA y
    lo marca como no confirmado.
    """
    cambios = []

    for tiempo, opciones in (plan.get("opciones_por_tiempo") or {}).items():
        for opcion in (opciones or []):
            v = verificar_opcion(opcion)

            declarada = v["proteina_declarada_g"]
            calculada = v["proteina_calculada_g"]
            cobertura = v["cobertura"]

            opcion["proteina_declarada_por_ia"] = declarada
            opcion["cobertura_verificacion"] = cobertura

            if cobertura >= 0.8:
                opcion["proteina_estimada_g"] = calculada
                opcion["proteina_verificada"] = True
                if declarada and abs(calculada - declarada) > 3:
                    cambios.append({
                        "tiempo": tiempo,
                        "opcion": v["descripcion"],
                        "antes": declarada,
                        "despues": calculada,
                    })
            else:
                opcion["proteina_verificada"] = False
                opcion["nota_verificacion"] = (
                    "Solo se verifico el " + str(int(cobertura * 100))
                    + "% de los alimentos. El valor es la estimacion de la IA."
                )

    return {
        "cambios": cambios,
        "total_corregidos": len(cambios),
    }


def verificar_plan(plan, objetivo_proteina_g=None):
    """
    Verifica el plan completo. Devuelve un reporte con el detalle por
    opcion y un resumen general.
    """
    reporte = {
        "por_tiempo": {},
        "alertas_criticas": [],
        "alimentos_desconocidos": set(),
        "resumen": {},
    }

    opciones_por_tiempo = plan.get("opciones_por_tiempo", {}) or {}
    total_opciones = 0
    opciones_con_alerta = 0
    cobertura_acumulada = 0.0

    for tiempo, lista in opciones_por_tiempo.items():
        verificadas = []
        for opcion in (lista or []):
            v = verificar_opcion(opcion)
            verificadas.append(v)
            total_opciones += 1
            cobertura_acumulada += v["cobertura"]

            if v["alertas"]:
                opciones_con_alerta += 1

            for a in v["alertas"]:
                if a["nivel"] == "alto":
                    reporte["alertas_criticas"].append({
                        "tiempo": tiempo,
                        "opcion": v["descripcion"],
                        **a,
                    })

            for sv in v["sin_verificar"]:
                if sv["motivo"] in ("no_esta_en_tabla_de_medidas", "sin_datos_nutricionales"):
                    reporte["alimentos_desconocidos"].add(sv["alimento"])

        reporte["por_tiempo"][tiempo] = verificadas

    reporte["alimentos_desconocidos"] = sorted(reporte["alimentos_desconocidos"])

    cobertura_promedio = cobertura_acumulada / total_opciones if total_opciones else 0

    reporte["resumen"] = {
        "opciones_revisadas": total_opciones,
        "opciones_con_alerta": opciones_con_alerta,
        "alertas_criticas": len(reporte["alertas_criticas"]),
        "cobertura_promedio": round(cobertura_promedio, 2),
        "alimentos_desconocidos": len(reporte["alimentos_desconocidos"]),
        "confiable": (
            cobertura_promedio >= 0.7
            and len(reporte["alertas_criticas"]) == 0
        ),
    }

    if objetivo_proteina_g:
        reporte["resumen"]["objetivo_proteina_g"] = objetivo_proteina_g

    return reporte


def resumen_legible(reporte):
    """Version en texto del reporte, para leer en consola o mostrar."""
    r = reporte["resumen"]
    lineas = []

    lineas.append("VERIFICACION NUTRICIONAL")
    lineas.append("")
    lineas.append("Opciones revisadas: " + str(r["opciones_revisadas"]))
    lineas.append("Cobertura de verificacion: " + str(int(r["cobertura_promedio"] * 100)) + "%")
    lineas.append("Opciones con alerta: " + str(r["opciones_con_alerta"]))
    lineas.append("Alertas criticas: " + str(r["alertas_criticas"]))
    lineas.append("")
    lineas.append("CONFIABLE: " + ("SI" if r["confiable"] else "NO"))

    if reporte["alertas_criticas"]:
        lineas.append("")
        lineas.append("ALERTAS CRITICAS:")
        for a in reporte["alertas_criticas"]:
            lineas.append("  [" + a["tiempo"] + "] " + a["detalle"])

    if reporte["alimentos_desconocidos"]:
        lineas.append("")
        lineas.append("ALIMENTOS QUE EL SISTEMA NO CONOCE:")
        for a in reporte["alimentos_desconocidos"]:
            lineas.append("  - " + a)
        lineas.append("")
        lineas.append("  Estos alimentos deberian agregarse a la tabla de")
        lineas.append("  medidas para poder verificar las dietas que los usen.")

    return "\n".join(lineas)
