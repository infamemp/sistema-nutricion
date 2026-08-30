# Conversión de medidas caseras

**Versión:** 1.1
**Fecha:** 30 de agosto de 2026
**Implementación:** `datos/medidas_caseras.json` y `medidas.py`

---

## 1. Para qué existe

Marifer prescribe en medidas caseras: "1 taza de arroz", "⅓ de aguacate", "1 paquetito de salmas". La BAM da valores por 100 g. Este módulo es el puente entre ambos.

Sin él, el sistema no puede verificar si una dieta cumple el objetivo de proteína, porque no sabe cuántos gramos son "1 pechuga de pollo".

**Regla que no cambia:** los gramos son solo para cálculo interno. El paciente siempre ve la medida casera, nunca el gramaje.

---

## 2. Contenido

62 alimentos con sus medidas reales, tomados de las 24 dietas de Marifer más los de uso común en México. Incluye las porciones exactas que ella usa: "⅓ de aguacate" (67 g), "1 paquetito de salmas" (30 g), "¾ de taza de pollo desmenuzado" (105 g).

Cada alimento puede tener:
- Pesos base: `taza_g`, `pieza_g`, `cucharada_g`, `rebanada_g`
- `porciones_usuales`: las medidas exactas que aparecen en sus dietas
- `buscar_como`: el término correcto para consultar la BAM
- `estado`: crudo o cocido

---

## 3. El problema crudo contra cocido

**Este es el hallazgo más importante del módulo, y se detectó en pruebas antes de que causara daño.**

Los cereales, leguminosas y pastas absorben agua al cocerse y triplican su peso. Sus valores por 100 g son completamente distintos:

| Alimento | kcal por 100 g |
|---|---|
| ARROZ PROMEDIO (crudo) | 363 |
| ARROZ INTEGRAL COCIDO | 123 |

Al calcular media taza de arroz cocido, el sistema devolvía **287 kcal y 62 g de carbohidratos** porque estaba tomando el arroz crudo. El valor correcto es **97 kcal y 20 g**.

**Por qué es peligroso:** el error no produce ninguna señal. Una dieta completa mal calculada se vería perfectamente normal.

**Solución implementada:** el campo `buscar_como` en cada alimento donde el estado importa. La función `buscar_en_bam()` lo usa automáticamente, de modo que buscar "arroz cocido" consulta "ARROZ INTEGRAL COCIDO" y no el crudo.

**Alimentos con estado marcado:** arroz, quinoa, pasta, frijol, lentejas, garbanzo, avena, camote, papa, nopales, verdura cocida, pechuga de pollo, huevo, salmón.

---

## 4. Segundo hallazgo, con piel o sin piel

La búsqueda de "pechuga de pollo" resolvía a "POLLO, PECHUGA CON PIEL", que tiene 181 kcal y 11.1 g de grasa. La versión sin piel, que es la que Marifer prescribe, tiene 120 kcal y 2.62 g de grasa. **Más de 4 veces la grasa.**

Corregido con `buscar_como: "pollo pechuga sin piel"`.

Es el mismo tipo de problema que el crudo/cocido: el nombre coloquial no basta, hay que especificar la variante correcta.

---

## 5. Chequeo de sensatez

La función `verificar_sensatez()` revisa cada porción calculada y devuelve advertencias si algo no cuadra. Mismo principio que el chequeo del InBody: mejor avisar que aceptar callado.

Detecta:
- Densidad calórica imposible, más de 9.5 kcal por gramo (ni la grasa pura llega a eso)
- Densidad muy alta, más de 6 kcal por gramo, que suele indicar que se tomó el alimento crudo cuando debía ser cocido
- Proteína que excede el peso del alimento
- Pesos estimados en lugar de medidas registradas

---

## 6. Funciones disponibles

| Función | Qué hace |
|---|---|
| `a_gramos(alimento, medida)` | Convierte una medida casera a gramos |
| `buscar_en_bam(alimento, bam)` | Busca en la BAM con el término correcto según el estado |
| `nutrientes_de_porcion(alimento, medida, datos)` | Calcula los nutrientes de esa porción concreta |
| `termino_para_bam(alimento)` | Devuelve el término de búsqueda correcto |
| `estado_alimento(alimento)` | Devuelve crudo, cocido o None |
| `verificar_sensatez(nutrientes)` | Lista de advertencias sobre un cálculo |

---

## 7. Nota para la Fase 3

**La IA tendrá que aprender los nombres de la BAM**, que no siempre coinciden con el lenguaje coloquial. La BAM llama "ARROZ PROMEDIO" a lo que Marifer llamaría "arroz", y "POLLO, PECHUGA SIN PIEL" a lo que ella escribe como "pechuga de pollo".

La tabla de medidas ya resuelve esto para los 62 alimentos registrados vía `buscar_como`. Para alimentos fuera de esa lista, el motor de IA necesitará una estrategia: probablemente presentarle a Gemini una muestra de los nombres de la BAM para que elija el correcto, en lugar de dejar que adivine.

---

## 8. Verificación realizada

Pruebas ejecutadas en el servidor el 30 de agosto de 2026:

| Porción | Resultado | Correcto |
|---|---|---|
| ½ taza de arroz cocido | 79 g, 97.2 kcal, 20.2 g carbohidrato | Sí, tras corregir crudo/cocido |
| 1 pechuga de pollo | 120 g, 144 kcal, 27 g proteína | Sí, tras corregir con/sin piel |
| ⅓ de aguacate | 67 g, 107.2 kcal, 9.8 g grasa | Sí |
| 2 huevos | 100 g, 155 kcal, 12.6 g proteína | Sí |

Los 27 g de proteína de la pechuga encajan con la regla de Marifer de 25 a 30 g por comida, lo que confirma que el sistema ya puede verificar ese tipo de criterios.

---

## 9. Bitácora

| Fecha | Cambio |
|---|---|
| 2026-08-30 | v1.0. Tabla inicial con 62 alimentos y módulo de conversión |
| 2026-08-30 | v1.1. Se detecta y corrige el problema crudo/cocido (arroz daba el triple de calorías) mediante el campo `buscar_como`. Se corrige también pechuga con piel a sin piel. Se agrega el chequeo de sensatez |
