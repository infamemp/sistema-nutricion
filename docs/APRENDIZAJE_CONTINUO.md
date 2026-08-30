# Aprendizaje continuo del sistema

**Versión:** 1.0
**Fecha:** 30 de agosto de 2026
**Estado:** diseñado, no implementado. Se construye cuando haya material real acumulado.

---

## 1. La pregunta que originó este documento

¿Puede el sistema ir absorbiendo la lógica y la esencia de Marifer? ¿Con cada dieta, cada corrección, cada caso nuevo, parecerse más a ella?

**Respuesta honesta: no de forma automática, y es importante no tener esa expectativa.**

Cada vez que la IA genera una dieta empieza de cero. No tiene memoria entre casos. Aunque Marifer corrija cien dietas, la siguiente sale igual que la primera, porque los modelos de IA se entrenan una vez y no se modifican con el uso.

**Pero el efecto sí se puede construir.** La IA no aprende, pero el sistema puede volverse más listo sobre qué información darle. Esa es la diferencia clave.

---

## 2. Advertencia que gobierna todo este documento

> **El sistema es inteligente, flexible, adaptable, proactivo, experto, y que investiga. NO es un robot rígido, repetitivo, ni de copiar y pegar.**

Este principio viene desde la definición original del proyecto y tiene prioridad sobre cualquier mecanismo de aprendizaje que se construya. Si un mecanismo mejora la consistencia a costa de volver al sistema repetitivo, **no se implementa**.

Un sistema que copia las dietas anteriores deja de razonar. Y un sistema que no razona no sirve para lo que Marifer necesita: adaptarse a cada paciente, cada padecimiento y cada circunstancia.

---

## 3. Nivel 1, registro de correcciones

**Qué es:** cada vez que Marifer usa el botón "Modificar propuesta", el sistema guarda qué pidió cambiar. Con el tiempo se revisan esas correcciones y se detectan patrones. Ejemplo: "en 8 de cada 10 casos pidió reducir la fruta del desayuno". Ese patrón se convierte en una regla nueva en `reglas_clinicas.json`.

**Estado:** la base de datos ya está preparada. La tabla `dietas_versiones` incluye el campo `instruccion_ajuste` justamente para esto. Solo falta usarlo y construir la pantalla de revisión.

**Riesgo:** bajo. Requiere que un humano revise y decida qué patrón se convierte en regla. No hay automatismo ciego.

**Recomendación: implementar.** Es el mecanismo más confiable y el que mejor respeta el principio de flexibilidad, porque lo que se ajusta son las reglas, no las dietas.

---

## 4. Nivel 2, banco de dietas aprobadas

**Qué es:** las dietas que Marifer aprueba sin cambios se guardan como ejemplos. Cuando llega un caso parecido, el sistema le muestra a la IA dos o tres de esas dietas como referencia.

**RIESGO ALTO, y es el punto más delicado de este documento.**

Este mecanismo puede degradar el sistema hasta volverlo exactamente lo que no debe ser: un motor de copiar y pegar. Los peligros concretos:

- **Repetición:** si el sistema ve tres dietas de referencia, tenderá a producir una cuarta muy parecida. Los pacientes empezarían a recibir planes casi idénticos.
- **Obsolescencia:** las dietas viejas se vuelven la norma. Si Marifer evoluciona su criterio, el sistema seguiría anclado a como pensaba hace un año.
- **Pérdida de razonamiento:** en lugar de analizar el caso concreto, el sistema buscaría el caso más parecido y lo imitaría. Deja de pensar.
- **Sesgo acumulado:** un error o una decisión circunstancial de una dieta aprobada se replicaría indefinidamente.

**Si algún día se implementa, con condiciones estrictas:**

- Los ejemplos se usan para transmitir **estilo y estructura**, nunca contenido. Jamás copiar alimentos ni cantidades.
- Rotación obligatoria: nunca los mismos ejemplos dos veces seguidas.
- Caducidad: las dietas de referencia expiran, no valen para siempre.
- Verificación activa contra la regla ya existente de no repetir opciones al mismo paciente.
- Instrucción explícita en el prompt: "estos ejemplos ilustran el estilo, resuelve este caso desde cero".

**Recomendación: no implementar por ahora.** El beneficio es marginal frente al riesgo de degradar la característica central del sistema. El Nivel 1 logra buena parte del mismo objetivo sin este peligro.

---

## 5. Nivel 3, análisis periódico asistido

**Qué es:** cada cierto tiempo, la IA analiza el conjunto de correcciones acumuladas y **propone** ajustes a las reglas clínicas. Marifer los revisa y aprueba o rechaza.

**Es una versión asistida del Nivel 1**, no un sustituto. La decisión sigue siendo humana.

**Cuándo:** solo cuando haya material real suficiente, del orden de 50 a 100 dietas. Antes de eso, cualquier patrón detectado sería ruido estadístico.

**Recomendación: dejar para más adelante**, después de que el Nivel 1 lleve tiempo funcionando.

---

## 6. Lo que sí hace al sistema parecerse a Marifer, hoy

Vale la pena recordar que el sistema ya tiene tres capas que capturan su forma de trabajar, y ninguna requiere aprendizaje automático:

1. **`STYLE_SPEC.md`**, derivado de 24 documentos reales suyos. Captura su voz, vocabulario, formatos y prohibiciones.
2. **`reglas_clinicas.json`**, con sus criterios de prescripción recabados directamente. Captura cómo decide.
3. **La knowledgebase clínica**, 17 fuentes evaluadas. Captura el marco de conocimiento en el que se apoya.

Esas tres capas ya son editables. **La vía más directa para que el sistema se parezca más a Marifer no es que "aprenda solo", es mantener esas tres capas actualizadas** conforme ella note cosas que ajustar.

---

## 7. Bitácora

| Fecha | Cambio |
|---|---|
| 2026-08-30 | v1.0. Documentados los tres niveles posibles de aprendizaje continuo, con la advertencia explícita sobre el riesgo del Nivel 2 de convertir el sistema en un motor repetitivo de copiar y pegar |
