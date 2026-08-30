# Fuentes de datos de alimentos

**Versión:** 1.0
**Fecha:** 30 de agosto de 2026
**Estado:** implementado y verificado en el servidor

---

## 1. Jerarquía de fuentes

El sistema consulta tres fuentes con prioridades distintas. La lógica vive en `alimentos.py`, que es el único punto de entrada para el resto del sistema.

| Prioridad | Fuente | Para qué | Tipo |
|---|---|---|---|
| 1 | **BAM 18.1.1** | Alimentos genéricos mexicanos | Archivo local |
| 2 | **USDA FoodData Central** | Alimentos genéricos no mexicanos | API |
| 3 | **OpenFoodFacts** | Solo productos de marca, con verificación humana | API |

---

## 2. BAM, Base de Alimentos de México

**Qué es:** proyecto conjunto del INCMNSZ y el INSP, con participación de la Universidad Iberoamericana y el CIAD. Es la base con la que el INSP estima el consumo dietético en sus estudios publicados, incluida la ENSANUT.

**Cobertura:** 2,045 alimentos con 19 campos nutricionales cada uno. Incluye preparaciones tradicionales mexicanas (tinga de pollo, cecina en jitomate, atole de frijol) y alimentos regionales (quelites, papaloquelite, tejocote, chinchayote, pulque) que ninguna otra fuente tiene.

**Formato:** archivo local `datos/alimentos_bam.json` (1.1 MB), convertido desde el Excel oficial. Sin API, sin límites de velocidad, sin dependencia de internet.

**Cita obligatoria:**
> Ramírez Silva, I.; Barragán-Vázquez, S.; Rodríguez Ramírez, S.; Rivera Dommarco, J.A.; Mejía-Rodríguez, F.; Barquera Cervera, S.; Tolentino Mayo, L.; Flores Aldana, M.; Villalpando Hernández, S.; Ancira Moreno, M.; et al. Base de Alimentos de México (BAM): Compilación de la Composición de los Alimentos Frecuentemente Consumidos en el país, Versión 18.1.1, 2021.

**Módulo:** `bam.py`. Búsqueda insensible a acentos y por palabras sueltas en cualquier orden.

---

## 3. USDA FoodData Central

**Qué es:** base de composición de alimentos del Departamento de Agricultura de Estados Unidos. Referencia mundial para alimentos genéricos.

**Para qué la usamos:** alimentos que la BAM no cubre bien, típicamente no mexicanos: quinoa, kale, pistaches, arándanos.

**Licencia:** dominio público (CC0). Uso comercial permitido sin restricciones.

**Acceso:** API key gratuita de api.data.gov. Límite de 1,000 consultas por hora por IP.

**Filtrado:** se consultan solo los conjuntos `Foundation` y `SR Legacy`, que son alimentos genéricos analizados en laboratorio. Se excluye `Branded` (productos de marca) porque para eso ya existe OpenFoodFacts.

**Módulo:** `usda.py`. La clave se lee de la variable de entorno `USDA_API_KEY`, definida en `.env`, **nunca en el repositorio**.

**Nota técnica:** los nutrientes se identifican por `nutrientId` y no por `nutrientNumber`, porque el endpoint de búsqueda devuelve la numeración antigua ("431") mientras que el de detalle usa la moderna ("1008"). El `nutrientId` es estable en ambos.

---

## 4. OpenFoodFacts, con restricciones

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

## 5. Fuente de respaldo documental

**Tablas de Composición de Alimentos del INCMNSZ**, versión condensada 2015 (PDF, 666 páginas, ISBN 978-607-7797-19-7).

Es el antecedente directo de la BAM, del mismo grupo institucional. Se conserva como respaldo documental por si se detecta algún hueco específico, pero **no requiere extracción**: la BAM cubre el mismo terreno y ya viene en formato de datos.

---

## 6. Archivos del módulo

| Archivo | Qué hace |
|---|---|
| `alimentos.py` | Punto único de entrada. Aplica la jerarquía de fuentes |
| `bam.py` | Búsqueda en la BAM local |
| `usda.py` | Cliente de la API del USDA |
| `openfoodfacts.py` | Cliente de OpenFoodFacts, uso restringido |
| `datos/alimentos_bam.json` | Los 2,045 alimentos de la BAM |
| `probar_openfoodfacts.py` | Diagnóstico de cobertura, para referencia |

**Funciones principales de `alimentos.py`:**
- `buscar_generico(termino)` — BAM primero, USDA si la BAM no tiene nada
- `buscar_marca(termino)` — OpenFoodFacts, devuelve candidatos para elegir
- `buscar_todo(termino)` — resultados agrupados por fuente, para la pantalla de consulta manual
- `resumen_fuentes()` — estado de las tres fuentes, para diagnóstico

---

## 7. Verificación realizada

Prueba de jerarquía ejecutada en el servidor el 30 de agosto de 2026:

| Búsqueda | Fuente usada | Resultado |
|---|---|---|
| nopal | BAM | NOPALES, 16 kcal |
| quinoa | USDA (la BAM no lo tiene) | Quinoa cooked, 120 kcal |
| salmon | BAM (sí lo tiene, tiene prioridad) | SALMON COCIDO, 156 kcal |

---

## 8. Bitácora

| Fecha | Cambio |
|---|---|
| 2026-08-30 | v1.0. Se probó OpenFoodFacts como fuente principal y se descartó por baja precisión (3 de 20). Se adoptó la BAM como fuente principal y el USDA como fuente activa secundaria. OpenFoodFacts queda restringido a productos de marca con verificación humana |
