# Reglas clínicas de prescripción

**Versión:** 1.0
**Fecha:** 30 de agosto de 2026
**Fuente:** criterios proporcionados directamente por Marifer Utrilla Lack
**Implementación:** `datos/reglas_clinicas.json` y `reglas.py`

---

## 1. Por qué existe este documento

El sistema no solo debe escribir dietas con el estilo de Marifer, debe **decidir como ella decide**. Este documento recoge su criterio clínico en forma de reglas ejecutables.

La distinción importa: imitar su estilo sin su criterio produciría dietas que suenan a ella pero no piensan como ella, y entonces tendría que revisar cada cantidad a mano, sin ahorro real de trabajo.

**Principio de diseño:** todos los números viven en `reglas_clinicas.json`, un archivo legible que Marifer puede revisar y ajustar sin tocar código. El módulo `reglas.py` solo los lee y calcula.

---

## 2. Proteína, el nutriente rector

Marifer construye la dieta alrededor de la proteína. Es la primera decisión del plan.

| Situación | Rango |
|---|---|
| Con GLP-1 | 1.0 a 1.5 g por kg de peso |
| Sin GLP-1 | 1.2 a 1.8 g por kg, según objetivos y resultados |

**Piso absoluto: 60 g diarios, no negociable.** Si el cálculo por peso da menos, se sube a 60 y el sistema lo señala.

**Distribución:** 25 a 30 g en cada una de las 3 comidas principales. Si el objetivo diario excede ese rango por comida, el sistema sugiere agregar una colación con proteína, que es lo que ella hace en la práctica (el scoop de proteína en la colación aparece en varias de sus dietas reales).

**Respaldo:** las guías EASO para pacientes con GLP-1, ya presentes en la knowledgebase clínica.

---

## 3. Resto de los grupos

**Verdura:** mínimo 2 tazas al día, distribuidas entre las comidas.

**Fruta:** máximo 2 piezas al día, 3 en deportistas o embarazadas. De bajo índice glucémico, con preferencia por frutos rojos, manzana, papaya y pera. **No hay frutas prohibidas**, solo se cuida la porción.

**Grasa:** idealmente 4 porciones al día. Aquí hay una regla importante que se detalla abajo.

**Carbohidrato:** 1 a 2 equivalentes por comida, según el caso. Preferencia por bajo índice glucémico.

---

## 4. Dos reglas que tienen prioridad sobre el cálculo

### 4.1 Calidad antes que números

Marifer se enfoca en alimentos reales y naturales. Evita siempre ultraprocesados, productos "light", empaquetados con listas largas de ingredientes, bebidas azucaradas, harinas y azúcares refinados, embutidos y grasas trans.

**Un alimento que cumple los números pero es ultraprocesado no se prescribe.** Esta regla va antes que cualquier cálculo.

### 4.2 Corrige al SMAE con criterio propio

En el grupo de grasas, el sistema de equivalentes incluye margarina, mayonesa y crema. **Marifer no las prescribe.** Su lista de grasas se limita a aguacate, aceite de oliva, semillas y frutos secos.

Es un ejemplo claro de que el criterio clínico manda sobre la tabla: el sistema debe respetar su filtro, no el del SMAE.

---

## 5. Lo que el sistema NO debe hacer

**No contar calorías.** Marifer saca un estimado mental pero no es estricta. Le interesa más el punto de partida del paciente, el cambio de hábitos y la calidad de los alimentos.

El sistema nunca debe mostrar conteo calórico al paciente ni construir el plan a partir de un objetivo calórico. Esto es consistente con lo observado en sus 24 documentos reales: cero calorías visibles.

---

## 6. Hallazgo sobre el uso del SMAE

Al recabar estos criterios se aclaró algo que estaba ambiguo: **Marifer sí piensa en equivalentes, pero prescribe en medidas caseras.** Dijo textualmente "porción de grasas según SMAE" y "carbohidratos 1-2 equivalentes según SMAE por comida".

Es decir, traduce mentalmente de equivalentes a tazas y piezas antes de escribir la dieta.

**Consecuencia para el sistema:** el concepto de equivalente es necesario como motor interno de cálculo, aunque nunca se muestre al paciente. Esto confirma la decisión ya tomada en `TABLA_DE_EQUIVALENCIAS.md` de construir una tabla propia (sin copiar el SMAE), y la vuelve indispensable en vez de opcional.

---

## 7. Jerarquía de decisión

Orden de prioridad cuando las reglas compiten entre sí:

1. Calidad del alimento: real y natural, sin ultraprocesados
2. Piso de proteína: 60 g diarios como mínimo absoluto
3. Objetivo de proteína por kg según uso de GLP-1
4. Distribución de proteína en 3 comidas de 25 a 30 g
5. Mínimos de verdura y límites de fruta
6. Grasas saludables, solo de la lista preferida
7. Carbohidratos, 1 a 2 equivalentes por comida
8. Preferencias y restricciones del paciente, de su historia clínica

---

## 8. Funciones disponibles

| Función | Qué hace |
|---|---|
| `objetivo_proteina(peso, usa_glp1)` | Calcula el rango, aplica el piso, distribuye por comida |
| `objetivos_diarios(peso, ...)` | Conjunto completo de objetivos del día |
| `alimento_permitido(nombre)` | Verifica si choca con las reglas de calidad |
| `resumen_para_prompt(peso, ...)` | Texto legible para inyectar en el prompt de la IA |
| `jerarquia()` | Orden de prioridad de las reglas |

---

## 9. Verificación realizada

Prueba ejecutada en el servidor el 30 de agosto de 2026:

**Paciente de 85 kg con GLP-1:** objetivo de 105 g, rango 85 a 128 g. El sistema detectó que 35 g por comida excede el rango preferido y sugirió agregar colación proteica.

**Paciente de 48 kg sin GLP-1:** el cálculo puro daba 57.6 g, por debajo del mínimo. El sistema aplicó el piso de 60 g y lo señaló explícitamente.

Ambas alertas automáticas funcionaron como se diseñó.

---

## 10. Bitácora

| Fecha | Cambio |
|---|---|
| 2026-08-30 | v1.0. Criterios recabados directamente de la nutrióloga e implementados como archivo de configuración editable más motor de cálculo |
