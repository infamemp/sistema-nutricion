"""
Valida la tabla de medidas contra las fuentes de datos reales.

Por que existe: es facil registrar un termino de busqueda que suena
correcto pero no existe en la BAM. Paso de verdad: se registraron
"jitomate saladette", "pepino crudo" y "champinon crudo", ninguno
existia. La BAM los llama "JITOMATE SALADET", "PEPINO CON CASCARA" y
"CHAMPINONES NATURALES".

El sintoma es silencioso: esos alimentos simplemente quedan sin
verificar, y las dietas que los usan pierden precision sin avisar.

Correr despues de cualquier cambio a medidas_caseras.json:

    python validar_tabla.py
"""

import medidas
import verificador


def validar():
    tabla = medidas.cargar()["alimentos"]

    ok = []
    fallidos = []
    sin_medida = []
    sin_aporte = []

    for nombre in sorted(tabla.keys()):
        entrada = tabla[nombre]

        if entrada.get("sin_aporte_nutricional"):
            sin_aporte.append(nombre)
            continue

        # Elegir una medida de prueba de las que tenga registradas
        medida_prueba = None
        usuales = entrada.get("porciones_usuales", {})
        if usuales:
            medida_prueba = list(usuales.keys())[0]
        elif "taza_g" in entrada:
            medida_prueba = "1 taza"
        elif "pieza_g" in entrada:
            medida_prueba = "1 pieza"
        elif "cucharada_g" in entrada:
            medida_prueba = "1 cucharada"
        elif "rebanada_g" in entrada:
            medida_prueba = "1 rebanada"
        elif "filete_g" in entrada:
            medida_prueba = "1 filete"

        if not medida_prueba:
            sin_medida.append(nombre)
            continue

        nutrientes, problema = verificador.nutrientes_de_alimento(nombre, medida_prueba)

        if problema:
            fallidos.append({
                "alimento": nombre,
                "medida": medida_prueba,
                "problema": problema,
                "buscar_como": entrada.get("buscar_como"),
                "buscar_como_usda": entrada.get("buscar_como_usda"),
            })
        else:
            ok.append({
                "alimento": nombre,
                "fuente": nutrientes["fuente"],
                "resuelve_a": nutrientes["nombre_en_fuente"],
                "proteina": nutrientes["proteina_g"],
            })

    return ok, fallidos, sin_medida, sin_aporte


def main():
    print("Validando la tabla de medidas contra la BAM y el USDA...")
    print("Esto puede tardar, cada consulta al USDA toma su tiempo.")
    print()

    ok, fallidos, sin_medida, sin_aporte = validar()
    total = len(ok) + len(fallidos) + len(sin_medida)

    print("=" * 60)
    print("RESULTADO")
    print("=" * 60)
    print("Alimentos en la tabla:  " + str(total))
    print("Verificables:           " + str(len(ok)))
    print("Con problema:           " + str(len(fallidos)))
    print("Sin medida registrada:  " + str(len(sin_medida)))
    print("Sin aporte nutricional: " + str(len(sin_aporte)) + " (cafe, tes, suplementos, no requieren verificacion)")
    print()

    if fallidos:
        print("ALIMENTOS QUE NO SE PUEDEN VERIFICAR:")
        print()
        for f in fallidos:
            print("  " + f["alimento"] + " (" + f["medida"] + ")")
            print("     problema: " + f["problema"][:100])
            if f["buscar_como"]:
                print("     buscar_como: '" + f["buscar_como"] + "'")
            if f["buscar_como_usda"]:
                print("     buscar_como_usda: '" + f["buscar_como_usda"] + "'")
            print()

    if sin_medida:
        print("SIN MEDIDA DE PRUEBA (revisar que tengan pesos registrados):")
        for n in sin_medida:
            print("  - " + n)
        print()

    porcentaje = round(len(ok) / total * 100) if total else 0
    print("Cobertura de la tabla: " + str(porcentaje) + "%")

    if porcentaje < 90:
        print()
        print("Conviene resolver los fallos antes de generar dietas reales.")


if __name__ == "__main__":
    main()
