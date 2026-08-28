# Knowledgebase Clínica, Resumen y Criterio de Fuentes

**Versión:** 1.0
**Fecha:** 27 de agosto de 2026
**Para:** referencia del contenido clínico que alimenta al motor de IA (Gemini, capa de análisis)

---

## 1. Qué es este documento

Inventario de las fuentes que forman la Knowledgebase (KB) del sistema, su nivel de autoridad, y el criterio con el que se evaluó cada una. Sirve también como procedimiento a seguir cuando el motor de IA necesite salir a buscar apoyo adicional en la web: el mismo filtro aplicado aquí manualmente es el que debe aplicarse ahí de forma automática.

Todos los archivos fuente siguen el mismo esquema de extracción de 17 secciones (filosofía, fisiología, glosario, protocolos, heurísticas de decisión, adaptaciones por población, contraindicaciones, fórmulas, etc.), reutilizado del pipeline de extracción de libros ya existente.

---

## 2. Niveles de autoridad

Cada fuente se clasifica en uno de tres niveles. Esto es independiente del sistema TIER A/TIER B que traen los archivos (ese mide *tipo de dato*, filosofía vs. cifra exacta; esto mide *quién lo dice y con qué respaldo*).

**Nivel A, clínico o académico.** Médicos, guías de sociedades científicas, dietistas registrados con trayectoria institucional, investigación epidemiológica primaria. Puede usarse para decisiones clínicas directas.

**Nivel B, práctico con credencial real.** Profesionales certificados (dietista, educador en diabetes, terapeuta nutricional funcional) cuyo trabajo es más aplicado o de consumo que clínico-formal. Útil como complemento operativo (recetas, adaptación práctica), no como única base de una decisión clínica de peso.

**Nivel C, divulgación sin autoridad clínica verificada, o con conflicto de interés activo.** No se usa, salvo que una investigación puntual demuestre lo contrario (ver sección 5).

---

## 3. Inventario completo (17 fuentes, 14 archivos)

Dos archivos contienen más de un libro combinado, marcado en la columna Archivo.

| Autor(es) | Obra | Año | Nivel | Especialidad | Archivo |
|---|---|---|---|---|---|
| Robert Kushner, Victor Lawrence, Sudhesh Kumar (eds.) | Practical Manual of Clinical Obesity | 2013 | A | Obesidad | robert-kushner...md |
| G. Michael Steelman, Eric Westman (eds.) | Obesity: Evaluation and Treatment Essentials | 2016 | A | Obesidad | michael-steelman...md |
| Jorge Chavarro, Walter Willett | The Fertility Diet | 2008 | A | Fertilidad | jorge-chavarro...md |
| Hillary Wright | The PCOS Diet Plan | 2017 | A | SOP | hillary-wright...md (libro 1/3) |
| Hillary Wright | The Prediabetes Diet Plan | 2013/2022 | A | Resistencia a la insulina | hillary-wright...md (libro 2/3) |
| Hillary Wright, Elizabeth Ward | The Menopause Diet Plan | 2020 | A | Menopausia | hillary-wright...md (libro 3/3) |
| Lily Nichols | Real Food for Pregnancy | 2018 | A | Embarazo | lily-nichols...md (libro 1/2) |
| Lily Nichols, Lisa Hendrickson-Jack | Real Food for Fertility | 2024 | A | Fertilidad | lily-nichols...md (libro 2/2) |
| Pamela Wartian Smith | What You Must Know about Women's Hormones | 2022 | A | Salud hormonal general | pamela-wartian-smith...md |
| Sara Gottfried | The Hormone Cure | 2013 | A | Salud hormonal, medicina funcional | sara-gottfried...md |
| ESHRE (sociedad médica) | Guideline on Endometriosis | 2022 | A | Endometriosis | eshre-guideline-endometriosis...md |
| Marion Franz, Alison Evert (eds., ADA) | ADA Guide to Nutrition Therapy for Diabetes | 2012 | A | Diabetes tipo 2 | marion-j_kb.md |
| Gary Scheiner | Think Like a Pancreas | 2020 | A | Manejo práctico de insulina | gary-scheiner...md |
| Rebecca Fett | It Starts with the Egg | 2016 | B (con matiz, ver 4.1) | Fertilidad | rebecca-fett...md |
| Cory Ruth, RDN | PCOS Is My Power | 2026 | B | SOP | cory-ruth...md |
| Summer Kessel, RD | Simple Meal Solutions for GLP-1 Diets | 2026 | B | Recetario para pacientes con GLP-1 | summer-kessel...md |
| Dian Shepperson Mills, Michael Vernon | Endometriosis: A Key to Healing and Fertility Through Nutrition | 2002/2017 | B | Endometriosis | michael-vernon...md |
| Katie Edmonds, FNTP | Heal Endo | 2022 | B | Endometriosis (aplicado) | katie-edmonds...md |
| Toni Weschler, MPH | Taking Charge of Your Fertility | 2015 | B | Educación de ciclo menstrual y fertilidad | toni-weschler...md |

**Excluida:** Jessie Inchauspé, *Glucose Revolution* (2022). Ver justificación en sección 5.

---

## 4. Cobertura por especialidad

| Especialidad | Fuentes Nivel A | Fuentes Nivel B |
|---|---|---|
| Obesidad | Kushner et al., Steelman & Westman | — |
| Diabetes tipo 2 | ADA Guide (Franz & Evert) | Scheiner (manejo de insulina) |
| Resistencia a la insulina | Hillary Wright (Prediabetes) | — |
| SOP | Hillary Wright (PCOS) | Cory Ruth |
| Endometriosis | ESHRE Guideline | Shepperson Mills & Vernon, Katie Edmonds |
| Fertilidad | Chavarro & Willett, Nichols & Hendrickson-Jack | Fett, Weschler |
| Embarazo | Lily Nichols | — |
| Salud hormonal general | Pamela Wartian Smith, Sara Gottfried | — |
| Menopausia | Hillary Wright & Ward | — |
| GLP-1 (aplicado) | — | Summer Kessel |

### 4.1 Nota sobre Rebecca Fett

Incluida con nivel B y una etiqueta de uso específica: **resumen de literatura científica, no autoridad clínica directa.** Investigación puntual (ago 2026) encontró una reseña académica publicada en una revista de obstetricia y ginecología revisada por pares, escrita por una ginecobstetra en ejercicio, que evalúa el libro como basado en medicina basada en evidencia con más de 60 estudios primarios citados. La crítica existente es de grado (exagera la certeza de ciertos suplementos), no de exactitud fabricada. Sin conflicto de interés comercial detectado equivalente al de fuentes descartadas.

### 4.2 Nota sobre Katie Edmonds

FNTP (Functional Nutritional Therapy Practitioner), no es médica ni dietista registrada, pero su libro trae prólogo del director científico de la Endometriosis Foundation of America. Se usa como complemento aplicado de la guía clínica ESHRE, mismo patrón que Kushner (clínico) más Summer Kessel (práctico) para obesidad y GLP-1.

### 4.3 Menopausia, nota de alcance

Confirmado con la nutrióloga (ago 2026): hoy es un padecimiento atendido en pocas ocasiones, pero es un área de expansión activa de su práctica. Se incluye en la KB con dos fuentes de nivel A desde ahora, para estar lista cuando esa parte de la práctica crezca.

---

## 5. Caso de estudio: por qué se excluyó a Jessie Inchauspé

Este caso se documenta en detalle porque establece el procedimiento a seguir cuando el motor de IA evalúe autores nuevos en sus búsquedas web.

**Perfil:** *Glucose Revolution* (2022). Autora con formación en matemáticas y bioquímica, no médica ni dietista. Se hizo conocida por Instagram como "Glucose Goddess" (más de 1.8 millones de seguidores). Su propio libro declara: *"Soy científica, no doctora."*

**Evidencia encontrada en la investigación (agosto 2026):**

- Una organización dedicada a monitorear desinformación en salud la nombró explícitamente como ejemplo de "influencers que desinforman sobre picos de glucosa", citando a un experto que documentó declaraciones incorrectas de su parte.
- Múltiples dietistas registrados (no un caso aislado) publicaron análisis críticos señalando que carece de las credenciales para dar consejo nutricional a ese nivel, y que su base de evidencia es principalmente su propia experiencia individual con un monitor de glucosa, generalizada como si aplicara a cualquier persona.
- Conflicto de interés comercial activo: lanzó un suplemento ("Anti-Spike Formula") promovido como "clínicamente probado", afirmación que nutriólogos han señalado carece de pruebas clínicas independientes.
- El respaldo público más citado a su favor (un investigador de longevidad de Harvard) pierde peso al confirmarse que ese mismo investigador es asesor de una empresa de monitores de glucosa, es decir, tiene su propio interés comercial en el tema.

**Regla resultante para el motor de IA:** al evaluar un autor o fuente nueva encontrada en una búsqueda web, antes de usarla como apoyo, verificar:

1. ¿Tiene una credencial clínica o académica verificable en el tema (médico, dietista registrado, investigador con publicaciones revisadas por pares), o es principalmente conocido por su presencia en redes sociales?
2. ¿Vende un producto propio (suplemento, programa, marca personal) cuyas afirmaciones de eficacia dependen del contenido que está citando? Esto es un conflicto de interés que exige más escrutinio, no descalificación automática.
3. ¿Existen críticas de profesionales de salud identificables (no comentarios anónimos) que señalen errores de exactitud, no solo diferencias de opinión o estilo?
4. ¿Existe alguna evaluación independiente y con nombre (una reseña académica, un profesional de la salud identificado) que respalde el contenido, más allá del marketing propio del autor?

Ninguna señal por sí sola descalifica una fuente. La combinación de "sin credencial clínica" más "conflicto comercial activo" más "señalado específicamente por profesionales de salud" es lo que sí la descalifica, como ocurrió en este caso. El caso de Rebecca Fett (sección 4.1) demuestra que un autor sin título médico puede pasar el filtro cuando la evidencia de respaldo profesional real existe.

---

## 6. Pendientes

- Ninguna fuente pendiente identificada por el momento. Si en el futuro se detecta un hueco de cobertura (por ejemplo, un padecimiento nuevo que Marifer empiece a atender), este documento se actualiza antes de incorporar el material nuevo a la KB operativa.

---

## 7. Bitácora

| Fecha | Cambio |
|---|---|
| 2026-08-27 | v1.0, inventario inicial de 17 fuentes (19 recibidas, 1 excluida por criterio de autoridad, 1 combinada correctamente contada como parte de un archivo con 3 libros). Se establece el procedimiento de evaluación de fuentes nuevas para búsquedas web del motor de IA, documentado a partir del caso Inchauspé vs. Fett |
