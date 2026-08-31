# RESTORE_POINT_v1 — Sistema Nutrición

**Fecha:** 28 de agosto de 2026
**Estado:** Fase 0 completa. Fase 1 arrancada: esqueleto de la aplicación verificado de extremo a extremo en el droplet.

---

## 1. Qué existe ahora mismo

**Servidor:** droplet `sistema-nutricion` en DigitalOcean, Ubuntu 24.04, IP `165.22.7.251`.

**Contraseña root:** fue reseteada el 28 de agosto de 2026 (la original se perdió). La nueva contraseña la definió Michel al conectarse por primera vez tras el reset. **Recordatorio: guardarla en un lugar seguro que no se vuelva a perder** (gestor de contraseñas o carpeta dedicada, no un archivo suelto fácil de borrar).

**Ubicación del proyecto en el servidor:** `/opt/sistema-nutricion/`

**Entorno de Python:**
- Python 3.12.3 (el que trae Ubuntu 24.04 por defecto, decisión tomada sobre usar 3.14)
- Entorno virtual creado en `/opt/sistema-nutricion/venv`
- Se activa con: `source venv/bin/activate` (desde dentro de `/opt/sistema-nutricion`)

**Paquetes instalados** (ver `requirements.txt` en el repo para la lista exacta con versiones):
fastapi, uvicorn[standard], jinja2, python-multipart, y sus dependencias.

**Código actual:** `main.py` (85 líneas) con las rutas del primer módulo funcional:

| Ruta | Método | Qué hace |
|---|---|---|
| `/` | GET | Muestra el formulario de alta rápida |
| `/pacientes/nuevo` | GET | Mismo formulario, ruta alterna |
| `/pacientes/alta` | POST | Guarda el paciente y, si se llenó fecha, crea también la cita |
| `/pacientes` | GET | Lista todos los pacientes registrados, con nombres clicables |
| `/pacientes/{id}` | GET | Vista de expediente: datos de contacto, citas con su estado, y estado de la historia clínica |
| `/pacientes/{id}/historia` | GET | Formulario de historia clínica, precargado si ya existe |
| `/pacientes/{id}/historia` | POST | Guarda o actualiza la historia clínica y redirige al expediente |
| `/pacientes/{id}/citas/nueva` | POST | Agenda una cita nueva (detecta solo si es primera consulta o seguimiento) |
| `/citas/{id}/estado` | POST | Cambia el estado de una cita: confirmada, cancelada, completada, no_asistio |
| `/citas/{id}/reagendar` | POST | Marca la cita como cancelada y crea una nueva con la fecha nueva, conservando el registro |
| `/pacientes/{id}/followup/nuevo` | GET | Formulario de consulta de seguimiento, con recordatorio de la consulta anterior y número autoasignado |
| `/pacientes/{id}/followup` | POST | Guarda la consulta, crea la medición si se llenó, y agenda la próxima cita si se indicó fecha |

**Plantillas en `templates/`:** `alta_rapida.html` (123 líneas, formulario de alta con secciones de datos del paciente y agendar cita), `lista_pacientes.html` (57 líneas, tabla con nombres enlazados al expediente), `expediente.html` (215 líneas, vista de expediente que combina datos de cuatro tablas distintas en una sola pantalla, incluye gestión completa de citas e historial de consultas) e `historia_clinica.html` (323 líneas, formulario de 10 secciones en página única con botón de guardar fijo) y `follow_up.html` (166 líneas, formulario de consulta de seguimiento con recordatorio de la consulta previa). Todas usan Tailwind vía CDN y la paleta verde de la marca.

**Automatizaciones del follow-up:**
- El número de consulta se asigna solo (última consulta + 1), nunca se teclea
- Si se llenan campos de medición, se crea un registro en `mediciones_inbody` con `origen="manual"` y queda enlazado al follow-up
- Si se indica fecha de próxima cita, se agenda automáticamente una cita nueva con nota "Agendada desde la consulta N"
- Al abrir una consulta nueva se muestran los ajustes acordados y el punto de mejora de la consulta anterior. Resuelve la necesidad planteada por la nutrióloga de "poder retomar la conversación en la siguiente consulta"

**Decisión de diseño del formulario de historia clínica:** página única con scroll, no pestañas ni paso a paso. Razón: la nutrióloga lo llena durante la consulta, hablando con el paciente, sin seguir un orden estricto. Con página única puede saltar entre secciones sin perder el hilo de la conversación. El botón de guardar es fijo en la parte inferior, siempre accesible.

**Nota técnica:** la ruta que guarda la historia clínica lee el formulario completo con `await request.form()` en lugar de declarar 50 parámetros `Form(...)` uno por uno. Los nombres de campo se recorren desde la lista `CAMPOS_HISTORIA` en `main.py`, lo que hace trivial agregar campos nuevos en el futuro: basta agregarlos a esa lista y a la plantilla.

**Nota de diseño validada en la práctica:** el expediente demuestra el principio de "separados por dentro, juntos cuando hace falta verlos". Los datos del paciente, sus citas y el estado de su historia clínica viven en tablas distintas, pero se presentan unificados en una sola vista continua.

**Verificado de extremo a extremo (29 ago 2026):** se dio de alta un paciente de prueba con cita agendada, apareció el mensaje de confirmación, y el registro se muestra correctamente en la lista de pacientes. Ciclo completo capturar → guardar → consultar funcionando.

**Nota técnica importante:** las versiones actuales de FastAPI cambiaron la sintaxis de `TemplateResponse`. La forma correcta es `templates.TemplateResponse(request, "archivo.html", {...})`, con el `request` como primer argumento. La forma antigua (`TemplateResponse("archivo.html", {"request": request, ...})`) produce el error `TypeError: unhashable type: 'dict'`.

**Cómo se ejecuta (desde el 29 ago 2026): como servicio permanente de systemd.**

La aplicación corre sola, arranca automáticamente cuando el servidor enciende, y sobrevive al cierre de la sesión SSH. Verificado cerrando la terminal y confirmando que el sitio sigue respondiendo.

Archivo del servicio: `/etc/systemd/system/sistema-nutricion.service`

```
[Unit]
Description=Sistema de Nutricion Marifer Utrilla
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/sistema-nutricion
Environment="PATH=/opt/sistema-nutricion/venv/bin"
ExecStart=/opt/sistema-nutricion/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Comandos de operación del día a día:**

| Para | Comando |
|---|---|
| Reiniciar tras editar código (obligatorio, ya no hay `--reload`) | `systemctl restart sistema-nutricion` |
| Ver si está corriendo | `systemctl status sistema-nutricion` |
| Ver errores y registros recientes | `journalctl -u sistema-nutricion -n 50` |
| Detenerlo | `systemctl stop sistema-nutricion` |
| Encenderlo | `systemctl start sistema-nutricion` |

**Cambio de flujo importante:** durante el desarrollo inicial se usaba `uvicorn main:app --host 0.0.0.0 --reload` en primer plano, que recargaba solo al guardar cambios. Con el servicio, cada cambio de código requiere reiniciar manualmente con `systemctl restart sistema-nutricion`.

**Nota de seguridad esperada:** el navegador muestra "Not secure" porque se accede por `http://` directo a la IP, sin certificado SSL. Es normal en esta etapa; el certificado se instala en la Fase 5, cuando se conecte el dominio `mafernut.com` a la aplicación real.

---

## 2. Cómo retomar desde cero si hace falta

**Nota de flujo de trabajo, aprendida en la práctica (29 ago 2026):** pegar bloques largos de código directamente en la terminal SSH **no es confiable**, PowerShell corta el pegado a media línea y corrompe el archivo (ocurrió dos veces con `models.py`). Métodos que sí funcionan:

1. **`nano` (probado y confiable):** `nano -i archivo.py`, pegar con clic derecho o Ctrl+Shift+V, guardar con Ctrl+O y Enter, salir con Ctrl+X. La bandera `-i` desactiva el auto-indentado, que arruinaría el código de Python. Nano confirma abajo cuántas líneas escribió, lo que sirve de verificación inmediata
2. **Vía GitHub (preferido a futuro):** subir el archivo al repo desde la computadora (donde copiar y pegar funciona sin límites) y hacer que el servidor lo descargue. Pendiente de configurar la autenticación del repo privado en el servidor

Siempre verificar después de escribir un archivo con `wc -l archivo.py` y comparar contra el número esperado.

Si el droplet se pierde o se necesita reconstruir el entorno desde cero:

```
apt update && apt upgrade -y
apt install python3-pip python3-venv git -y
mkdir -p /opt/sistema-nutricion
cd /opt/sistema-nutricion
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
(El `requirements.txt` vive en el repo de GitHub, en la raíz del proyecto.)

---

## 3. Checklist completo del proyecto

### Fase 0 — Cimientos y decisiones ✅ COMPLETA
- [x] Stack decidido: Python, FastAPI, HTML+Tailwind+HTMX, SQLite
- [x] Motor de IA: Gemini (análisis) + Claude (redacción)
- [x] Droplet DigitalOcean creado y funcionando
- [x] Dominio `mafernut.com` (Cloudflare) apuntando al droplet
- [x] Correo `contacto@mafernut.com` (Hostinger) con MX/SPF/DKIM/DMARC verificados
- [x] Repo de GitHub privado con `.gitignore`
- [x] API keys de Gemini y Anthropic obtenidas
- [x] Identidad de marca: logo, colores, tagline confirmados
- [x] Guía de estilo (`GUIA_DE_ESTILO.md` / `STYLE_SPEC.md`), a partir de 22 documentos reales
- [x] Historia Clínica rediseñada y aprobada (11 secciones)
- [x] Follow-up diseñado y aprobado
- [x] Knowledgebase clínica: 17 fuentes evaluadas, con criterio de autoridad documentado
- [x] Tabla de Equivalencias Nutrimentales propia (reemplaza el SMAE, evita infracción de derechos de autor)
- [x] Aviso de Privacidad (LFPDPPP 2025), borrador completo

### Fase 1 — Base de datos y plantillas 🔵 EN CURSO
- [x] Python 3.12 confirmado en el droplet
- [x] Entorno virtual creado y funcionando
- [x] FastAPI + Uvicorn + Jinja2 + python-multipart instalados
- [x] Primer `main.py` mínimo, verificado de extremo a extremo desde el navegador
- [x] Diseño y creación de la base de datos SQLite: 8 tablas (`pacientes`, `historias_clinicas`, `mediciones_inbody`, `ids_inbody_conocidos`, `follow_ups`, `dietas_versiones`, `opciones_prescritas`, `laboratorios`), definidas en `models.py` con SQLAlchemy, creadas físicamente en `sistema_nutricion.db` vía `init_db.py`, verificadas con `sqlite3 .tables`
- [x] Novena tabla `citas` creada (agendar sin requerir Historia Clínica completa, campo `google_event_id` preparado para sincronización futura con Google Calendar, ver `docs/PROJECT_PLAN.md` Fase 1). `models.py` ahora tiene 211 líneas y 9 tablas
- [x] Formulario de alta rápida (datos básicos del paciente + agendar cita), funcionando y verificado
- [x] Lista de pacientes, funcionando
- [x] Vista de expediente del paciente (datos de contacto, citas con estado, estado de historia clínica), funcionando
- [x] Gestión de citas desde el expediente: agendar nueva, reagendar (cancela la anterior y crea nueva, dejando registro visible), cancelar, marcar completada, marcar no asistió. Verificado
- [x] Módulo de follow-up (consultas de seguimiento) con número autoasignado, registro de medición, agendado automático de próxima cita, y recordatorio de la consulta anterior. Verificado
- [x] Formulario completo de Historia Clínica (10 secciones, guardar y editar), funcionando y verificado
- [ ] Formulario digital de intake (basado en `Historia_Clinica_v2.docx`)
- [ ] Formulario digital de follow-up (basado en `Follow_Up_v1.docx`)
- [ ] Mecanismo de identificación de InBody en 3 capas (búsqueda por lista, pantalla de comparación, lista de IDs por paciente)
- [ ] Historial de versiones de dietas (nunca sobreescribir)
- [ ] Registro de opciones ya prescritas por paciente
- [x] Servidor convertido en servicio permanente de systemd (arranca solo, sobrevive al cierre de SSH, se reinicia solo si falla)

### Fase 2 — Knowledgebase y base de alimentos ⬜ PENDIENTE
- [ ] Conexión real a la API de OpenFoodFacts
- [ ] Construcción del archivo `tabla_equivalencias.json` con alimentos mexicanos reales (diseño ya aprobado en `TABLA_DE_EQUIVALENCIAS.md`)
- [ ] Carga de la Knowledgebase clínica al sistema, para que Gemini la consuma
- [ ] Uso de la cuenta de OpenFoodFacts de Michel para contribuir alimentos mexicanos faltantes

### Fase 3 — Motor de IA ⬜ PENDIENTE
- [ ] Integración de la API de Gemini (análisis)
- [ ] Integración de la API de Claude (redacción)
- [ ] Inyección de `STYLE_SPEC.md` en el prompt de redacción
- [ ] Resumen pre-consulta automático
- [ ] Lógica de banderas clínicas
- [ ] Análisis de estudios de laboratorio subidos (advertencias, nunca diagnóstico)
- [ ] Lectura de InBody vía PDF nativo con reintento automático

### Fase 4 — Aprobación, PDF y envío ⬜ PENDIENTE
- [ ] Flujo de un clic: revisar, aprobar, generar, enviar
- [ ] Botón "Modificar propuesta"
- [ ] Motor de maquetación de flujo (la caja se ajusta al texto)
- [ ] Gráficas de progreso
- [ ] Carta al médico referente
- [ ] Módulo de acciones de salida: correo, descarga, WhatsApp por enlace

### Fase 5 — Plataforma pulida ⬜ PENDIENTE
- [ ] Certificado SSL sobre `mafernut.com`
- [ ] Interfaz unificada, tablet-first
- [ ] Respaldo diario cifrado a Google Drive

### Fase 6 — Portal del paciente y pagos ⬜ PENDIENTE (opcional, se decide al llegar)
- [ ] Acceso web del paciente
- [ ] Pagos en línea

### Pendientes administrativos, en paralelo
- [ ] Revisión del Aviso de Privacidad por un abogado especializado
- [ ] Formato específico de solicitud ARCO (separado del aviso)
- [ ] Confirmar guardado seguro de la nueva contraseña del droplet

**Archivos de la base de datos, en `/opt/sistema-nutricion/`:**
- `database.py` — conexión a SQLite vía SQLAlchemy
- `models.py` — las 8 tablas (195 líneas)
- `init_db.py` — script que crea las tablas físicas, ya ejecutado
- `sistema_nutricion.db` — el archivo de base de datos real, ya creado con las 8 tablas dentro

**Herramienta instalada:** `sqlite3` (cliente de línea de comandos, útil para inspeccionar la base de datos directamente: `sqlite3 sistema_nutricion.db ".tables"`)

---


**Módulo de alimentos (Fase 2), agregado el 30 ago 2026:**

Archivos en `/opt/sistema-nutricion/`: `alimentos.py` (orquestador, 109 líneas), `bam.py` (118), `usda.py` (119), `openfoodfacts.py` (112), `probar_openfoodfacts.py` (102, diagnóstico) y `datos/alimentos_bam.json` (1.1 MB, 2045 alimentos).

Arquitectura de tres fuentes con jerarquía, detallada en `docs/FUENTES_ALIMENTOS.md`: BAM local para alimentos mexicanos, USDA para genéricos internacionales, OpenFoodFacts restringido a productos de marca con verificación humana.

**Sistema de login, agregado el 1 sep 2026:**

`auth.py` (72 líneas, hash PBKDF2 sin dependencias externas) más middleware de sesión en `main.py`. Requiere `itsdangerous` instalado (`pip install itsdangerous`).

**Variables nuevas en `.env`:** `SESSION_SECRET_KEY` y `MARIFER_PASSWORD_HASH`. Ninguna de las dos se generó ni compartió por chat.

**Para cambiar la contraseña:** `python auth.py` en el servidor, pega el hash resultante en `.env`, reinicia el servicio.

**ADVERTENCIA sobre orden de middleware en Starlette:** el último middleware agregado con `app.add_middleware()` es el que se ejecuta PRIMERO en cada petición. `SessionMiddleware` debe agregarse DESPUÉS de `RequiereLoginMiddleware` en el código, para quedar como capa más externa y preparar la sesión antes de que el middleware de login la lea. El orden inverso produce `AssertionError: SessionMiddleware must be installed`.

**Pantalla de revisión y aprobación, agregada el 31 ago 2026:**

`templates/ver_dieta.html` (114 líneas) y rutas nuevas en `main.py`: `/pacientes/{id}/dieta/nueva`, `/pacientes/{id}/dieta/{id}` (ver), `/pacientes/{id}/dieta/{id}/aprobar`, `/pacientes/{id}/dieta/{id}/ajustar`, `/pacientes/{id}/dieta/{id}/pdf`.

**HALLAZGO CRÍTICO DE INFRAESTRUCTURA, corregido:** el servicio de systemd no leía `.env`. Las tres claves de API (USDA, Gemini, Anthropic) solo funcionaban cuando se probaban a mano en la terminal con `export $(cat .env | xargs)`, pero la aplicación real, corriendo como servicio, nunca tuvo acceso a ellas. Se descubrió al dar el primer clic real en "Generar con IA" desde el navegador.

**Corrección aplicada** en `/etc/systemd/system/sistema-nutricion.service`, se agregó bajo `WorkingDirectory`:
```
EnvironmentFile=/opt/sistema-nutricion/.env
```
Luego `systemctl daemon-reload` y `systemctl restart sistema-nutricion`.

**Advertencia para quien retome:** si en el futuro se agrega una clave nueva al `.env`, esta corrección ya la va a recoger sola en el próximo restart, no hace falta tocar el archivo de servicio de nuevo.

**Pendiente menor sin resolver:** en una prueba se generaron 4 versiones de dieta en vez de 3 para el mismo paciente. Posible causa: recargar la URL del borrador dispara `/dieta/nueva` de nuevo. Revisar si conviene separar "crear" de "ver" de forma más estricta.

**Generador de PDF, agregado el 31 ago 2026 (Fase 4):**

`pdf.py` (200 líneas) y `templates/plan_pdf.html` (249 líneas). Motor: WeasyPrint.

**Dependencias del sistema instaladas:**
```
apt install -y libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi-dev
pip install weasyprint
```

**Logo:** `assets/logo/logo_marifer.svg`. **Usar el SVG, no los PNG.** Los PNG dan mala calidad y `Mafer_Logo_Grande.png` además trae el tagline antiguo "Nutrición y Vida en Equilibrio".

**Prueba rápida de diseño sin gastar llamadas a las IA:**
```
python -c "
import pdf, json
doc = json.load(open('/tmp/doc_prueba.json'))
print(pdf.generar(doc, 'Ana López', proxima_cita='15 de septiembre de 2026'))
"
```
`/tmp/doc_prueba.json` guarda un documento ya redactado, así que regenerar la lámina es instantáneo. Si se pierde, se recrea corriendo el flujo completo una vez.

**Bajar un PDF a la PC:**
```
scp root@165.22.7.251:"/opt/sistema-nutricion/pdfs/ARCHIVO.pdf" E:\Descargas\
```

**Capa de redacción con Claude, agregada el 31 ago 2026:**

`claude_api.py` (174 líneas) y `redactor.py` (216 líneas). Modelo: `claude-sonnet-4-5`.

**Variable de entorno nueva:** `ANTHROPIC_API_KEY` en `.env`, junto a `USDA_API_KEY` y `GEMINI_API_KEY`.

**Archivo nuevo:** `datos/estilo/STYLE_SPEC.md` (195 líneas), el contrato de estilo derivado de los 24 documentos reales de Marifer. Se inyecta en el campo `system` de la API.

**Prueba rápida:**
```
python -c "import claude_api, json; print(json.dumps(claude_api.probar_conexion(), indent=2))"
```

**Cadena completa funcionando:** Gemini analiza, el sistema verifica, Claude redacta.

**Verificación nutricional, agregada el 31 ago 2026:**

`verificador.py` (406 líneas) y `validar_tabla.py` (123 líneas).

**Qué hace:** calcula la proteína real de cada opción desde la BAM y el USDA, y sobrescribe el número que estimó la IA. Los modelos no son confiables sumando.

**Comando útil tras cualquier cambio a la tabla de medidas:**
```
python validar_tabla.py
```
Prueba los 171 alimentos contra las fuentes reales. Debe dar 100% de cobertura.

**Advertencia para quien retome:** al registrar un término en `buscar_como`, verificarlo primero con `bam.buscar_palabras()`. Se registraron cinco términos inventados que no existían y dejaban alimentos sin verificar en silencio.

**Capa de análisis con Gemini, agregada el 30 ago 2026 (Fase 3):**

`gemini.py` (174 líneas, cliente de la API) y `plan_generador.py` (296 líneas, generador de planes técnicos).

**Modelo en uso: `gemini-3.7-flash`.** Importante: la generación 2.5 de Gemini se descontinúa el 16 de octubre de 2026, no usarla. Si el modelo deja de funcionar, correr `gemini.listar_modelos()` para ver qué hay disponible con la clave actual y ajustar la constante `MODELO_ANALISIS` en `gemini.py`.

**Variable de entorno nueva:** `GEMINI_API_KEY` en `.env`, junto a `USDA_API_KEY`.

**Prueba rápida de que todo funciona:**
```
python -c "import gemini, json; print(json.dumps(gemini.probar_conexion(), indent=2))"
```

Verificado con un caso de SOP con resistencia a la insulina: 44 segundos, prompt de 285 KB, plan técnico completo y coherente. Detalle en `docs/PROJECT_PLAN.md` Fase 3.

**Knowledgebase clínica, cargada el 30 ago 2026:**

19 archivos de extracciones de libros y guías clínicas en `datos/knowledgebase/` (1.4 MB), indexados en `datos/kb_indice.json` y accesibles vía `knowledgebase.py` (152 líneas).

El índice clasifica cada fuente por tema clínico y nivel de autoridad, de modo que el sistema entrega solo las relevantes al caso. Verificado: SOP más resistencia a la insulina devuelve 4 fuentes de 19, con 338 KB de contexto.

**Con esto la Fase 2 queda completa.** El sistema tiene las cuatro capas de conocimiento listas para la Fase 3: fuentes de alimentos (BAM, USDA, OFF), reglas clínicas de Marifer, conversión de medidas caseras, y knowledgebase clínica.

**Conversión de medidas caseras, agregado el 30 ago 2026:**

`medidas.py` (246 líneas) más `datos/medidas_caseras.json` (62 alimentos). Traduce entre las medidas de Marifer y los gramos de la BAM.

**Advertencia importante para quien retome:** los alimentos cambian su densidad al cocerse. Siempre usar `medidas.buscar_en_bam(alimento, bam)` en lugar de `bam.buscar_palabras()` directo, porque la primera aplica el campo `buscar_como` que evita tomar el alimento crudo cuando debe ser cocido. Detalle en `docs/MEDIDAS_CASERAS.md`.

**Motor de reglas clínicas, agregado el 30 ago 2026:**

`reglas.py` (179 líneas) más `datos/reglas_clinicas.json`. Codifica los criterios de prescripción de Marifer, recabados directamente de ella. Los números viven en el JSON, editable sin tocar código.

Verificado con dos casos: paciente de 85 kg con GLP-1 (objetivo 105 g, detectó que excede 30 g por comida y sugirió colación proteica) y paciente de 48 kg sin GLP-1 (aplicó el piso no negociable de 60 g). Detalle en `docs/REGLAS_CLINICAS.md`.

**Variable de entorno nueva:** `USDA_API_KEY` en el archivo `.env` (permisos 600). Para usarla en la terminal: `export $(cat .env | xargs)`.

---

## 4. Bitácora de este punto de restauración

| Fecha | Evento |
|---|---|
| 2026-08-28 | Se pierde la contraseña original del droplet; reseteada exitosamente vía panel de DigitalOcean |
| 2026-08-28 | Servidor actualizado (`apt update && apt upgrade`), Python 3.12.3 confirmado |
| 2026-08-28 | Entorno virtual creado, FastAPI y dependencias instaladas |
| 2026-08-28 | Primer `main.py` de prueba, verificado funcionando desde navegador externo (`http://165.22.7.251:8000`) |
| 2026-08-29 | Base de datos SQLite creada: 8 tablas definidas en `models.py`, generadas físicamente vía `init_db.py`, verificadas con `sqlite3` |
| 2026-08-29 | Novena tabla `citas` agregada (211 líneas en `models.py`, 9 tablas en total). Se descubre que pegar código largo por SSH corrompe archivos; se adopta `nano -i` como método confiable, documentado en la sección 2 |
| 2026-08-29 | Primer módulo funcional completo: formulario de alta rápida de paciente con agendado de cita, más lista de pacientes. Verificado de extremo a extremo con un registro de prueba. Se corrige la sintaxis de `TemplateResponse` para FastAPI moderno |
| 2026-08-29 | Aplicación convertida en servicio permanente de systemd (`sistema-nutricion.service`). Arranca automáticamente con el servidor, sobrevive al cierre de SSH, se reinicia solo si falla. Verificado cerrando la terminal. Nuevo flujo: cada cambio de código requiere `systemctl restart sistema-nutricion` |
| 2026-08-29 | Vista de expediente del paciente construida y verificada. Combina en una sola pantalla los datos del paciente, sus citas (con etiqueta de estado por color) y el estado de su historia clínica, leyendo de tres tablas distintas |
| 2026-08-29 | Formulario de Historia Clínica completo (10 secciones, ~50 campos) construido y verificado: guardar, redirigir al expediente, y editar recuperando los datos. **El sistema ya es utilizable en la vida real** para dar de alta pacientes, agendar citas y capturar historias clínicas |
| 2026-08-29 | Gestión de citas completa desde el expediente: agendar, reagendar, cancelar, marcar completada o no asistió. El reagendado cancela la cita anterior y crea una nueva, dejando el rastro visible (cita anterior tachada con etiqueta "cancelada"), conforme a la política acordada de no sobreescribir nada |
| 2026-09-01 | Sistema de login implementado y verificado. Cierra el hueco de seguridad de acceso sin contraseña |
| 2026-08-31 | Pantalla de revisión y aprobación funcionando end-to-end. Se corrige que systemd no leía .env, un hallazgo que afectaba a la aplicación en producción desde que se agregaron las claves |
| 2026-08-31 | Generador de PDF funcionando con la identidad visual de la marca. Fase 4 arrancada |
| 2026-08-31 | Capa de redacción con Claude funcionando. Fase 3 funcionalmente completa |
| 2026-08-31 | Verificación nutricional implementada. El sistema calcula la proteína real y corrige lo que estima la IA. Tabla ampliada a 171 alimentos con 100% de cobertura |
| 2026-08-30 | **Fase 3 arrancada**: capa de análisis con Gemini funcionando, primer plan técnico generado y verificado |
| 2026-08-30 | Knowledgebase clínica cargada e indexada. **Fase 2 completa** |
| 2026-08-30 | Tabla de conversión de medidas caseras implementada. Se detectaron dos errores silenciosos de cálculo (arroz crudo contra cocido, pollo con piel contra sin piel) y se resolvieron con el campo `buscar_como` |
| 2026-08-30 | Motor de reglas clínicas implementado y verificado. Los criterios de prescripción de la nutrióloga quedan codificados y editables sin tocar código |
| 2026-08-30 | Arquitectura de fuentes de alimentos implementada y verificada: BAM (local, 2045 alimentos mexicanos), USDA (API, dominio público) y OpenFoodFacts (restringido a marcas). Se descartó OpenFoodFacts como fuente principal tras medir su precisión: 3 de 20 |
| 2026-08-30 | Módulo de follow-up terminado y verificado. Incluye tres automatizaciones: número de consulta autoasignado, creación del registro de medición si se llenan esos campos, y agendado automático de la próxima cita. Al abrir una consulta nueva muestra los ajustes acordados y el punto de mejora de la anterior |
