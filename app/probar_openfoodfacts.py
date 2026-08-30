"""
Diagnostico de cobertura de OpenFoodFacts para alimentos mexicanos.

Ejecutar con:  python probar_openfoodfacts.py

Mide que tan bien responde la base de datos a los alimentos que
Marifer usa realmente en sus dietas, para decidir cuanto necesitamos
complementar con las tablas del INCMNSZ.
"""

import time
import openfoodfacts as off

# OpenFoodFacts limita a 10 busquedas por minuto.
# Con 7 segundos entre consultas nos mantenemos dentro del limite.
PAUSA_SEGUNDOS = 7

# Alimentos tomados de las dietas reales de la nutriologa
ALIMENTOS_PRUEBA = [
    "tortilla de maiz",
    "nopal",
    "frijol negro",
    "queso panela",
    "salmas",
    "aguacate",
    "avena",
    "quinoa",
    "yogurt griego natural",
    "queso cottage",
    "atun en agua",
    "pechuga de pollo",
    "jicama",
    "chia",
    "crema de almendras",
    "tortitas de arroz",
    "leche de almendras",
    "camote",
    "lentejas",
    "huevo",
]


def main():
    print("Diagnostico de cobertura, OpenFoodFacts Mexico")
    print("=" * 60)
    print(f"Pausa de {PAUSA_SEGUNDOS}s entre consultas por el limite de la API.")
    print(f"Tiempo estimado: {len(ALIMENTOS_PRUEBA) * PAUSA_SEGUNDOS // 60} minutos aprox.")
    print()
    print("IMPORTANTE: revisa manualmente si el alimento devuelto corresponde")
    print("al buscado. OpenFoodFacts indexa productos empacados con codigo de")
    print("barras, no alimentos genericos, y suele devolver coincidencias")
    print("aproximadas (ej. 'chips de jicama' cuando se busca 'jicama').")
    print()

    con_datos = 0
    sin_datos = 0
    sin_resultados = 0

    for i, alimento in enumerate(ALIMENTOS_PRUEBA):
        if i > 0:
            time.sleep(PAUSA_SEGUNDOS)

        try:
            resultados = off.buscar(alimento, limite=3)
        except Exception as e:
            print(f"[ERROR]      {alimento}: {e}")
            print()
            continue

        if not resultados:
            print(f"[SIN NADA]   {alimento}")
            sin_resultados += 1
            continue

        completos = [r for r in resultados if off.tiene_datos_completos(r)]

        if completos:
            mejor = completos[0]
            print(f"[OK]         {alimento}")
            print(f"             -> {mejor['nombre']}")
            print(f"                {mejor['energia_kcal']} kcal | "
                  f"P {mejor['proteina_g']}g | "
                  f"C {mejor['carbohidratos_g']}g | "
                  f"G {mejor['grasa_g']}g")
            con_datos += 1
        else:
            print(f"[INCOMPLETO] {alimento} ({len(resultados)} resultados sin macros)")
            sin_datos += 1

        print()

    total = len(ALIMENTOS_PRUEBA)
    print("=" * 60)
    print(f"Con datos completos:  {con_datos}/{total}")
    print(f"Incompletos:          {sin_datos}/{total}")
    print(f"Sin resultados:       {sin_resultados}/{total}")
    print()
    print(f"Cobertura util: {round(con_datos / total * 100)}%")


if __name__ == "__main__":
    main()
