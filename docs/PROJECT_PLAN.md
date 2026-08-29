# Sistema Integral de Nutrición, Documento Maestro del Proyecto

**Versión:** 3.2
**Fecha:** 27 de agosto de 2026
**Estado:** Fase 0 completa. Infraestructura lista. Guía de estilo cerrada. Recolección de material en curso.

---

## 1. Resumen del proyecto

Plataforma web para **Marifer Utrilla, Nutrición y Salud Hormonal**, nutrióloga en Puebla, México, especializada en obesidad, diabetes, resistencia a la insulina, SOP, endometriosis, salud hormonal, fertilidad y embarazo. El sistema gestiona expedientes clínicos, genera dietas personalizadas asistidas por IA (con revisión y aprobación humana obligatoria), produce PDFs con su identidad visual y los envía al paciente.

**Principio rector:** la nutrióloga no es adepta a la tecnología. Todo debe resolverse con un doble clic y una interfaz simple, usable desde su tablet (Redmi Pad Pro 2) y su PC con Windows 11. La IA propone, ella siempre decide.

**Contexto:** trabaja de forma independiente. Recibe pacientes propios y referidos por el médico de UniDO, ginecólogos, internistas y especialistas en fertilidad. Atiende presencial y en línea (algunos pacientes en el extranjero, por eso inglés disponible). Volumen actual: 20 a 50 consultas al mes.

---

## 2. Decisiones técnicas cerradas (Fase 0)

| Componente | Decisión | Notas |
|---|---|---|
| Servidor | **DigitalOcean Droplet Basic**, 1 GB RAM / 1 vCPU / 25 GB SSD, $6 USD/mes | Más respaldo semanal 20% (~$1.20). Sin contrato, sin alta. Creado: `sistema-nutricion`, Ubuntu 24.04, NYC1, IP `165.22.7.251` |
| Stack | **Python** (backend, motor IA, generación de documentos) | Terreno nativo de Michel, repo en GitHub como los demás proyectos |
| Stack interno (dentro del droplet) | **FastAPI** (backend asíncrono) más **HTML + Tailwind + HTMX** (interfaz) | No son alternativas de hosting, son las piezas que corren dentro del droplet. FastAPI es el cerebro que procesa cada clic, HTML+Tailwind+HTMX es la pantalla. GitHub solo guarda el código, no lo ejecuta |
| Motor de IA, análisis | **Gemini API (Google)** | Razonamiento dietético, KB completa en contexto (in-context RAG, sin embeddings), lectura nativa de PDFs InBody, cálculos y banderas. Salida: plan técnico estructurado |
| Motor de IA, redacción | **Claude API (Anthropic)** | Solo documentos para humanos: dieta final, recomendaciones, carta al médico. Redacta sobre el plan ya resuelto por Gemini. Costo estimado $2 a $5 USD/mes |
| Base de datos | **SQLite** (un solo archivo) | Gratis, no es un servicio contratado. Suficiente para el volumen actual, encaja natural con el respaldo nocturno a Google Drive |
| Base de alimentos | **OpenFoodFacts** (gratuita, abierta, sin key) | FatSecret queda como mejora posterior (acceso restringido por región) |
| Dominio | **mafernut.com**, registrado y administrado en **Cloudflare** | El DNS (registro A) apunta al droplet de DigitalOcean, para que la app sea accesible en ese dominio |
| Correo de envío | **contacto@mafernut.com**, cuenta activa en Hostinger, DNS completo | 8 registros en el DNS de Cloudflare: verificación TXT, 2 MX (mx1/mx2.hostinger.com, prioridad 5/10), SPF, 3 CNAME de DKIM (a/b/c), y DMARC (`p=none`). Las 4 validaciones de Hostinger (recepción, SPF, DKIM, DMARC) confirmadas en verde. El hosting compartido de Hostinger sigue sin usarse para la aplicación, únicamente para el correo |
| Idiomas | Español (México) por defecto, inglés disponible | Alimentación, ingredientes y lenguaje adaptados a Puebla |
| InBody | **Opcional por paciente** (interruptor con o sin InBody) | Solo disponible para pacientes atendidos en UniDO. Sin InBody, captura manual de peso y medidas |

Proveedores evaluados y descartados para el VPS: Hostinger KVM (precio promocional que sube al renovar), IONOS MX (contrato anual más $200 de alta), Hetzner (planes baratos solo en Europa), Contabo (sin respaldos incluidos, throttling de CPU). También se evaluó y descartó PaaS tipo Render o Railway, por claridad conceptual.

---

## 3. Los 7 módulos del sistema

1. **Base de datos de pacientes.** Historias clínicas, perfil, mediciones, historial de citas y dietas. Dinámica, consultable por la IA, versionada.
2. **Captura de información.** Plantilla de intake inicial y plantilla de follow-up, optimizadas para tablet.
3. **Motor de IA nutricional.** Genera la dieta sugerida a partir de: expediente del paciente, knowledgebase, y búsqueda web controlada con lista blanca. Prohibido: redes sociales, influencers, modas sin sustento.
4. **Knowledgebase.** Fuente de verdad: guías clínicas por padecimiento, Tabla de Equivalencias Nutrimentales propia, alimentación mexicana, base de alimentos vía API.
5. **Flujo de aprobación y entrega.** La IA propone, la nutrióloga revisa, un clic aprueba, se genera el PDF y se envía por correo.
6. **Portal del paciente** (fase posterior). El paciente ve su dieta y avance en la web, con pagos en línea.
7. **La plataforma.** La envoltura: una sola interfaz web sencilla, responsiva, doble clic y a trabajar.

---

## 4. Mapa de desarrollo por fases

Regla de oro: **no se avanza de fase hasta que la nutrióloga use y apruebe la anterior en la vida real.** Cada fase entrega algo usable de inmediato.

### Fase 0, Cimientos y decisiones. COMPLETA
Stack, servidor, IA, base de alimentos, alcance, identidad visual y guía de estilo.

### Fase 1, Base de datos y plantillas
- Estructura de pacientes y expedientes
- **Historia Clínica (intake inicial), APROBADA.** Rediseño de las 33 preguntas originales en 11 secciones, documento de referencia en `docs/Historia_Clinica_v2.docx`. Es la especificación de contenido, no el formulario final: en esta fase se construye como formulario interactivo dentro de la app (campos de texto, menús desplegables donde aplique, casillas sí/no, navegable por sección, pensado para tablet). Se espera seguir ajustando campos con el uso real, sin problema. Secciones: datos generales, objetivos y expectativas, antecedentes heredofamiliares, antecedentes personales patológicos, antecedentes gineco-obstétricos, historia de peso, revisión de síntomas, alergias/intolerancias/preferencias (separadas), hábitos alimentarios, actividad física/sueño/hábitos, suplementos/medicamentos/laboratorios
- **Follow-up, APROBADO.** Documento de referencia en `docs/Follow_Up_v1.docx`, mismo tratamiento que la Historia Clínica (especificación de contenido, no el formulario final). Secciones: datos de la consulta (número de consulta automático, asignado por el sistema, nunca tecleado), continuidad del plan anterior (porcentaje de apego, promedio de días de ejercicio, qué le gustó/no le gustó, cambios que hizo, en qué puede mejorar), estatus médico y tratamiento, medición de hoy (peso, IMC, porcentaje de grasa, masa grasa en kg, MME, grasa visceral, alineado con los campos que ya extrae el InBody), y notas y ajustes acordados para el siguiente periodo. Sin plantilla rígida por diseño, la mayoría queda como texto libre guiado. Cada follow-up queda ligado al anterior en el expediente, para alimentar el resumen pre-consulta automático de la Fase 3. Se espera seguir ajustando campos con el uso real, sin problema
- Plantillas de intake y follow-up usables desde tablet
- **Historial de versiones de dietas** (ninguna dieta se sobreescribe jamás)
- Datos estructurados de medicación y padecimientos (base para las banderas clínicas)
- **Registro de opciones ya prescritas por paciente**, para no repetir el mismo desayuno tres consultas seguidas
- **Lectura del InBody**, basada en 3 reportes reales de InBody370S (clínica UNIDO): el PDF crudo se envía como adjunto a la variante económica y rápida de Gemini (revisar cuál es la vigente al construir) con prompt restrictivo, en JSON estricto. Sin parsear línea por línea con código.
  - **Campos a extraer** (set ampliado tras ver los reportes reales): peso, porcentaje de grasa corporal, masa grasa corporal, masa de músculo esquelético (MME), nivel de grasa visceral, tasa metabólica basal, IMC. Estos son insumo interno para el motor de IA, nunca se muestran al paciente en el documento final (sigue vigente la regla de cero calorías y macros visibles)
  - **Historial dentro del propio PDF:** el reporte trae su propia tabla de mediciones anteriores (de 1 hasta 9 o más puntos, la cantidad varía por paciente). La instrucción a Gemini debe pedir leer cuantos puntos existan, sin asumir una cantidad fija, y regresar cada uno con su fecha. Una sola foto de un paciente con historial largo puede alimentar varios puntos de seguimiento de una sola vez
  - Manejo de errores: `json.loads()` en Python, si falla **un reintento automático**, y si el segundo intento también falla, campo en blanco para que ella lo teclee en 5 segundos. Chequeo de sensatez posterior (peso entre 20 y 300 kg) por si la IA malinterpreta una celda
  - **Identificación del paciente, nunca automática.** El reporte trae un ID de la clínica (ej. `040225-1`) y un nombre que puede venir truncado (ej. "juan carlos be..."), así que ninguno de los dos se usa para vincular solo. Mecanismo de 3 capas:
    1. **Búsqueda y selección de una lista real de pacientes**, nunca texto libre. El nombre del PDF sirve solo de referencia visual para que ella confirme
    2. **Pantalla de comparación antes de guardar:** edad, sexo y estatura del PDF contra lo ya registrado en el expediente. Si no coinciden, se bloquea la confirmación automática y se muestra alerta, obligando a revisar
    3. **Lista de IDs conocidos por paciente** (no un ID único): un mismo paciente puede tener varios IDs a lo largo del tiempo si cambia de clínica o dispositivo. El primer uso de un ID nuevo pide búsqueda completa y confirmación; los siguientes usos del mismo ID ya sugieren el paciente para un solo toque. La confirmación humana nunca se salta, solo se acelera
- Entregable: captura digital de pacientes funcionando, aun sin IA

### Fase 2, Knowledgebase y base de alimentos
- **Guías clínicas por padecimiento, APROBADAS.** 17 fuentes (19 recibidas, 1 excluida) cubriendo obesidad, diabetes tipo 2, RI, SOP, endometriosis, fertilidad, embarazo, salud hormonal general, menopausia (área de expansión futura) y recetario para pacientes con GLP-1. Inventario completo, nivel de autoridad de cada fuente y criterio de evaluación en `docs/KNOWLEDGEBASE.md`
- **Procedimiento de evaluación de fuentes nuevas para búsquedas web del motor de IA**, documentado a partir de un caso real: se investigó y comparó a dos autoras de perfil similar (ambas sin título médico, ambas con libros exitosos): una se excluyó (evidencia de errores señalados por dietistas registrados, conflicto de interés comercial activo con un suplemento propio) y otra se incluyó con nivel ajustado (respaldo de una reseña académica publicada por una ginecobstetra en una revista revisada por pares). El criterio de 4 preguntas queda documentado en `docs/KNOWLEDGEBASE.md` sección 5, y debe aplicarse cada vez que el motor evalúe una fuente nueva encontrada en la web
- **Tabla de Equivalencias Nutrimentales (TEN), decisión final.** Se descartó usar el SMAE directamente: es una publicación protegida por derechos de autor de Fomento de Nutrición y Salud, A.C., y aunque Marifer posee un ejemplar comprado legítimamente, eso da derecho a usarlo con su criterio clínico para escribir dietas, no a digitalizar su compilación específica dentro de un producto de software. En su lugar, se construye una tabla propia (mismo método general de "alimentos equivalentes", categorías y valores de referencia de ciencia nutricional de dominio público, confirmados por estar publicados de forma independiente en múltiples fuentes sin relación entre sí) más datos de OpenFoodFacts para alimentos mexicanos específicos. Diseño completo en `docs/TABLA_DE_EQUIVALENCIAS.md`. Nombrada distinto a SMAE para evitar confusión de marca; el archivo técnico será `tabla_equivalencias.json`, no `smae.json`. **Regla crítica sin cambios:** cálculo interno para que la nutrióloga decida cuántos equivalentes prescribir, nunca expuesta al paciente en crudo. La construcción del archivo real con alimentos mexicanos poblados queda pendiente para el código de la Fase 2
- **Guía clínica de referencia:** EASO (European Association for the Study of Obesity) para obesidad, usada como marco de referencia, no como protocolo estricto de seguir al pie de la letra. Otras guías por padecimiento (diabetes, RI, SOP, endometriosis, fertilidad, GLP-1) pendientes de definir con la nutrióloga
- **Biblioteca de bloques de contenido** (15 bloques identificados, ver `GUIA_DE_ESTILO.md` sección 6)
- **Valores clínicos de referencia** ya recuperados de su material: rangos de glucosa en ayunas, preprandial, posprandial 1h y 2h, nocturna, y HbA1c
- Conexión a OpenFoodFacts
- Lista blanca de fuentes web permitidas

### Fase 3, Motor de IA
- **Arquitectura de dos motores:** Gemini analiza (expediente, KB completa en contexto, PDFs) y produce el plan técnico estructurado. Claude redacta los documentos finales para humanos. La frontera entre ambos es un documento estructurado: Gemini nunca escribe para el paciente, Claude nunca calcula ni decide clínicamente
- **`STYLE_SPEC.md` se inyecta en el prompt de redacción** como contrato de estilo
- **Regla de individualización:** la biblioteca guarda el qué, la IA decide el cómo y el cuánto. Dos pacientes con la misma condición reciben el mismo criterio clínico y distinta redacción
- **Resumen pre-consulta automático** (media página antes de cada cita, lo genera Gemini porque es análisis, no redacción para el paciente)
- **Lógica de banderas clínicas.** GLP-1 implica proteger masa muscular y proteína, SOP con RI tiene sus consideraciones propias. Nunca opina sobre medicamentos, solo alerta y refiere al médico
- **Análisis de estudios de laboratorio (subidos por la nutrióloga, enviados por el médico tratante).** Mismo mecanismo que el InBody: el PDF se envía crudo a Gemini, que lee de forma nativa. **Regla no negociable: nunca diagnostica, eso es trabajo exclusivo del médico.** Lo que sí hace es un análisis completo cruzando el resultado contra tres fuentes ya presentes en el expediente, y levanta advertencias con su justificación, nunca una conclusión clínica:
  - **Contra alimentación:** por ejemplo, ferritina baja en alguien con dieta pobre en hierro registrada en su recordatorio de 24 horas
  - **Contra suplementos:** interferencias de laboratorio conocidas, como biotina en dosis alta alterando pruebas de tiroides, o exceso de calcio/vitamina D elevando calcio sérico
  - **Contra medicamentos:** GLP-1 asociado a riesgo de deficiencia de B12 y vitamina D, y a pérdida de masa muscular reflejada en creatinina; metformina asociada a deficiencia de B12 a largo plazo
  - Salida: lista de advertencias accionables desde nutrición, visible solo para la nutrióloga, nunca para el paciente

### Fase 4, Aprobación, PDF y envío
- Flujo de un clic: revisar, aprobar, PDF, correo
- **Botón "Modificar propuesta".** Campo de texto simple en la pantalla de revisión (por ejemplo "quita el aguacate y cambia las colaciones por opciones frías") y la IA regenera. Ingeniería: el ajuste se aplica siempre sobre la última versión guardada en el historial, no sobre un hilo de conversación libre. Se envía versión actual más instrucción de ajuste, y el resultado se guarda como nueva versión. System prompt con regla explícita de devolver únicamente la dieta modificada, cero saludos, cero disculpas, cero relleno
- **Motor de maquetación de flujo.** La caja se dibuja alrededor del texto, no al revés. El motor mide el contenido, dibuja la tarjeta del tamaño exacto, y si no cabe corta limpio y continúa en la siguiente lámina con su encabezado. El desbordamiento deja de ser posible por construcción
- **Dos tipos de documento:** plan personalizado (con nombre y fecha) y guía de padecimiento (reutilizable, se adjunta según diagnóstico)
- **Pie de página** en toda lámina: fecha exacta, próxima cita, número de lámina y datos de contacto. **Datos confirmados:** "Marifer Utrilla Lack, Nutrióloga y Especialista en Salud Hormonal, Educadora en Diabetes", teléfono/WhatsApp +52 238 136 7151
- **Módulo de acciones de salida**, común a los 4 tipos de documento (dieta, guía, recomendación, carta al médico), disponible al finalizar cualquiera de ellos:
  - **Enviar por correo:** casilla de sí o no antes de confirmar, si está marcada se envía automático al aprobar
  - **Descargar localmente:** botón que guarda el PDF en su computadora o tablet
  - **Enviar por WhatsApp (camino simple):** genera un enlace que abre WhatsApp con el PDF ya adjunto, ella solo confirma el envío dentro de WhatsApp. Sin costo, sin cuentas nuevas, funciona desde el día uno
  - Descartada la opción de imprimir directo desde el sistema: es redundante una vez que el archivo ya se puede descargar
  - **Mejora futura, no bloqueante:** API oficial de WhatsApp Business para envío automático sin confirmación manual. Requiere cuenta de negocio verificada en Meta, un proveedor intermediario (Twilio o similar), costo por mensaje, y plantillas pre-aprobadas por Meta para los primeros contactos. Se evalúa solo si el volumen de pacientes lo justifica
- **Gráficas de progreso** (peso, porcentaje de grasa, masa muscular en el tiempo, con o sin InBody)
- **Carta al médico referente** (informe breve de evolución para el doctor que refirió, la redacta Claude)

### Fase 5, Plataforma pulida
- Interfaz unificada, responsiva, tablet first
- **Respaldo diario cifrado de la base de datos a Google Drive** (tarea nocturna)

### Fase 6, Portal del paciente y pagos (opcional, se decide al llegar)
- Acceso web del paciente a su dieta y avance
- Pagos en línea (Mercado Pago u otra)
- **Recordatorios de cita**

Sugerencia evaluada y descartada por ahora: dictado por voz al expediente (retomable si la nutrióloga lo pide).

---

## 5. Identidad y estilo

Documentados en detalle en `docs/GUIA_DE_ESTILO.md` (español, referencia humana) y `docs/STYLE_SPEC.md` (inglés, se inyecta en el prompt). Ambos derivados del análisis de 22 documentos reales entregados a pacientes entre febrero y agosto de 2026.

Puntos clave:

- **Su voz:** primera persona plural cómplice ("damos prioridad", "vamos a eliminar"), diminutivos afectivos (paquetito, cajita, chilito), imperativo corto, siempre explica el para qué, e instrucciones condicionales con empatía
- **Sin frases motivacionales genéricas.** Su calidez no viene de porras, viene de hablar en plural, explicar el porqué y anticipar las dificultades reales del paciente
- **Medidas caseras siempre**, gramos solo para proteína. Nunca calorías ni macros
- **Vocabulario poblano y mexicano** conviviendo con anglicismos ya asimilados (smoothie, avotoast, lunch). Ambos son suyos
- **Reglas anti IA:** solo caracteres de teclado normal (nada de guiones largos, comillas curvas ni líneas de `====`), frases prohibidas, y variación natural obligatoria contra la simetría artificial. La flecha `→` sí se autoriza porque es suya
- **Mayúsculas** solo en títulos, encabezados y etiquetas cortas. Los párrafos largos centrados en mayúsculas se eliminan
- **Logo confirmado**, leyenda oficial "Nutrición y Salud Hormonal". `Mafer_Logo_Grande.png` para encabezados de documento y web (alta resolución, transparente), versión 360×360 para usos cuadrados (ícono, perfil), `Limon.png` como elemento decorativo suelto sin texto

---

## 6. Requisitos pendientes (checklist de material)

### De la nutrióloga
- [x] Dietas reales anonimizadas. Recibidos 22 documentos, base de la guía de estilo
- [x] Colores e identidad visual, extraídos del material
- [x] Logo, en PNG con transparencia (no vector real, pero suficiente calidad). Leyenda oficial confirmada: "Nutrición y Salud Hormonal" (se descartan las variantes con "Nutrición y Vida en Equilibrio", tagline anterior). Archivo principal para encabezados: `Mafer_Logo_Grande.png` (2413×1546 px, transparente); archivos cuadrados para ícono o foto de perfil: `Logo_Marifer_360x360.png` y equivalente; elemento decorativo suelto disponible: `Limon.png` (el círculo sin texto, alta resolución)
- [x] Datos de contacto para el pie de página. Marifer Utrilla Lack, Nutrióloga y Especialista en Salud Hormonal, Educadora en Diabetes, +52 238 136 7151 (mismo número para WhatsApp). Sin redes pendientes de agregar
- [x] Validar el cambio de mayúsculas. Validado
- [x] Su formato actual de intake. Compartido y analizado (Historia_Clínica.docx), rediseño en discusión, ver Fase 1
- [x] PDFs de InBody de ejemplo. Recibidos 3 reportes reales de InBody370S (clínica UNIDO), base del diseño de extracción y del mecanismo de identificación de paciente
- [x] Confirmar si trabaja con SMAE y qué guías clínicas respeta. Usaba el SMAE comprado como referencia personal; el sistema no lo digitaliza (ver decisión de la Tabla de Equivalencias Nutrimentales propia en la Fase 2). Guía clínica de obesidad: EASO, como referencia, no protocolo estricto
- [x] Aviso de privacidad para datos de salud. Generado (`docs/Aviso_de_Privacidad.docx`) con base en la LFPDPPP vigente desde marzo 2025 (ley nueva, no la de 2010; autoridad ahora es la Secretaría Anticorrupción y Buen Gobierno tras la desaparición del INAI). Cubre datos recabados, finalidades, uso de IA como encargada del tratamiento con obligación de confidencialidad, transferencia internacional (servidor en EE.UU.), derechos ARCO, cláusula de plazos de conservación/bloqueo/supresión de datos, y bloque de consentimiento firmado. Datos completados: Lic. María Fernanda Utrilla Lack, domicilio en Av. Kepler 2143, Reserva Territorial Atlixcáyotl, Puebla. Pendientes: formato específico de solicitud ARCO (separado de este aviso), y revisión de un abogado especializado antes de uso real (el reglamento de la ley nueva aún no se publica)

### De Michel
- [x] Crear cuenta de DigitalOcean y droplet. `sistema-nutricion`, Ubuntu 24.04, NYC1, IP `165.22.7.251`, $7.20 al mes con respaldo semanal activo
- [x] Obtener API key de Gemini (Google AI Studio, análisis)
- [x] Obtener API key de Anthropic (solo redacción)
- [x] Crear repo de GitHub del proyecto (privado, con .gitignore de Python)
- [x] Subir la documentación al repo en `docs/`
- [x] Definir correo de envío. Completado y verificado al 100%: `contacto@mafernut.com` en Hostinger, con los 8 registros DNS correctos en Cloudflare (MX, SPF, DKIM, DMARC, verificación) y las 4 validaciones de Hostinger en verde

---

## 7. Estructura del repositorio

```
sistema-nutricion/
├── README.md
├── .gitignore
├── assets/
│   └── logo/
│       ├── Limon.png
│       ├── Logo_Marifer_360x360.png
│       ├── Mafer_Logo_Grande.png
│       ├── Mafer_Profile_Pic_360X360.png
│       ├── Marifer_Inicio.jpg
│       └── Marifer_Inicio.png
└── docs/
    ├── PROJECT_PLAN.md
    ├── GUIA_DE_ESTILO.md
    ├── STYLE_SPEC.md
    ├── Historia_Clinica_v2.docx
    ├── Follow_Up_v1.docx
    ├── KNOWLEDGEBASE.md
    ├── TABLA_DE_EQUIVALENCIAS.md
    └── Aviso_de_Privacidad.docx
```

**Nota de nomenclatura:** nombres de archivo sin espacios (guion bajo en su lugar), para evitar errores al referenciarlos desde código.

Las API keys nunca van al repo. Viven en un archivo `.env` local, ya cubierto por el .gitignore de Python.

---

## 8. Principios de diseño (no negociables)

1. **Simplicidad radical.** Máximo uno o dos procesos separados, nada de comandos ni pasos que confundan.
2. **La IA nunca aprueba sola.** Toda dieta pasa por revisión y clic de aprobación de la nutrióloga.
3. **Fuentes serias únicamente.** Knowledgebase primero, web solo como soporte con lista blanca. Cero redes sociales, influencers o modas.
4. **La voz es suya, no de la IA.** El paciente debe reconocer a su nutrióloga en cada documento. Nada de texto que se sienta generado.
5. **Individualización real.** Mismo criterio clínico, distinta redacción y distintos ejemplos para cada paciente. Se acaba el copy paste.
6. **Nada se pierde.** Historial completo, versionado, respaldo doble (DigitalOcean y Google Drive).
7. **México primero.** Alimentos, ingredientes y lenguaje de Puebla, inglés disponible cuando se necesite.

---

## 9. Bitácora de cambios

| Fecha | Cambio |
|---|---|
| 2026-08-26 | v1.0, planeación inicial cerrada: módulos, mapa de fases, decisiones técnicas, sugerencias adoptadas, checklist |
| 2026-08-26 | v1.1, motor de IA cambia a arquitectura de dos motores: Gemini para análisis, Claude para redacción |
| 2026-08-26 | v1.2, hosting confirmado en DigitalOcean. Se documenta el stack interno. Se adoptan botón "Modificar propuesta", SMAE como JSON e InBody leído crudo |
| 2026-08-26 | v1.3, ingeniería detallada de las tres adopciones anteriores |
| 2026-08-26 | v1.4, checklist "De Michel" completo salvo el correo de envío |
| 2026-08-27 | v1.5, análisis de 22 documentos reales de la nutrióloga. Se identifica la marca (Marifer Utrilla, Nutrición y Salud Hormonal) y se crean `GUIA_DE_ESTILO.md` y `STYLE_SPEC.md`. Nuevas decisiones: dos tipos de documento, biblioteca de bloques paramétrica que guarda el qué y no el cómo, motor de maquetación de flujo que hace imposible el desbordamiento, reglas anti IA, mayúsculas solo donde sirven, y pie de página con fecha, próxima cita y número de lámina. Se corrige el principio de tono: sin frases motivacionales genéricas. Se define la estructura del repo |
| 2026-08-27 | v1.6, se agrega el módulo de acciones de salida al finalizar cualquier documento: correo (casilla sí o no), descarga local, y WhatsApp por enlace directo (camino simple, sin costo). Se descarta imprimir por redundante con la descarga. Queda anotada la API oficial de WhatsApp Business como mejora futura no bloqueante |
| 2026-08-27 | v1.7, análisis de 3 reportes reales de InBody370S (clínica UNIDO). Se amplía el set de campos a extraer, se agrega lectura del historial interno del PDF (número de puntos variable), y se define el mecanismo de identificación de paciente en 3 capas: búsqueda por lista (nunca texto libre), pantalla de comparación que bloquea ante datos que no cuadran, y lista de IDs conocidos por paciente para admitir cambios de clínica o dispositivo sin perder la confirmación humana obligatoria |
| 2026-08-27 | v2.0, se confirman datos de contacto y validación de mayúsculas. Se analiza la Historia Clínica actual (33 campos) contra un intake nutricional estándar, se identifican 6 vacíos (destaca antecedentes gineco-obstétricos, dada la especialidad) y una reorganización en 11 secciones, pendiente de aprobación para generar la versión nueva. Se diseña el follow-up de captura libre-guiada, ligado entre consultas. Se agrega el análisis de estudios de laboratorio: mismo mecanismo que InBody, cruza resultados contra alimentación, suplementos y medicamentos, solo advertencias accionables para la nutrióloga, nunca diagnóstico. Se aclara la regla crítica del SMAE (cálculo interno, nunca expuesto en crudo) y se confirma EASO como guía de referencia para obesidad |
| 2026-08-27 | v2.1, logo recibido y confirmado (6 archivos PNG con transparencia, sin vector real pero de calidad suficiente). Se detectó y resolvió una discrepancia de tagline entre archivos ("Nutrición y Salud Hormonal" vs "Nutrición y Vida en Equilibrio"); queda vigente la primera. Se asigna cada archivo a su uso (encabezados, ícono cuadrado, elemento decorativo). Checklist de Michel completo salvo el correo de envío |
| 2026-08-27 | v2.2, se documenta la estructura real del repo con la carpeta `assets/logo/` ya creada, y se anota la recomendación de quitar espacios de los nombres de archivo |
| 2026-08-27 | v2.3, Historia Clínica aprobada: se genera `Historia_Clinica_v2.docx` con las 11 secciones (incluye antecedentes heredofamiliares, gineco-obstétricos, historia de peso y objetivos, antes ausentes). Se aclara que este Word es la especificación de contenido, no el formulario final, el cual se construirá interactivo dentro de la app en la Fase 1. Se deja explícito que los campos seguirán ajustándose con el uso real |
| 2026-08-27 | v2.4, Knowledgebase clínica aprobada: 17 fuentes analizadas y clasificadas por nivel de autoridad en `docs/KNOWLEDGEBASE.md`. Se investigó a fondo un caso de dos autoras de perfil similar sin título médico; una se excluyó por conflicto de interés comercial y errores señalados por dietistas registrados, otra se incluyó con nivel ajustado por tener respaldo académico verificable. Se documenta el procedimiento de 4 preguntas para que el motor de IA evalúe cualquier fuente nueva que encuentre en la web. Se confirma la menopausia como área de expansión futura de la práctica |
| 2026-08-28 | v2.5, dominio y correo resueltos: `mafernut.com` registrado y administrado en Cloudflare (DNS apunta al droplet), correo de envío resuelto con Hostinger Premium (ya incluido en el plan, conectado vía registros MX en el DNS de Cloudflare). El hosting compartido de Hostinger queda limitado exclusivamente al correo, la aplicación sigue viviendo solo en el droplet |
| 2026-08-28 | v2.6, cuenta de correo `contacto@mafernut.com` creada y verificada en Hostinger (registro TXT confirmado en el DNS de Cloudflare). Checklist de infraestructura de Michel queda completo |
| 2026-08-28 | v2.7, configuración de correo completada al 100%: agregados MX, SPF, 3 DKIM y DMARC en el DNS de Cloudflare (8 registros en total). Las 4 validaciones de Hostinger (recepción, antisuplantación, antispam, antiphishing) confirmadas en verde |
| 2026-08-28 | v2.8, primer borrador del Aviso de Privacidad generado, verificando primero que la LFPDPPP cambió por completo en marzo de 2025 (ley nueva, no solo cambio de autoridad; INAI desaparecido, ahora Secretaría Anticorrupción y Buen Gobierno). Cubre datos sensibles de salud, uso de IA como encargada del tratamiento, transferencia internacional de datos, y derechos ARCO. Marcado como borrador pendiente de revisión legal profesional, ya que el reglamento de la ley nueva aún no existe |
| 2026-08-28 | v2.9, Aviso de Privacidad completado con datos reales: nombre legal Lic. María Fernanda Utrilla Lack, domicilio del consultorio en Puebla, fecha de actualización 01 de septiembre de 2026. Sigue pendiente únicamente la revisión de un abogado especializado |
| 2026-08-28 | v3.0, se agrega al Aviso de Privacidad la cláusula de plazos de conservación, bloqueo y supresión de datos (verificado que la ley nueva formaliza este ciclo en dos fases, no tres), y se refuerza la sección de IA con la obligación explícita de confidencialidad de los encargados del tratamiento. Queda pendiente, por separado, un formato específico de solicitud ARCO |
| 2026-08-28 | v3.1, Follow-up aprobado: se genera `Follow_Up_v1.docx` con captura libre-guiada organizada en 5 secciones, incluyendo porcentaje de apego al plan, promedio de días de ejercicio, y mediciones alineadas con los campos reales del InBody (peso, IMC, porcentaje de grasa, masa grasa en kg, MME, grasa visceral). Se aclara que el número de consulta es automático, asignado por el sistema. Con esto queda cerrada toda la planeación de contenido de la Fase 1, salvo el SMAE, en pausa hasta contar con la fuente real de equivalencias |
| 2026-08-28 | v3.2, decisión final sobre equivalencias: se descarta usar el SMAE real (protegido por derechos de autor, incluso siendo un ejemplar comprado legítimamente por Marifer, la compra da derecho de uso profesional pero no de digitalizar la compilación dentro de un producto de software). Se construye una Tabla de Equivalencias Nutrimentales propia, con nombre distinto para evitar confusión de marca, basada en valores de ciencia nutricional de dominio público (verificados por estar publicados de forma independiente en múltiples fuentes) más OpenFoodFacts. Diseño completo en `docs/TABLA_DE_EQUIVALENCIAS.md`. Se identifica que la cuenta de OpenFoodFacts de Michel puede usarse para contribuir alimentos mexicanos faltantes a la base de datos abierta. Con esto, toda la planeación de contenido de la Fase 1 y las decisiones clave de la Fase 2 quedan cerradas |
