"""
Punto unico de consulta de alimentos del sistema.

Jerarquia de fuentes (actualizada tras migracion a base Marifer, sep 2026):

1. MARIFER (local)      Base de equivalencias propia de la nutriologa,
                        clasificada por grupo SMAE real. Fuente principal.
                        2342 alimentos, sin internet, sin limites.

2. USDA (API o local)   Alimentos que Marifer no cubre bien. Hoy via API
                        (1000 consultas/hora); pasara a ser local (FNDDS)
                        en cuanto se complete esa migracion.

3. BAM (local)          Ultimo respaldo local si ni Marifer ni USDA
                        tienen el alimento. 2045 alimentos.

4. OpenFoodFacts (API)  SOLO productos de marca, cuando la nutriologa
                        indica un nombre comercial especifico
                        ("tostadas Sanissimo", "yogurt Yoplait").
                        NUNCA se consulta automaticamente para alimentos
                        genericos.

Por que OpenFoodFacts no es fuente general: la prueba de cobertura
mostro que devuelve productos equivocados con alta frecuencia. Buscando
"tortilla de maiz" devolvio Takis Fuego; "huevo" devolvio galletas
Maria; "aguacate" devolvio aceite de aguacate. Es una base de productos
empacados con codigo de barras, no de alimentos. Usarla sin verificacion
produciria dietas calculadas con datos incorrectos.

REGLA DE SEGURIDAD: ningun resultado de OpenFoodFacts se acepta sin que
la nutriologa lo confirme. Las funciones de este modulo que consultan
esa fuente siempre devuelven una lista de candidatos para elegir, nunca
un resultado unico automatico.
"""

import bam
import marifer


def buscar_generico(termino, limite=10):
    """
    Busca un alimento generico. Consulta Marifer primero, luego USDA,
    y a BAM solo si ninguna de las dos anteriores devuelve nada.
    """
    resultados = marifer.buscar_palabras(termino, limite=limite)
    if resultados:
        return resultados

    try:
        import usda
        resultados = usda.buscar(termino, limite=limite)
        if resultados:
            return resultados
    except Exception:
        pass

    return bam.buscar_palabras(termino, limite=limite)


def buscar_marca(termino, limite=5):
    """
    Busca un producto comercial por marca. Devuelve SIEMPRE una lista de
    candidatos para que la nutriologa elija, nunca un resultado unico.

    Usar solo cuando la nutriologa escribe un nombre comercial explicito.
    """
    try:
        import openfoodfacts as off
        resultados = off.buscar(termino, limite=limite)
        return [r for r in resultados if off.tiene_datos_completos(r)]
    except Exception:
        return []


def buscar_todo(termino, limite=10):
    """
    Busqueda amplia para la pantalla de consulta manual. Devuelve los
    resultados agrupados por fuente, para que quede claro de donde
    viene cada dato.
    """
    salida = {
        "marifer": marifer.buscar_palabras(termino, limite=limite),
        "generico_internacional": [],
        "bam": bam.buscar_palabras(termino, limite=limite),
        "productos_de_marca": [],
    }

    try:
        import usda
        salida["generico_internacional"] = usda.buscar(termino, limite=5)
    except Exception:
        pass

    return salida


def resumen_fuentes():
    """Estado de las fuentes disponibles, util para diagnostico."""
    import os

    estado = {
        "marifer": {
            "disponible": True,
            "alimentos": marifer.total_alimentos(),
            "tipo": "local",
        },
        "bam": {
            "disponible": True,
            "alimentos": bam.total_alimentos(),
            "tipo": "local",
        },
        "usda": {
            "disponible": bool(os.environ.get("USDA_API_KEY")),
            "tipo": "api",
            "nota": "requiere USDA_API_KEY en el archivo .env",
        },
        "openfoodfacts": {
            "disponible": True,
            "tipo": "api",
            "nota": "solo para productos de marca, con verificacion humana",
        },
    }
    return estado
