# Fuentes de datos de alimentos

**Versión:** 3.0
**Fecha:** 21 de septiembre de 2026
**Estado:** implementado y verificado en el servidor

---

## 1. Jerarquía de fuentes

El sistema consulta cuatro fuentes con prioridades distintas. La lógica vive en `alimentos.py`, que es el único punto de entrada para el resto del sistema.

| Prioridad | Fuente | Para qué | Tipo |
|---|---|---|---|
| 1 | **Marifer** | Base de equivalencias propia de la nutrióloga, clasificada por grupo SMAE real. Fuente principal | Archivo local |
| 2 | **FNDDS** | Alimentos que Marifer no cubre bien (salmón, quinoa, kale, pistaches, y en general alimentos no tradicionales en México) | Archivo local |
| 3 | **BAM 18.1.1** | Último respaldo local si ninguna de las dos anteriores tiene el alimento | Archivo local |
| 4 | **OpenFoodFacts** | Solo productos de marca, con verificación humana | API |

Esta jerarquía reemplazó a la anterior (BAM → USDA en línea → OpenFoodFacts) el 3 de septiembre de 2026. El cliente de la API del USDA (`usda.py`) sigue en el repositorio pero **ya no lo usa ningún módulo** — quedó reemplazado por la versión local de FNDDS.

---

## 2. Marifer — fuente principal

**Qué es:** base de equivalencias propia de la nutrióloga, clasificada según el Sistema Mexicano de Alimentos Equivalentes (SMAE). Cada alimento trae su grupo SMAE, su porción casera típica y sus valores nutricionales por 100 g de peso neto, para poder escalar a cualquier cantidad.

**Cobertura:** 2,916 alimentos, sin internet, sin límites de velocidad. Es la versión v10 (21 de septiembre de 2026): los 2,838 alimentos de la base v9 ya limpiados, más 78 que la base anterior tenía y v9 había perdido (entre ellos 17 bebidas alcohólicas: vino, tequila, whisky, ron, etc.).

**Grupos (campo `categoria`):** 19 grupos SMAE con su nombre completo: Verduras, Frutas, Cereales S/G, Cereales C/G, Leguminosas, AOA MBAG, AOA BAG, AOA MAG, AOA AAG, Leche descremada, Leche semidescremada, Leche entera, Leche con azúcar, Grasas sin proteínas, Grasas con proteínas, Azúcares sin grasa, Azúcares con grasa, Libres en energía y Alcohol. Antes se usaban códigos como `AOAMBG` o `CerealesSG`; ningún módulo depende del texto de la categoría. Cuando un mismo nombre existe en dos grupos, el nombre lleva el grupo entre paréntesis, por ejemplo "Castaña (Grasas con proteínas)".

**Campos por alimento (26):**

| Campo(s) | Notas |
|---|---|
| `energia_kcal`, `proteina_g`, `grasa_g`, `carbohidratos_g`, `fibra_g` | Los que usa hoy el verificador |
| `grasa_saturada_g`, `grasa_monoinsaturada_g`, `grasa_poliinsaturada_g`, `colesterol_mg` | Nuevos. `medidas.py` ya pedía `grasa_saturada_g`, que antes salía vacío |
| `calcio_mg`, `hierro_mg`, `potasio_mg`, `sodio_mg`, `fosforo_mg`, `vitamina_a_ug`, `vitamina_c_mg`, `folato_ug` | Micronutrientes, ahora en su columna correcta |
| `etanol_g` | Alcohol de las bebidas; 0 en el resto |
| `azucar_smae_g` | Columna "Azúcar" del SMAE. **No es azúcar total** (vale 0 en muchas frutas y lácteos). No usar como `azucares_g` |
| `indice_glicemico`, `carga_glicemica` | IG del alimento (existe en ~6 % de la base) y carga glicémica por porción, calculada como IG × carbohidratos de la porción ÷ 100 |
| `medida_casera` | `cantidad`, `unidad`, `peso_neto_g` y `peso_bruto_g` de la porción de origen |
| `revision` | Estado del registro (ver abajo) |

Los nombres de los campos que ya existían no cambiaron, así que `marifer.py` funciona igual, sin modificaciones.

**Conversión desde el Excel maestro.** El Excel maestro (`kb_alimentos_v10.xlsx`) trae los valores por porción SMAE y no vive en el repositorio. Para generar el JSON: cada valor = valor de la porción × 100 ÷ peso neto de la porción. "ND" o celda vacía pasa a `null`. Si los macros de la porción pesan más que el peso neto (porciones muy chicas, como 1 cucharadita de manteca), el divisor sube al peso de los macros y el registro lleva el campo `nota_conversion` (37 registros).

**Calidad de los datos (campo `revision`):**

- `OK` (1,602) y `CORREGIDO` (1,202): sin problemas conocidos o corregidos en la limpieza de v10.
- `REINCORPORADO` (76): venían de la base anterior; sus micronutrientes están sin dato. Otros 2 de los 78 reincorporados quedaron en `VERIFICAR`.
- `VERIFICAR` (36): algún dato sin confirmar (energía que no cuadra con los macros, cantidades inferidas por OCR). Ninguno de los alimentos de la tabla de medidas resuelve hoy a un registro `VERIFICAR`.
- Cualquier campo en `null` significa "sin dato confiable", nunca cero. En la limpieza de v10, 937 ceros dudosos de micronutrientes pasaron a `null`.

**La nota anterior sobre el hierro estaba incompleta.** La versión anterior anulaba `hierro_mg` en ~967 alimentos por "errores de captura". La causa real era que varias columnas de micronutrientes estaban cruzadas: en ~65 % de los alimentos con dato, `vitamina_c_mg` contenía calcio; en ~66 %, `folato_ug` contenía hierro; y en ~47 %, `hierro_mg` contenía sodio. v10 corrige las columnas, por lo que los valores de hierro, calcio, sodio y vitaminas ya son utilizables.

**Cómo se busca, y por qué importa el nombre.** El verificador toma el primer resultado de `buscar_palabras`: el nombre más corto que contiene todas las palabras. Por eso una palabra genérica puede caer en otro producto: con la base v10, "fresas" habría devuelto "Pica Fresa" (un dulce), y "zanahoria" ya devolvía "Jugo de zanahoria" con la base anterior. Para esos casos, `medidas_caseras.json` fija el término exacto en `buscar_como` (fresas → "fresa entera", pechuga de pollo → "pechuga de pollo sin piel cocida", zanahoria → "zanahoria picada cruda"). **Después de cualquier cambio a la base o a la tabla de medidas, correr `validar_tabla.py`** (desde `/opt/sistema-nutricion`, con el `venv` del servidor) y revisar que la cobertura no baje.

**Módulo:** `marifer.py`. Búsqueda insensible a acentos, por palabras sueltas en cualquier orden.

---

## 3. FNDDS — reemplazo local del USDA

**Qué es:** Food and Nutrient Database for Dietary Studies del USDA, en versión local simplificada. Reemplaza al cliente en línea que antes vivía en `usda.py`.

**Ventajas sobre la API en línea:** archivo local, sin API key, sin el límite de 1,000 consultas por hora, sin depender de internet ni de la disponibilidad del servicio.

**Cobertura:** 5,431 alimentos, filtrados a los conjuntos `Foundation` y `SR Legacy` (alimentos genéricos analizados en laboratorio, no productos de marca). Valores por 100 g, igual que la BAM y Marifer.

**Nota de idioma:** los nombres vienen en inglés, tal como los publica el USDA. Esta fuente es para el **cálculo interno** del verificador, no para mostrarse en documentos del paciente sin traducir primero.

**Nota de calidad:** revisado contra rangos fisiológicos plausibles antes de la conversión (septiembre 2026). Sin errores de captura encontrados; los únicos valores atípicos (manteca de cerdo, cereal de bebé fortificado, salsa de pescado, té instantáneo concentrado) son correctos.

**Módulo:** `fndds.py`.

---

## 4. BAM, Base de Alimentos de México — respaldo

**Qué es:** proyecto conjunto del INCMNSZ y el INSP, con participación de la Universidad Iberoamericana y el CIAD. Es la base con la que el INSP estima el consumo dietético en sus estudios publicados, incluida la ENSANUT.

**Cobertura:** 2,045 alimentos con 19 campos nutricionales cada uno. Incluye preparaciones tradicionales mexicanas (tinga de pollo, cecina en jitomate, atole de frijol) y alimentos regionales (quelites, papaloquelite, tejocote, chinchayote, pulque) que ninguna otra fuente tiene. Con la migración a Marifer y FNDDS, la BAM pasó de fuente principal a último respaldo local.

**Cita obligatoria:**
> Ramírez Silva, I.; Barragán-Vázquez, S.; Rodríguez Ramírez, S.; Rivera Dommarco, J.A.; Mejía-Rodríguez, F.; Barquera Cervera, S.; Tolentino Mayo, L.; Flores Aldana, M.; Villalpando Hernández, S.; Ancira Moreno, M.; et al. Base de Alimentos de México (BAM): Compilación de la Composición de los Alimentos Frecuentemente Consumidos en el país, Versión 18.1.1, 2021.

**Módulo:** `bam.py`. Búsqueda insensible a acentos y por palabras sueltas en cualquier orden.

---

## 5. OpenFoodFacts, con restricciones

**Qué es:** base colaborativa de productos empacados con código de barras.

**Para qué la usamos:** exclusivamente productos comerciales cuando la nutrióloga escribe un nombre de marca específico ("tostadas Sanissimo", "yogurt griego Yoplait", "leche de almendras Silk").

**Por qué NO es fuente general.** Se hizo una prueba de cobertura con 20 alimentos tomados de las dietas reales de la nutrióloga. Resultado: precisión de 3 de 20. Ejemplos de lo que devolvió:

| Se buscó | Devolvió | Correcto |
|---|---|---|
| tortilla de maíz | Takis Fuego | No |
| nopal | Tostadas de maíz | No |
| aguacate | Aceite de aguacate (839 kcal) | No |
| avena | Cheerios | No |
| huevo | Galletas María sin gluten | No |
| jícama | Chips de jícama (490 kcal) | No |
| queso panela | Queso Panela FUD | Sí |
| queso cottage | Queso Cottage | Sí |
| leche de almendras | SILK sin azúcar | Sí |

La causa es estructural: es una base de **productos con código de barras**, no de alimentos. La jícama del mercado no trae código de barras, así que no está; lo que sí está son las botanas de jícama.

**Riesgo evitado:** si el sistema hubiera aceptado esos resultados sin verificación, habría calculado dietas usando los valores de Takis en lugar de tortilla.

**Regla de seguridad implementada:** ningún resultado de OpenFoodFacts se acepta automáticamente. La función `buscar_marca()` devuelve siempre una lista de candidatos para que la nutrióloga elija. Nunca se consulta esta fuente para alimentos genéricos.

**Límite de velocidad:** 10 consultas por minuto. Requiere pausas entre peticiones.

---

## 6. Fuente de respaldo documental

**Tablas de Composición de Alimentos del INCMNSZ**, versión condensada 2015 (PDF, 666 páginas, ISBN 978-607-7797-19-7).

Es el antecedente directo de la BAM, del mismo grupo institucional. Se conserva como respaldo documental por si se detecta algún hueco específico, pero **no requiere extracción**: la BAM cubre el mismo terreno y ya viene en formato de datos.

---

## 7. Archivos del módulo

| Archivo | Qué hace |
|---|---|
| `alimentos.py` | Punto único de entrada. Aplica la jerarquía de fuentes |
| `marifer.py` | Búsqueda en la base propia de la nutrióloga (fuente principal) |
| `fndds.py` | Búsqueda en la versión local del FNDDS |
| `bam.py` | Búsqueda en la BAM local (respaldo) |
| `openfoodfacts.py` | Cliente de OpenFoodFacts, uso restringido |
| `usda.py` | Cliente de la API en línea del USDA. **Ya no se usa** — reemplazado por `fndds.py` |
| `datos/alimentos_marifer.json` | Los 2,916 alimentos de Marifer (v10, 26 campos) |
| `datos/alimentos_fndds.json` | Los 5,431 alimentos del FNDDS |
| `datos/alimentos_bam.json` | Los 2,045 alimentos de la BAM |
| `probar_openfoodfacts.py` | Diagnóstico de cobertura, para referencia |

**Funciones principales de `alimentos.py`:**
- `buscar_generico(termino, limite=10)` — Marifer primero, FNDDS si Marifer no tiene nada, BAM si ninguna de las dos anteriores tiene nada
- `buscar_marca(termino, limite=5)` — OpenFoodFacts, devuelve candidatos para elegir
- `buscar_todo(termino, limite=10)` — resultados agrupados por fuente (Marifer, FNDDS, BAM), para la pantalla de consulta manual
- `resumen_fuentes()` — estado de las cuatro fuentes, para diagnóstico

---

## 8. Verificación realizada

### Migración a la base v10 (21 de septiembre de 2026)

Se corrió `validar_tabla.py` en el servidor después del despliegue, y se comprobó que los archivos llegaron idénticos (hash SHA-256):

| Concepto | Resultado |
|---|---|
| Alimentos en la tabla de medidas | 164, más 7 sin aporte nutricional (café, tés, suplementos) |
| Verificables | 159 (cobertura 97 %) |
| Con problema | 5: aceite de aguacate, amaranto, pan de masa madre, salsa macha y vinagre de manzana. Ya estaban sin verificar antes de la migración |
| Prueba puntual | "pechuga de pollo", 1 pechuga → "Pechuga de pollo sin piel cocida", 34.8 g de proteína |

En la misma prueba con los mismos archivos, las 159 verificables se resolvieron así: 91 por Marifer, 26 por BAM y 42 por FNDDS (antes de la migración: 89, 28 y 42).

De las 293 medidas caseras que calcula el verificador, 262 dan el mismo resultado con la base nueva. Las que cambian:

| Alimento | Cambio | Motivo |
|---|---|---|
| Pechuga de pollo (1 pechuga, 120 g) | 28.0 → 34.8 g de proteína | Antes usaba valores de pechuga cruda con pesos de pechuga cocida |
| Aguacate (1/3) | 62 → 54 kcal | El valor por 100 g estaba a casi la mitad; los pesos de la tabla pasaron a pulpa (1/3 = 31 g) |
| Espinaca cruda y cocida | 16 → 7 kcal (1 taza cruda); 97 → 42 kcal (1 taza cocida) | La cruda usaba valores de espinaca cocida y la cocida tenía un valor por 100 g incorrecto |
| Espárragos, jícama | 40 a 50 % menos de energía | Valores por 100 g incorrectos en la base anterior |
| Zanahoria | Mismos valores, alimento correcto | Devolvía "Jugo de zanahoria" |
| Queso mozzarella (40 g) | 56 → 120 kcal; 12.7 → 8.9 g de proteína | Devolvía la versión "cero grasa" |

Pendiente conocido: "aguacate, 3 rebanadas" quedó en 45 g de pulpa (78 kcal); no hay fuente para ajustarlo y conviene que lo confirme la nutrióloga.

### Prueba del 30 de agosto de 2026 (jerarquía anterior, BAM como principal)

Prueba de jerarquía ejecutada en el servidor el 30 de agosto de 2026 (jerarquía anterior, BAM como principal):

| Búsqueda | Fuente usada | Resultado |
|---|---|---|
| nopal | BAM | NOPALES, 16 kcal |
| quinoa | USDA (la BAM no lo tiene) | Quinoa cooked, 120 kcal |
| salmon | BAM (sí lo tiene, tiene prioridad) | SALMON COCIDO, 156 kcal |

*Esta prueba quedó reemplazada por la del 21 de septiembre de 2026, con la jerarquía actual.*

---

## 9. Bitácora

| Fecha | Cambio |
|---|---|
| 2026-08-30 | v1.0. Se probó OpenFoodFacts como fuente principal y se descartó por baja precisión (3 de 20). Se adoptó la BAM como fuente principal y el USDA como fuente activa secundaria. OpenFoodFacts queda restringido a productos de marca con verificación humana |
| 2026-09-03 | Migración de fuente principal: Marifer (base propia de la nutrióloga, 2,342 alimentos) pasa a ser la fuente #1; BAM baja a respaldo |
| 2026-09-03 | Corrección de datos y búsqueda: se anulan valores erróneos detectados por validación cruzada; se mejora la detección de plurales en la búsqueda |
| 2026-09-03 | FNDDS local reemplaza a la API en línea del USDA como fuente #2; se corrigen 7 términos de búsqueda; se documentan 5 alimentos sin cobertura en ninguna fuente |
| 2026-09-04 | v2.0. Documento actualizado para reflejar la jerarquía real del código (estaba desactualizado desde la migración del 3 de septiembre) |
| 2026-09-21 | v3.0. Migración a la base v10 de Marifer: 2,916 alimentos (antes 2,342), 26 campos por alimento, micronutrientes en su columna correcta (la base anterior los tenía cruzados) y sin dato como `null`. `medidas_caseras.json` v2.2: se fijó `buscar_como` en fresas, pechuga de pollo, pollo desmenuzado y zanahoria, y el aguacate pasa a pesos de pulpa. Sin cambios de código. Verificado en el servidor con `validar_tabla.py` |
