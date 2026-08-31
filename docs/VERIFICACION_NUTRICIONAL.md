# Verificación nutricional

**Versión:** 1.0
**Fecha:** 31 de agosto de 2026
**Implementación:** `verificador.py`, `validar_tabla.py`

---

## 1. El problema que resuelve

Cuando la IA generaba una dieta y declaraba "32 g de proteína en este desayuno", **ese número era una estimación suya que nadie comprobaba.** Podía estar bien o mal.

Al medirlo, resultó estar mal con frecuencia. En una prueba real: una cena declarada en 31 g tenía 60.8 g, y una comida declarada en 36 g tenía 20.9 g. **Casi el doble en un caso y casi la mitad en el otro.**

Un paciente con esas dietas no habría alcanzado su objetivo de proteína, y nadie se habría dado cuenta.

---

## 2. La solución: el sistema calcula, la IA propone

Los modelos de lenguaje no son confiables sumando. Pueden elegir bien los alimentos y las cantidades, que es donde aportan valor, pero la aritmética la hace Python, que no se equivoca.

**Flujo implementado:**

1. Gemini genera el plan con alimentos y cantidades
2. `recalcular_plan()` consulta la BAM y el USDA, calcula la proteína real de cada opción, y **sobrescribe el número que estimó la IA**
3. La estimación original se guarda en `proteina_declarada_por_ia` para auditoría
4. Si la cobertura de verificación es menor al 80%, no se sobrescribe y se marca como no confirmado

---

## 3. Guardarraíl contra alimentos mal identificados

Durante las pruebas apareció un caso revelador: buscar "pimiento" en la BAM devolvía **"QUESO PIMIENTO"**, un queso con 22 g de proteína por 100 g. El verificador contaba esos 26.6 g como si fueran del pimiento, inflando el total de la comida.

Es el mismo tipo de error que OpenFoodFacts devolviendo Takis por "tortilla de maíz".

**Solución:** techos de proteína por categoría de alimento. Si una verdura devuelve más de 5 g de proteína por 100 g, o una fruta más de 3, el dato se rechaza en vez de usarse.

---

## 4. La tabla de medidas es una tabla viva

**171 alimentos**, extraídos de los 24 documentos reales de Marifer más los de uso común en México. Cubre el universo de lo que ella prescribe, no el universo completo de alimentos mexicanos.

Incluye sus preparaciones (enfrijoladas, sincronizadas, sopes de nopal, tinga), sus formatos (salmas, tortirregias, pan thin, hot cakes de avena) y sus bebidas (té de canela, agua de jamaica, jugo verde).

**Crece con la práctica.** Cuando el verificador reporte un alimento desconocido, se agrega.

---

## 5. Jerarquía de fuentes en la verificación

| Fuente | Para qué |
|---|---|
| **BAM** (local) | Alimentos genéricos mexicanos |
| **USDA** (API) | Lo que la BAM no cubre: quinoa, pistaches, pepitas, pan de masa madre, dátiles, kéfir, arándanos |
| **Sin aporte** | Café, tés, agua de jamaica, creatina, electrolitos. No se verifican porque no aportan nutrientes relevantes |

La tabla indica con `buscar_en: usda` cuáles van directo al USDA, para no gastar una consulta fallida a la BAM. Las consultas al USDA se guardan en caché para no agotar el límite de 1,000 por hora.

---

## 6. Lección aprendida: verificar los términos antes de registrarlos

Se registraron cinco términos que sonaban correctos pero no existían en la BAM: "jitomate saladette", "pepino crudo", "champiñón crudo", "tortilla de maíz nixtamalizada", "aceite de aguacate".

La BAM los llama distinto: **"JITOMATE SALADET"** (sin doble t), **"PEPINO CON CÁSCARA"**, **"CHAMPIÑONES NATURALES"** (en plural).

**El síntoma era silencioso:** esos alimentos simplemente quedaban sin verificar, y las dietas que los usaban perdían precisión sin avisar.

**Por eso existe `validar_tabla.py`:** recorre los 171 alimentos, prueba cada uno contra las fuentes reales, y reporta cuáles fallan. Correr después de cualquier cambio a la tabla.

---

## 7. Estado actual

| Métrica | Valor |
|---|---|
| Alimentos en la tabla | 171 |
| Verificables | 164 (100%) |
| Sin aporte nutricional | 7 |
| Con problema | 0 |

**Prueba de generación completa** (caso de SOP con resistencia a la insulina):
- Cobertura de verificación: 97%
- Alertas críticas: 0
- Veredicto: CONFIABLE
- Correcciones aplicadas automáticamente: 9

---

## 8. Pendiente identificado

En la última prueba aparecieron opciones con 45 y 57 g de proteína, cuando la regla de Marifer indica 25 a 30 g por comida. **Los números ya son correctos**, el problema es que la IA está eligiendo porciones más generosas de lo que ella prescribe. Ajuste pendiente en el prompt del generador.

---

## 9. Bitácora

| Fecha | Cambio |
|---|---|
| 2026-08-31 | v1.0. Se construye el verificador tras detectar que los números de la IA no correspondían a la realidad. Se conecta la BAM y el USDA al cálculo, se agrega el guardarraíl de alimentos mal identificados, se amplía la tabla a 171 alimentos con los documentos reales de Marifer, y se crea la herramienta de validación. Cobertura final: 100% |
