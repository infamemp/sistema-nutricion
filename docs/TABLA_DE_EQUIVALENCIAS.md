# Tabla de Equivalencias Nutrimentales (TEN), Documento de Diseño

**Versión:** 1.0
**Fecha:** 28 de agosto de 2026
**Para:** referencia del contenido que alimentará al motor de IA en la Fase 2

---

## 1. Qué es esto y por qué existe

Marifer trabaja con el concepto de "alimentos equivalentes" (agrupar alimentos por categoría con aporte nutrimental similar, intercambiables entre sí) para decidir cuántas porciones de cada grupo prescribir a un paciente. En México, la referencia comercial más conocida para esto es el SMAE (Sistema Mexicano de Alimentos Equivalentes), una publicación protegida por derechos de autor de Fomento de Nutrición y Salud, A.C.

El sistema **no reproduce ni digitaliza el SMAE**. En su lugar, construye una tabla propia, con el mismo método general, a partir de dos fuentes que sí son legítimas de usar:

1. **Ciencia nutricional de dominio público:** los valores de referencia por categoría (cuántos gramos de carbohidrato, proteína y grasa corresponde a una porción) están publicados de forma independiente en decenas de fuentes sin relación entre sí (hospitales, universidades, clínicas de diabetes en varios países). Esto confirma que son hechos científicos generales, no la compilación protegida de un autor.
2. **OpenFoodFacts:** base de datos abierta y colaborativa de alimentos, usada para obtener la información nutrimental de productos y alimentos específicos, incluyendo mexicanos.

**Nombre del sistema:** para evitar cualquier confusión con la marca registrada SMAE, este documento y el archivo de datos resultante se llaman **Tabla de Equivalencias Nutrimentales (TEN)**. El archivo técnico se llamará `tabla_equivalencias.json`, nunca `smae.json`.

**Regla que se mantiene sin cambios:** esta tabla es cálculo interno para que la IA decida cuántos equivalentes prescribir. Nunca se expone al paciente en su forma cruda, por la misma razón ya documentada para el SMAE: tomada literal, permitiría sustituciones inapropiadas (ej. un carbohidrato por una dona del mismo peso en gramos).

---

## 2. Categorías y valores de referencia

Valores por porción (una "unidad equivalente"), consistentes entre las fuentes independientes consultadas:

| Categoría | Carbohidratos | Proteína | Grasa | Energía aprox. |
|---|---|---|---|---|
| Cereales y tubérculos | 15 g | 3 g | trazas | 80 kcal |
| Frutas | 15 g | 0 g | 0 g | 60 kcal |
| Verduras | 5 g | 2 g | 0 g | 25 kcal |
| Leche | 12 g | 8 g | variable según tipo (descremada/semidescremada/entera) | 90-150 kcal |
| Leguminosas | 15 g | 7 g | trazas | 90 kcal |
| Alimentos de origen animal, muy bajo aporte de grasa | 0 g | 7 g | 0-1 g | 35 kcal |
| Alimentos de origen animal, bajo aporte de grasa | 0 g | 7 g | 3 g | 55 kcal |
| Alimentos de origen animal, moderado aporte de grasa | 0 g | 7 g | 5 g | 75 kcal |
| Alimentos de origen animal, alto aporte de grasa | 0 g | 7 g | 8 g | 100 kcal |
| Aceites y grasas | 0 g | 0 g | 5 g | 45 kcal |
| Azúcares | 15 g | 0 g | variable | 60-90 kcal |

Estas categorías siguen la nomenclatura estándar en español usada en la práctica nutricional mexicana (verduras, frutas, cereales y tubérculos, leguminosas, alimentos de origen animal por nivel de grasa, leche, aceites y grasas, azúcares), la cual es terminología descriptiva general, no exclusiva de ninguna publicación.

---

## 3. Cómo se construye la tabla real (trabajo de la Fase 2)

Este documento fija el método y los valores de referencia. La construcción del archivo `tabla_equivalencias.json` con alimentos mexicanos específicos y sus porciones exactas es trabajo de código, pendiente para la Fase 2, y seguirá este proceso:

1. Para cada categoría, se identifican alimentos mexicanos comunes (ej. tortilla de maíz, frijoles de la olla, nopales, papaya).
2. Se consulta OpenFoodFacts para obtener su información nutrimental por 100 g.
3. Se calcula matemáticamente qué porción de ese alimento corresponde a una unidad equivalente de su categoría, comparando contra los valores de referencia de la sección 2.
4. El resultado (alimento, categoría, porción calculada) se guarda en `tabla_equivalencias.json`, organizado por categoría, mismo formato plano que se había planeado para el archivo anterior.

## 4. Huecos de datos esperados y cómo llenarlos

OpenFoodFacts tiene mucho mejor cobertura de productos empacados y de marca (sobre todo europeos) que de alimentos genéricos frescos mexicanos. Es esperable encontrar huecos o información incompleta para alimentos como nopales, tortillas artesanales, o preparaciones caseras.

Michel tiene una cuenta activa en OpenFoodFacts (con una contribución económica realizada). La donación no otorga acceso especial a datos, la API es abierta para todos por igual, pero la cuenta sí permite **contribuir directamente**, agregando o mejorando entradas de alimentos mexicanos genéricos. Esto beneficia al sistema propio y queda disponible para cualquiera que use OpenFoodFacts después. Se usará esta vía para llenar los huecos que se detecten al construir la tabla real en la Fase 2.

---

## 5. Qué NO incluye este documento

- Ninguna cifra, porción, o alimento copiado del SMAE o de cualquier otra publicación protegida.
- El archivo de datos real con alimentos mexicanos poblados (eso es la Fase 2).
- Cambios al orden de fases ya acordado: este documento es planeación de contenido, no código.

---

## 6. Bitácora

| Fecha | Cambio |
|---|---|
| 2026-08-28 | v1.0, diseño inicial. Se descarta usar el SMAE directamente (protegido por derechos de autor, incluso siendo un ejemplar comprado legítimamente) y se define una tabla propia, con nombre distinto (TEN) para evitar confusión de marca, basada en valores de ciencia nutricional de dominio público más OpenFoodFacts |
