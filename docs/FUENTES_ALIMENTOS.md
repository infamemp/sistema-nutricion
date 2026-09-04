# Fuentes de datos de alimentos

**Versión:** 2.0
**Fecha:** 4 de septiembre de 2026
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

**Qué es:** base de equivalencias propia de la nutrióloga, clasificada según el Sistema Mexicano de Alimentos Equivalentes (SMAE). Cada alimento trae su grupo real (AOAMBG, CerealesSG, Frutas, etc.), su porción casera típica, y sus valores nutricionales por 100 g de porción neta para poder escalar a cualquier cantidad.

**Cobertura:** 2,342 alimentos, sin internet, sin límites de velocidad.

**Nota de calidad:** el campo `hierro_mg` viene anulado (`None`) en aproximadamente 967 alimentos porque el dato original tenía errores de captura (valores fisiológicamente imposibles). Cualquier campo en `None` significa "sin dato confiable", nunca cero.

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
| `datos/alimentos_marifer.json` | Los 2,342 alimentos de Marifer |
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

Prueba de jerarquía ejecutada en el servidor el 30 de agosto de 2026 (jerarquía anterior, BAM como principal):

| Búsqueda | Fuente usada | Resultado |
|---|---|---|
| nopal | BAM | NOPALES, 16 kcal |
| quinoa | USDA (la BAM no lo tiene) | Quinoa cooked, 120 kcal |
| salmon | BAM (sí lo tiene, tiene prioridad) | SALMON COCIDO, 156 kcal |

*Pendiente: repetir esta prueba con la jerarquía actual (Marifer → FNDDS → BAM) para tener una verificación vigente.*

---

## 9. Bitácora

| Fecha | Cambio |
|---|---|
| 2026-08-30 | v1.0. Se probó OpenFoodFacts como fuente principal y se descartó por baja precisión (3 de 20). Se adoptó la BAM como fuente principal y el USDA como fuente activa secundaria. OpenFoodFacts queda restringido a productos de marca con verificación humana |
| 2026-09-03 | Migración de fuente principal: Marifer (base propia de la nutrióloga, 2,342 alimentos) pasa a ser la fuente #1; BAM baja a respaldo |
| 2026-09-03 | Corrección de datos y búsqueda: se anulan valores erróneos detectados por validación cruzada; se mejora la detección de plurales en la búsqueda |
| 2026-09-03 | FNDDS local reemplaza a la API en línea del USDA como fuente #2; se corrigen 7 términos de búsqueda; se documentan 5 alimentos sin cobertura en ninguna fuente |
| 2026-09-04 | v2.0. Documento actualizado para reflejar la jerarquía real del código (estaba desactualizado desde la migración del 3 de septiembre) |
