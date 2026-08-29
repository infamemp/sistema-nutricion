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

**Código actual:** `main.py`, una aplicación mínima de prueba:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def inicio():
    return {"mensaje": "El sistema de Marifer está funcionando"}
```

**Verificado:** accesible desde un navegador externo en `http://165.22.7.251:8000`, mostrando el mensaje de prueba correctamente. Confirma que la cadena completa funciona: servidor, Python, FastAPI, firewall, y acceso externo.

**Cómo se ejecuta hoy** (modo de desarrollo, manual, no automático):
```
cd /opt/sistema-nutricion
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --reload
```
Esto corre en primer plano en la terminal SSH. Si se cierra la sesión de SSH, el servidor se detiene. Convertirlo en un servicio permanente (que siga corriendo solo) es trabajo pendiente, ver checklist.

**Nota de seguridad esperada:** el navegador muestra "Not secure" porque se accede por `http://` directo a la IP, sin certificado SSL. Es normal en esta etapa; el certificado se instala en la Fase 5, cuando se conecte el dominio `mafernut.com` a la aplicación real.

---

## 2. Cómo retomar desde cero si hace falta

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
- [ ] Diseño de la base de datos SQLite (tablas: pacientes, historia clínica, mediciones de InBody, follow-ups, versiones de dietas)
- [ ] Formulario digital de intake (basado en `Historia_Clinica_v2.docx`)
- [ ] Formulario digital de follow-up (basado en `Follow_Up_v1.docx`)
- [ ] Mecanismo de identificación de InBody en 3 capas (búsqueda por lista, pantalla de comparación, lista de IDs por paciente)
- [ ] Historial de versiones de dietas (nunca sobreescribir)
- [ ] Registro de opciones ya prescritas por paciente
- [ ] Convertir el servidor de prueba en un servicio permanente (hoy se detiene si se cierra la sesión SSH)

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

---

## 4. Bitácora de este punto de restauración

| Fecha | Evento |
|---|---|
| 2026-08-28 | Se pierde la contraseña original del droplet; reseteada exitosamente vía panel de DigitalOcean |
| 2026-08-28 | Servidor actualizado (`apt update && apt upgrade`), Python 3.12.3 confirmado |
| 2026-08-28 | Entorno virtual creado, FastAPI y dependencias instaladas |
| 2026-08-28 | Primer `main.py` de prueba, verificado funcionando desde navegador externo (`http://165.22.7.251:8000`) |
