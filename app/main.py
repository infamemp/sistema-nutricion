import json
import os
from fastapi import FastAPI, Request, Form, Depends, HTTPException, File, UploadFile
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import Optional

from database import get_db, engine
import models
import auth
import correo
import calendario
import inbody
import laboratorio
import plan_generador as plan_gen
import redactor
import pdf as pdf_gen

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

RUTAS_PUBLICAS = {"/login", "/olvide-password", "/restablecer-password"}


class RequiereLoginMiddleware(BaseHTTPMiddleware):
    """
    Bloquea toda la aplicacion salvo /login hasta que la sesion tenga
    la marca de autenticado. Es deliberadamente simple: un solo
    operador, una sola contraseña, sin roles ni permisos distintos.
    """
    async def dispatch(self, request: Request, call_next):
        if request.url.path in RUTAS_PUBLICAS or request.url.path.startswith("/static/"):
            return await call_next(request)

        if not request.session.get("autenticado"):
            return RedirectResponse(url="/login", status_code=303)

        return await call_next(request)


app.add_middleware(RequiereLoginMiddleware)

# SessionMiddleware va AL FINAL a proposito: en Starlette, el ultimo
# middleware agregado con add_middleware() es el que se ejecuta PRIMERO
# en cada peticion. Debe preparar la sesion antes de que
# RequiereLoginMiddleware intente leerla. Este orden ya causo el mismo
# error tres veces al reescribir este archivo sin conservarlo. NO MOVER.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SESSION_SECRET_KEY"],
    max_age=60 * 60 * 12,  # 12 horas
)


@app.get("/login", response_class=HTMLResponse)
def formulario_login(request: Request):
    if request.session.get("autenticado"):
        return RedirectResponse(url="/pacientes", status_code=303)
    return templates.TemplateResponse(request, "login.html")


@app.post("/login", response_class=HTMLResponse)
def procesar_login(request: Request, password: str = Form(...)):
    hash_guardado = os.environ.get("MARIFER_PASSWORD_HASH")

    if not hash_guardado:
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "El sistema no tiene una contraseña configurada. Revisa el archivo .env."},
        )

    if auth.verificar_password(password, hash_guardado):
        request.session["autenticado"] = True
        return RedirectResponse(url="/pacientes", status_code=303)

    return templates.TemplateResponse(
        request, "login.html", {"error": "Contraseña incorrecta."}
    )


@app.get("/logout")
def cerrar_sesion(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@app.get("/olvide-password", response_class=HTMLResponse)
def formulario_olvide(request: Request):
    return templates.TemplateResponse(request, "olvide_password.html")


@app.post("/olvide-password", response_class=HTMLResponse)
def procesar_olvide(request: Request):
    from itsdangerous import URLSafeTimedSerializer

    serializador = URLSafeTimedSerializer(os.environ["SESSION_SECRET_KEY"])
    token = serializador.dumps("recuperar_password")

    enlace = str(request.base_url) + "restablecer-password?token=" + token

    try:
        correo.enviar_recuperacion(os.environ["CORREO_RECUPERACION"], enlace)
        mensaje = "Se envio un enlace de recuperacion. Revisa el correo (y spam) en los proximos minutos."
    except Exception as e:
        mensaje = "No se pudo enviar el correo: " + str(e)[:200]

    return templates.TemplateResponse(request, "olvide_password.html", {"mensaje": mensaje})


@app.get("/restablecer-password", response_class=HTMLResponse)
def formulario_restablecer(request: Request, token: str):
    from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

    serializador = URLSafeTimedSerializer(os.environ["SESSION_SECRET_KEY"])
    try:
        serializador.loads(token, max_age=1800)  # 30 minutos
    except SignatureExpired:
        return templates.TemplateResponse(
            request, "olvide_password.html",
            {"mensaje": "Ese enlace ya expiro. Solicita uno nuevo."},
        )
    except BadSignature:
        raise HTTPException(status_code=400, detail="Enlace invalido")

    return templates.TemplateResponse(request, "restablecer_password.html", {"token": token})


@app.post("/restablecer-password", response_class=HTMLResponse)
def procesar_restablecer(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    password_confirmar: str = Form(...),
):
    from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

    serializador = URLSafeTimedSerializer(os.environ["SESSION_SECRET_KEY"])
    try:
        serializador.loads(token, max_age=1800)
    except (SignatureExpired, BadSignature):
        raise HTTPException(status_code=400, detail="Enlace invalido o expirado")

    if password != password_confirmar:
        return templates.TemplateResponse(
            request, "restablecer_password.html",
            {"token": token, "error": "Las contraseñas no coinciden."},
        )

    if len(password) < 8:
        return templates.TemplateResponse(
            request, "restablecer_password.html",
            {"token": token, "error": "Usa al menos 8 caracteres."},
        )

    nuevo_hash = auth.generar_hash(password)

    ruta_env = os.path.join(os.path.dirname(__file__), ".env")
    with open(ruta_env) as f:
        lineas = f.readlines()

    reemplazado = False
    for i, linea in enumerate(lineas):
        if linea.startswith("MARIFER_PASSWORD_HASH="):
            lineas[i] = "MARIFER_PASSWORD_HASH=" + nuevo_hash + "\n"
            reemplazado = True
            break
    if not reemplazado:
        lineas.append("MARIFER_PASSWORD_HASH=" + nuevo_hash + "\n")

    with open(ruta_env, "w") as f:
        f.writelines(lineas)

    os.environ["MARIFER_PASSWORD_HASH"] = nuevo_hash

    return templates.TemplateResponse(
        request, "login.html",
        {"error": None, "mensaje": "Contraseña actualizada. Ya puedes iniciar sesion."},
    )


def obtener_paciente(db: Session, paciente_id: int):
    paciente = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return paciente


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    return templates.TemplateResponse(request, "alta_rapida.html")


@app.get("/pacientes/nuevo", response_class=HTMLResponse)
def formulario_alta(request: Request):
    return templates.TemplateResponse(request, "alta_rapida.html")


@app.post("/pacientes/alta", response_class=HTMLResponse)
def crear_paciente(
    request: Request,
    nombre_completo: str = Form(...),
    celular: Optional[str] = Form(None),
    correo_electronico: Optional[str] = Form(None),
    fecha_nacimiento: Optional[str] = Form(None),
    sexo: Optional[str] = Form(None),
    motivo_consulta: Optional[str] = Form(None),
    referido_por: Optional[str] = Form(None),
    origen_consulta: str = Form("privado"),
    cita_fecha: Optional[str] = Form(None),
    cita_hora: Optional[str] = Form(None),
    cita_notas: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    fecha_nac = None
    if fecha_nacimiento:
        fecha_nac = date.fromisoformat(fecha_nacimiento)

    paciente = models.Paciente(
        nombre_completo=nombre_completo,
        celular=celular,
        correo_electronico=correo_electronico,
        fecha_nacimiento=fecha_nac,
        sexo=sexo,
        motivo_consulta=motivo_consulta,
        referido_por=referido_por,
        origen_consulta=origen_consulta,
    )
    db.add(paciente)
    db.commit()
    db.refresh(paciente)

    mensaje = "Paciente " + nombre_completo + " guardado correctamente."

    if cita_fecha:
        hora = cita_hora if cita_hora else "09:00"
        fecha_hora = datetime.fromisoformat(cita_fecha + "T" + hora)
        cita = models.Cita(
            paciente_id=paciente.id,
            fecha_hora=fecha_hora,
            tipo="primera_consulta",
            estado="agendada",
            notas_breves=cita_notas,
        )
        db.add(cita)
        db.commit()
        db.refresh(cita)
        _sincronizar_creacion_google(db, cita, paciente, ya_en_google=False)
        mensaje = mensaje + " Cita agendada para el " + cita_fecha + " a las " + hora + "."

    return templates.TemplateResponse(
        request, "alta_rapida.html", {"mensaje": mensaje}
    )


@app.get("/pacientes", response_class=HTMLResponse)
def lista_pacientes(request: Request, db: Session = Depends(get_db)):
    pacientes = db.query(models.Paciente).order_by(models.Paciente.id.desc()).all()
    return templates.TemplateResponse(
        request, "lista_pacientes.html", {"pacientes": pacientes}
    )


@app.get("/pacientes/{paciente_id}", response_class=HTMLResponse)
def ver_expediente(paciente_id: int, request: Request, db: Session = Depends(get_db)):
    paciente = obtener_paciente(db, paciente_id)

    mensaje = None
    if request.query_params.get("error") == "inbody_fallo":
        mensaje = (
            "No se pudo leer el reporte de InBody con inteligencia artificial. "
            "Intenta con una foto mas clara, o captura los datos manualmente en un follow-up."
        )
    elif request.query_params.get("error") == "laboratorio_fallo":
        mensaje = (
            "No se pudo analizar el laboratorio con inteligencia artificial. "
            "Intenta con una foto o PDF mas claro."
        )

    citas = (
        db.query(models.Cita)
        .filter(models.Cita.paciente_id == paciente_id)
        .order_by(models.Cita.fecha_hora.desc())
        .all()
    )

    historia = (
        db.query(models.HistoriaClinica)
        .filter(models.HistoriaClinica.paciente_id == paciente_id)
        .first()
    )

    followups = (
        db.query(models.FollowUp)
        .filter(models.FollowUp.paciente_id == paciente_id)
        .order_by(models.FollowUp.numero_consulta.desc())
        .all()
    )

    mediciones = (
        db.query(models.MedicionInBody)
        .filter(models.MedicionInBody.paciente_id == paciente_id)
        .order_by(models.MedicionInBody.fecha_medicion.asc())
        .all()
    )

    # JSON listo para Chart.js. Se arma aqui, no en la plantilla, para que
    # agregar una metrica nueva a futuro (ej. tasa_metabolica_basal) sea
    # solo una linea en este diccionario, sin tocar la logica de consulta.
    mediciones_json = json.dumps(
        [
            {
                "fecha": m.fecha_medicion.strftime("%d/%m/%Y") if m.fecha_medicion else None,
                "peso": m.peso,
                "porcentaje_grasa": m.porcentaje_grasa,
                "mme": m.mme,
            }
            for m in mediciones
        ],
        ensure_ascii=False,
    )

    dietas = (
        db.query(models.DietaVersion)
        .filter(models.DietaVersion.paciente_id == paciente_id)
        .order_by(models.DietaVersion.version.desc())
        .all()
    )

    laboratorios = (
        db.query(models.Laboratorio)
        .filter(models.Laboratorio.paciente_id == paciente_id)
        .order_by(models.Laboratorio.fecha_subida.desc())
        .all()
    )

    return templates.TemplateResponse(
        request,
        "expediente.html",
        {
            "paciente": paciente,
            "citas": citas,
            "historia": historia,
            "followups": followups,
            "dietas": dietas,
            "mediciones": mediciones,
            "mediciones_json": mediciones_json,
            "laboratorios": laboratorios,
            "mensaje": mensaje,
        },
    )


@app.get("/pacientes/{paciente_id}/editar", response_class=HTMLResponse)
def formulario_editar_paciente(paciente_id: int, request: Request, db: Session = Depends(get_db)):
    paciente = obtener_paciente(db, paciente_id)
    return templates.TemplateResponse(request, "editar_paciente.html", {"paciente": paciente})


@app.post("/pacientes/{paciente_id}/editar")
def guardar_edicion_paciente(
    paciente_id: int,
    nombre_completo: str = Form(...),
    celular: Optional[str] = Form(None),
    correo_electronico: Optional[str] = Form(None),
    fecha_nacimiento: Optional[str] = Form(None),
    sexo: Optional[str] = Form(None),
    motivo_consulta: Optional[str] = Form(None),
    referido_por: Optional[str] = Form(None),
    origen_consulta: str = Form("privado"),
    db: Session = Depends(get_db),
):
    paciente = obtener_paciente(db, paciente_id)

    paciente.nombre_completo = nombre_completo
    paciente.celular = celular
    paciente.correo_electronico = correo_electronico
    paciente.fecha_nacimiento = date.fromisoformat(fecha_nacimiento) if fecha_nacimiento else None
    paciente.sexo = sexo
    paciente.motivo_consulta = motivo_consulta
    paciente.referido_por = referido_por
    paciente.origen_consulta = origen_consulta

    db.commit()

    return RedirectResponse(url="/pacientes/" + str(paciente_id), status_code=303)


def _calcular_edad(fecha_nacimiento):
    hoy = date.today()
    return hoy.year - fecha_nacimiento.year - (
        (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day)
    )


@app.post("/pacientes/{paciente_id}/inbody/procesar", response_class=HTMLResponse)
async def procesar_inbody(
    paciente_id: int,
    request: Request,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    paciente = obtener_paciente(db, paciente_id)

    imagen_bytes = await archivo.read()
    mime_type = archivo.content_type or "image/jpeg"

    try:
        resultado = inbody.procesar_reporte(imagen_bytes, mime_type)
    except Exception:
        return RedirectResponse(
            url="/pacientes/" + str(paciente_id) + "?error=inbody_fallo", status_code=303
        )

    advertencias = []

    id_inbody = resultado.get("id_inbody")
    if id_inbody:
        conflicto = (
            db.query(models.IdInBodyConocido)
            .filter(models.IdInBodyConocido.id_inbody == id_inbody)
            .filter(models.IdInBodyConocido.paciente_id != paciente_id)
            .first()
        )
        if conflicto:
            advertencias.append(
                "El ID de InBody '" + id_inbody + "' ya esta registrado a nombre de OTRO "
                "paciente. Verifica que este es el reporte correcto antes de continuar."
            )

    if resultado.get("edad") is not None and paciente.fecha_nacimiento:
        edad_calculada = _calcular_edad(paciente.fecha_nacimiento)
        if abs(edad_calculada - resultado["edad"]) > 1:
            advertencias.append(
                "La edad del reporte (" + str(resultado["edad"]) + ") no coincide con la "
                "edad calculada del paciente (" + str(edad_calculada) + ")."
            )

    if resultado.get("sexo") and paciente.sexo and resultado["sexo"] != paciente.sexo:
        advertencias.append(
            "El sexo del reporte (" + resultado["sexo"] + ") no coincide con el "
            "registrado en el expediente (" + paciente.sexo + ")."
        )

    if resultado.get("estatura_cm") and paciente.estatura:
        if abs(resultado["estatura_cm"] - paciente.estatura) > 3:
            advertencias.append(
                "La estatura del reporte (" + str(resultado["estatura_cm"]) + " cm) no "
                "coincide con la registrada (" + str(paciente.estatura) + " cm)."
            )

    return templates.TemplateResponse(
        request,
        "inbody_confirmar.html",
        {
            "paciente": paciente,
            "resultado": resultado,
            "advertencias": advertencias,
            "datos_json": json.dumps(resultado, ensure_ascii=False),
        },
    )


@app.post("/pacientes/{paciente_id}/inbody/confirmar")
def confirmar_inbody(
    paciente_id: int,
    datos_json: str = Form(...),
    db: Session = Depends(get_db),
):
    paciente = obtener_paciente(db, paciente_id)
    resultado = json.loads(datos_json)

    id_inbody = resultado.get("id_inbody")

    for punto in resultado.get("historial", []):
        if not punto.get("fecha"):
            continue
        medicion = models.MedicionInBody(
            paciente_id=paciente_id,
            fecha_medicion=datetime.fromisoformat(punto["fecha"]),
            peso=punto.get("peso"),
            imc=punto.get("imc"),
            porcentaje_grasa=punto.get("porcentaje_grasa"),
            masa_grasa_kg=punto.get("masa_grasa_kg"),
            mme=punto.get("mme"),
            grasa_visceral=punto.get("grasa_visceral"),
            tasa_metabolica_basal=punto.get("tasa_metabolica_basal"),
            origen="inbody",
            id_inbody_reporte=id_inbody,
        )
        db.add(medicion)

    if id_inbody:
        ya_conocido = (
            db.query(models.IdInBodyConocido)
            .filter(models.IdInBodyConocido.paciente_id == paciente_id)
            .filter(models.IdInBodyConocido.id_inbody == id_inbody)
            .first()
        )
        if not ya_conocido:
            db.add(models.IdInBodyConocido(
                paciente_id=paciente_id,
                id_inbody=id_inbody,
                clinica="UniDO",
            ))

    if not paciente.sexo and resultado.get("sexo"):
        paciente.sexo = resultado["sexo"]
    if not paciente.estatura and resultado.get("estatura_cm"):
        paciente.estatura = resultado["estatura_cm"]

    db.commit()

    return RedirectResponse(url="/pacientes/" + str(paciente_id), status_code=303)


@app.post("/pacientes/{paciente_id}/laboratorio/procesar", response_class=HTMLResponse)
async def procesar_laboratorio(
    paciente_id: int,
    request: Request,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    paciente = obtener_paciente(db, paciente_id)

    archivo_bytes = await archivo.read()
    mime_type = archivo.content_type or "application/pdf"

    try:
        analisis = laboratorio.analizar(archivo_bytes, mime_type)
    except Exception:
        return RedirectResponse(
            url="/pacientes/" + str(paciente_id) + "?error=laboratorio_fallo", status_code=303
        )

    return templates.TemplateResponse(
        request,
        "laboratorio_confirmar.html",
        {"paciente": paciente, "analisis": analisis},
    )


@app.post("/pacientes/{paciente_id}/laboratorio/guardar")
def guardar_laboratorio(
    paciente_id: int,
    analisis: str = Form(...),
    db: Session = Depends(get_db),
):
    obtener_paciente(db, paciente_id)

    db.add(models.Laboratorio(paciente_id=paciente_id, analisis_ia=analisis))
    db.commit()

    return RedirectResponse(url="/pacientes/" + str(paciente_id), status_code=303)


@app.post("/pacientes/{paciente_id}/laboratorio/{laboratorio_id}/eliminar")
def eliminar_laboratorio(paciente_id: int, laboratorio_id: int, db: Session = Depends(get_db)):
    lab = (
        db.query(models.Laboratorio)
        .filter(models.Laboratorio.id == laboratorio_id)
        .filter(models.Laboratorio.paciente_id == paciente_id)
        .first()
    )
    if lab:
        db.delete(lab)
        db.commit()

    return RedirectResponse(url="/pacientes/" + str(paciente_id), status_code=303)


@app.get("/pacientes/{paciente_id}/historia", response_class=HTMLResponse)
def ver_historia(paciente_id: int, request: Request, editar: int = 0, db: Session = Depends(get_db)):
    paciente = obtener_paciente(db, paciente_id)

    historia = (
        db.query(models.HistoriaClinica)
        .filter(models.HistoriaClinica.paciente_id == paciente_id)
        .first()
    )

    if not historia:
        historia = models.HistoriaClinica(paciente_id=paciente_id)

    return templates.TemplateResponse(
        request,
        "historia_clinica.html",
        {"paciente": paciente, "h": historia, "editar": bool(editar)},
    )


CAMPOS_HISTORIA = [
    "objetivo_que_espera", "objetivo_tiempo", "objetivo_importante",
    "antecedente_diabetes", "antecedente_obesidad", "antecedente_tiroides",
    "antecedente_hipertension", "antecedente_cardiovascular", "antecedente_cancer",
    "antecedente_otros", "padecimientos_diagnosticados", "cirugias",
    "tratamiento_medico_actual", "gineco_menarca", "gineco_ciclo",
    "gineco_anticonceptivo", "gineco_embarazos", "gineco_busca_embarazo",
    "gineco_menopausia", "edad_inicio_sobrepeso", "dietas_previas",
    "sint_gastrointestinal", "sint_distension", "sint_hormigueo",
    "sint_caida_pelo", "sint_unas_debiles", "sint_dolor_cabeza",
    "sint_memoria", "sint_fatiga", "sint_piel_seca", "sint_acantosis",
    "sint_otro", "alergias", "intolerancias", "alimentos_evitar",
    "restricciones_eleccion", "recordatorio_desayuno", "recordatorio_comida",
    "recordatorio_cena", "recordatorio_snacks", "hidratacion", "quien_cocina",
    "ejercicio_rutina", "alcohol", "tabaco", "sueno", "suplementos", "medicamentos",
]


@app.post("/pacientes/{paciente_id}/historia")
async def guardar_historia(paciente_id: int, request: Request, db: Session = Depends(get_db)):
    paciente = obtener_paciente(db, paciente_id)

    form = await request.form()

    historia = (
        db.query(models.HistoriaClinica)
        .filter(models.HistoriaClinica.paciente_id == paciente_id)
        .first()
    )

    if not historia:
        historia = models.HistoriaClinica(paciente_id=paciente_id)
        db.add(historia)

    for campo in CAMPOS_HISTORIA:
        valor = form.get(campo)
        setattr(historia, campo, valor if valor else None)

    for campo_num in ["peso_maximo", "peso_minimo"]:
        valor = form.get(campo_num)
        setattr(historia, campo_num, float(valor) if valor else None)

    estres = form.get("nivel_estres")
    historia.nivel_estres = int(estres) if estres else None

    # Medicion capturada a mano en la Historia Clinica (bloque identico al
    # de Follow-up): crea una medicion real (misma tabla que usan las
    # graficas de Progreso y la generacion de dietas), no solo una nota de
    # referencia. Resuelve el caso del paciente que llega a su primera
    # consulta ya con InBody o bascula tomados antes de sentarse con
    # Marifer. Si se llena aunque sea un campo, se crea el registro.
    campos_medicion = ["peso", "imc", "porcentaje_grasa", "masa_grasa_kg", "mme", "grasa_visceral"]
    if any(form.get(c) for c in campos_medicion):
        medicion = models.MedicionInBody(paciente_id=paciente_id, origen="manual")
        for campo in campos_medicion:
            valor = form.get(campo)
            setattr(medicion, campo, float(valor) if valor else None)
        db.add(medicion)

    # La estatura, a diferencia del peso, es un dato fijo del paciente (no
    # una serie de tiempo): siempre se actualiza con lo que se capture aqui,
    # nunca solo "la primera vez".
    estatura_actual = form.get("estatura_actual")
    if estatura_actual:
        paciente.estatura = float(estatura_actual)

    db.commit()

    return RedirectResponse(url="/pacientes/" + str(paciente_id), status_code=303)


@app.post("/pacientes/{paciente_id}/medicion/{medicion_id}/eliminar")
def eliminar_medicion(paciente_id: int, medicion_id: int, db: Session = Depends(get_db)):
    medicion = (
        db.query(models.MedicionInBody)
        .filter(models.MedicionInBody.id == medicion_id)
        .filter(models.MedicionInBody.paciente_id == paciente_id)
        .first()
    )
    if medicion:
        db.delete(medicion)
        db.commit()

    return RedirectResponse(url="/pacientes/" + str(paciente_id) + "#seccion-progreso", status_code=303)


def _sincronizar_creacion_google(db, cita, paciente, ya_en_google):
    """
    Crea el evento en el calendario de Google correspondiente al
    origen_consulta del paciente, salvo que ya_en_google indique que
    la cita nacio directo en Google Calendar (se evita duplicar).
    Un fallo aqui nunca debe tronar la peticion: la cita ya quedo
    guardada en el sistema, que es lo indispensable.
    """
    if ya_en_google:
        return
    try:
        event_id = calendario.crear_evento(
            paciente.origen_consulta or "privado",
            resumen=paciente.nombre_completo,
            fecha_hora_inicio=cita.fecha_hora,
            descripcion=cita.notas_breves or "",
        )
        cita.google_event_id = event_id
        db.commit()
    except Exception as e:
        print("Aviso: no se pudo sincronizar con Google Calendar:", str(e)[:300])


def _sincronizar_borrado_google(db, cita, paciente):
    """Borra el evento de Google Calendar de una cita, si tenia uno."""
    if not cita.google_event_id:
        return
    try:
        calendario.eliminar_evento(paciente.origen_consulta or "privado", cita.google_event_id)
        cita.google_event_id = None
        db.commit()
    except Exception as e:
        print("Aviso: no se pudo borrar el evento de Google Calendar:", str(e)[:300])


@app.post("/pacientes/{paciente_id}/citas/nueva")
def nueva_cita(
    paciente_id: int,
    fecha: str = Form(...),
    hora: str = Form(...),
    notas: Optional[str] = Form(None),
    ya_en_google: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    paciente = obtener_paciente(db, paciente_id)

    existe_previa = (
        db.query(models.Cita)
        .filter(models.Cita.paciente_id == paciente_id)
        .first()
    )
    tipo = "seguimiento" if existe_previa else "primera_consulta"

    cita = models.Cita(
        paciente_id=paciente_id,
        fecha_hora=datetime.fromisoformat(fecha + "T" + hora),
        tipo=tipo,
        estado="agendada",
        notas_breves=notas,
    )
    db.add(cita)
    db.commit()
    db.refresh(cita)

    _sincronizar_creacion_google(db, cita, paciente, ya_en_google=bool(ya_en_google))

    return RedirectResponse(url="/pacientes/" + str(paciente_id), status_code=303)


@app.post("/citas/{cita_id}/estado")
def cambiar_estado_cita(
    cita_id: int,
    nuevo_estado: str = Form(...),
    db: Session = Depends(get_db),
):
    cita = db.query(models.Cita).filter(models.Cita.id == cita_id).first()
    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    estados_validos = ["agendada", "confirmada", "cancelada", "completada", "no_asistio"]
    if nuevo_estado not in estados_validos:
        raise HTTPException(status_code=400, detail="Estado no valido")

    cita.estado = nuevo_estado
    db.commit()

    if nuevo_estado == "cancelada":
        paciente = obtener_paciente(db, cita.paciente_id)
        _sincronizar_borrado_google(db, cita, paciente)

    return RedirectResponse(url="/pacientes/" + str(cita.paciente_id), status_code=303)


@app.post("/citas/{cita_id}/reagendar")
def reagendar_cita(
    cita_id: int,
    fecha: str = Form(...),
    hora: str = Form(...),
    ya_en_google: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    cita_anterior = db.query(models.Cita).filter(models.Cita.id == cita_id).first()
    if not cita_anterior:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    paciente = obtener_paciente(db, cita_anterior.paciente_id)

    cita_anterior.estado = "cancelada"
    db.commit()
    _sincronizar_borrado_google(db, cita_anterior, paciente)

    cita_nueva = models.Cita(
        paciente_id=cita_anterior.paciente_id,
        fecha_hora=datetime.fromisoformat(fecha + "T" + hora),
        tipo=cita_anterior.tipo,
        estado="agendada",
        notas_breves=cita_anterior.notas_breves,
    )
    db.add(cita_nueva)
    db.commit()
    db.refresh(cita_nueva)

    _sincronizar_creacion_google(db, cita_nueva, paciente, ya_en_google=bool(ya_en_google))

    return RedirectResponse(url="/pacientes/" + str(cita_anterior.paciente_id), status_code=303)


@app.get("/pacientes/{paciente_id}/followup/nuevo", response_class=HTMLResponse)
def formulario_followup(paciente_id: int, request: Request, db: Session = Depends(get_db)):
    paciente = obtener_paciente(db, paciente_id)

    anterior = (
        db.query(models.FollowUp)
        .filter(models.FollowUp.paciente_id == paciente_id)
        .order_by(models.FollowUp.numero_consulta.desc())
        .first()
    )

    numero_consulta = (anterior.numero_consulta + 1) if anterior else 1

    return templates.TemplateResponse(
        request,
        "follow_up.html",
        {
            "paciente": paciente,
            "anterior": anterior,
            "numero_consulta": numero_consulta,
            "hoy": date.today().isoformat(),
        },
    )


@app.post("/pacientes/{paciente_id}/followup")
async def guardar_followup(paciente_id: int, request: Request, db: Session = Depends(get_db)):
    obtener_paciente(db, paciente_id)
    form = await request.form()

    anterior = (
        db.query(models.FollowUp)
        .filter(models.FollowUp.paciente_id == paciente_id)
        .order_by(models.FollowUp.numero_consulta.desc())
        .first()
    )
    numero_consulta = (anterior.numero_consulta + 1) if anterior else 1

    medicion_id = None
    campos_medicion = ["peso", "imc", "porcentaje_grasa", "masa_grasa_kg", "mme", "grasa_visceral"]
    hay_medicion = any(form.get(c) for c in campos_medicion)

    if hay_medicion:
        medicion = models.MedicionInBody(paciente_id=paciente_id, origen="manual")
        for campo in campos_medicion:
            valor = form.get(campo)
            setattr(medicion, campo, float(valor) if valor else None)
        db.add(medicion)
        db.commit()
        db.refresh(medicion)
        medicion_id = medicion.id

    fecha_consulta = form.get("fecha_consulta")
    proxima_cita = form.get("proxima_cita")
    apego = form.get("porcentaje_apego")
    dias_ejercicio = form.get("promedio_dias_ejercicio")

    followup = models.FollowUp(
        paciente_id=paciente_id,
        numero_consulta=numero_consulta,
        fecha_consulta=datetime.fromisoformat(fecha_consulta) if fecha_consulta else datetime.utcnow(),
        proxima_cita=date.fromisoformat(proxima_cita) if proxima_cita else None,
        porcentaje_apego=float(apego) if apego else None,
        promedio_dias_ejercicio=float(dias_ejercicio) if dias_ejercicio else None,
        que_le_gusto=form.get("que_le_gusto") or None,
        que_no_le_gusto=form.get("que_no_le_gusto") or None,
        cambios_que_hizo=form.get("cambios_que_hizo") or None,
        en_que_puede_mejorar=form.get("en_que_puede_mejorar") or None,
        estatus_tratamiento_medico=form.get("estatus_tratamiento_medico") or None,
        notas_libres=form.get("notas_libres") or None,
        ajustes_acordados=form.get("ajustes_acordados") or None,
        medicion_inbody_id=medicion_id,
    )
    db.add(followup)

    if proxima_cita:
        cita = models.Cita(
            paciente_id=paciente_id,
            fecha_hora=datetime.fromisoformat(proxima_cita + "T09:00"),
            tipo="seguimiento",
            estado="agendada",
            notas_breves="Agendada desde la consulta " + str(numero_consulta),
        )
        db.add(cita)

    db.commit()

    return RedirectResponse(url="/pacientes/" + str(paciente_id), status_code=303)


def _cargar_contenido(dieta):
    """El campo contenido de DietaVersion guarda un JSON con el
    documento redactado mas el resumen de verificacion."""
    return json.loads(dieta.contenido)


@app.get("/pacientes/{paciente_id}/dieta/nueva", response_class=HTMLResponse)
def formulario_generar_dieta(paciente_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Siempre muestra una pantalla de confirmacion antes de generar: elegir
    Menu o Tabla de Porciones, y si hay laboratorios, decidir si incluir
    alguno.
    """
    paciente = obtener_paciente(db, paciente_id)

    laboratorios = (
        db.query(models.Laboratorio)
        .filter(models.Laboratorio.paciente_id == paciente_id)
        .order_by(models.Laboratorio.fecha_subida.desc())
        .all()
    )

    return templates.TemplateResponse(
        request,
        "dieta_nueva.html",
        {"paciente": paciente, "laboratorios": laboratorios},
    )


@app.post("/pacientes/{paciente_id}/dieta/nueva")
def generar_dieta_confirmada(
    paciente_id: int,
    tipo_documento: str = Form("menu"),
    incluir_laboratorio: Optional[str] = Form(None),
    laboratorio_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    analisis_laboratorio = None
    if incluir_laboratorio and laboratorio_id:
        lab = (
            db.query(models.Laboratorio)
            .filter(models.Laboratorio.id == int(laboratorio_id))
            .first()
        )
        if lab:
            analisis_laboratorio = lab.analisis_ia

    return _generar_dieta_y_redirigir(
        paciente_id, db, analisis_laboratorio=analisis_laboratorio, tipo_documento=tipo_documento
    )


def _generar_dieta_y_redirigir(paciente_id: int, db: Session, analisis_laboratorio=None, tipo_documento="menu"):
    paciente = obtener_paciente(db, paciente_id)

    historia_obj = (
        db.query(models.HistoriaClinica)
        .filter(models.HistoriaClinica.paciente_id == paciente_id)
        .first()
    )
    if not historia_obj:
        raise HTTPException(
            status_code=400,
            detail="El paciente no tiene historia clinica. Llenala antes de generar una dieta.",
        )

    medicion_obj = (
        db.query(models.MedicionInBody)
        .filter(models.MedicionInBody.paciente_id == paciente_id)
        .order_by(models.MedicionInBody.fecha_medicion.desc())
        .first()
    )
    if not medicion_obj:
        raise HTTPException(
            status_code=400,
            detail="El paciente no tiene ninguna medicion registrada (se necesita el peso). Agrega una desde un follow-up.",
        )

    paciente_dict = {"sexo": paciente.sexo}
    historia_dict = {c.name: getattr(historia_obj, c.name) for c in historia_obj.__table__.columns}
    medicion_dict = {c.name: getattr(medicion_obj, c.name) for c in medicion_obj.__table__.columns}

    padecimientos = []
    if historia_dict.get("padecimientos_diagnosticados"):
        padecimientos.append(historia_dict["padecimientos_diagnosticados"])

    ultima = (
        db.query(models.DietaVersion)
        .filter(models.DietaVersion.paciente_id == paciente_id)
        .order_by(models.DietaVersion.version.desc())
        .first()
    )
    numero_version = (ultima.version + 1) if ultima else 1

    if tipo_documento == "porciones":
        # Los ejemplos de comidas armadas solo se incluyen la primera vez
        # que este paciente recibe una Tabla de Porciones (decision de
        # Marifer). Las siguientes veces se omiten solos.
        ya_tuvo_porciones = (
            db.query(models.DietaVersion)
            .filter(models.DietaVersion.paciente_id == paciente_id)
            .filter(models.DietaVersion.tipo_documento == "porciones")
            .first()
        )
        incluir_ejemplos = ya_tuvo_porciones is None

        resultado = plan_gen.generar_tabla_porciones(
            paciente_dict, historia_dict, medicion_dict, incluir_ejemplos,
            padecimientos=padecimientos,
        )
        guardado = {
            "documento": resultado["documento"],
            "confiable": resultado["verificacion"]["confiable"],
            "problemas": resultado["verificacion"]["problemas"],
        }
    else:
        # Continuidad con el plan anterior: se le pasa a Gemini como
        # contexto, nunca como instruccion de repetir o evitar (ver
        # plan_generador.py). Es exclusivo del Menu; la Tabla de Porciones
        # no maneja "opciones prescritas" en ese sentido.
        ultima_aprobada = (
            db.query(models.DietaVersion)
            .filter(models.DietaVersion.paciente_id == paciente_id)
            .filter(models.DietaVersion.estado == "aprobada")
            .order_by(models.DietaVersion.version.desc())
            .first()
        )
        opciones_previas = None
        if ultima_aprobada:
            filas_opciones = (
                db.query(models.OpcionPrescrita)
                .filter(models.OpcionPrescrita.dieta_id == ultima_aprobada.id)
                .all()
            )
            if filas_opciones:
                opciones_previas = [f.descripcion for f in filas_opciones if f.descripcion]

        ultimo_followup = (
            db.query(models.FollowUp)
            .filter(models.FollowUp.paciente_id == paciente_id)
            .order_by(models.FollowUp.numero_consulta.desc())
            .first()
        )
        retroalimentacion = None
        if ultimo_followup:
            retroalimentacion = {
                "que_le_gusto": ultimo_followup.que_le_gusto,
                "que_no_le_gusto": ultimo_followup.que_no_le_gusto,
                "cambios_que_hizo": ultimo_followup.cambios_que_hizo,
                "en_que_puede_mejorar": ultimo_followup.en_que_puede_mejorar,
                "ajustes_acordados": ultimo_followup.ajustes_acordados,
            }

        resultado_plan = plan_gen.generar_plan(
            paciente_dict, historia_dict, medicion_dict, padecimientos=padecimientos,
            opciones_previas=opciones_previas,
            retroalimentacion_followup=retroalimentacion,
            analisis_laboratorio=analisis_laboratorio,
        )
        resultado_doc = redactor.redactar(resultado_plan["plan"], nombre_paciente=paciente.nombre_completo)

        guardado = {
            "documento": resultado_doc["documento"],
            "confiable": resultado_plan["verificacion"]["resumen"]["confiable"],
            "cobertura": resultado_plan["verificacion"]["resumen"]["cobertura_promedio"],
        }

    dieta = models.DietaVersion(
        paciente_id=paciente_id,
        version=numero_version,
        contenido=json.dumps(guardado, ensure_ascii=False),
        estado="borrador_ia",
        creado_por="ia",
        tipo_documento=tipo_documento,
        version_anterior_id=ultima.id if ultima else None,
    )
    db.add(dieta)
    db.commit()
    db.refresh(dieta)

    return RedirectResponse(url="/pacientes/" + str(paciente_id) + "/dieta/" + str(dieta.id), status_code=303)


@app.get("/pacientes/{paciente_id}/dieta/nueva-manual")
def crear_dieta_manual(paciente_id: int, db: Session = Depends(get_db)):
    """
    Crea un borrador completamente vacio, para llenar a mano cuando no
    hay internet o no se quiere usar la IA. Reutiliza la misma pantalla
    de edicion que un borrador generado por IA.

    Esta ruta debe quedar registrada ANTES que ver_dieta (mas abajo): las
    dos tienen la forma /dieta/<algo>, y FastAPI usa la primera que
    coincida en orden de registro, sin importar el tipo esperado. Si
    ver_dieta queda primero, "nueva-manual" se intenta leer como
    dieta_id (entero) y truena.
    """
    obtener_paciente(db, paciente_id)

    ultima = (
        db.query(models.DietaVersion)
        .filter(models.DietaVersion.paciente_id == paciente_id)
        .order_by(models.DietaVersion.version.desc())
        .first()
    )
    numero_version = (ultima.version + 1) if ultima else 1

    documento_vacio = {
        "objetivos_clave": [],
        "suplementacion": [],
        "menu": {t: {"encabezado": "", "opciones": []} for t in TIEMPOS_MENU},
        "recomendaciones": [],
    }
    guardado = {"documento": documento_vacio, "confiable": False, "cobertura": 0}

    dieta = models.DietaVersion(
        paciente_id=paciente_id,
        version=numero_version,
        contenido=json.dumps(guardado, ensure_ascii=False),
        estado="borrador_ia",
        creado_por="manual",
        version_anterior_id=ultima.id if ultima else None,
    )
    db.add(dieta)
    db.commit()
    db.refresh(dieta)

    return RedirectResponse(
        url="/pacientes/" + str(paciente_id) + "/dieta/" + str(dieta.id) + "/editar", status_code=303
    )


@app.get("/pacientes/{paciente_id}/dieta/{dieta_id}", response_class=HTMLResponse)
def ver_dieta(paciente_id: int, dieta_id: int, request: Request, db: Session = Depends(get_db)):
    paciente = obtener_paciente(db, paciente_id)
    dieta = db.query(models.DietaVersion).filter(models.DietaVersion.id == dieta_id).first()
    if not dieta:
        raise HTTPException(status_code=404, detail="Version de dieta no encontrada")

    guardado = _cargar_contenido(dieta)

    mensaje = None
    if request.query_params.get("enviado"):
        mensaje = "Dieta enviada por correo a " + (paciente.correo_electronico or "")
    elif request.query_params.get("error") == "sin_correo":
        mensaje = "Este paciente no tiene correo electronico registrado. Agregalo en sus datos de contacto."

    if dieta.tipo_documento == "porciones":
        return templates.TemplateResponse(
            request,
            "ver_porciones.html",
            {
                "paciente": paciente,
                "dieta": dieta,
                "doc": guardado["documento"],
                "confiable": guardado.get("confiable", False),
                "problemas": guardado.get("problemas", []),
                "mensaje": mensaje,
            },
        )

    return templates.TemplateResponse(
        request,
        "ver_dieta.html",
        {
            "paciente": paciente,
            "dieta": dieta,
            "doc": guardado["documento"],
            "menu": guardado["documento"].get("menu", {}),
            "confiable": guardado.get("confiable", False),
            "mensaje": mensaje,
        },
    )


@app.post("/pacientes/{paciente_id}/dieta/{dieta_id}/aprobar")
def aprobar_dieta(paciente_id: int, dieta_id: int, db: Session = Depends(get_db)):
    dieta = db.query(models.DietaVersion).filter(models.DietaVersion.id == dieta_id).first()
    if not dieta:
        raise HTTPException(status_code=404, detail="Version de dieta no encontrada")

    dieta.estado = "aprobada"

    # Registro de opciones prescritas: se guarda solo al aprobar, nunca en
    # un borrador, para que "ya se le dio esto" signifique que de verdad
    # llego al paciente.
    guardado = _cargar_contenido(dieta)
    menu = guardado.get("documento", {}).get("menu", {})
    for tipo_comida, datos in menu.items():
        for opcion_texto in datos.get("opciones", []) or []:
            db.add(models.OpcionPrescrita(
                dieta_id=dieta.id,
                tipo_comida=tipo_comida,
                descripcion=opcion_texto,
            ))

    db.commit()

    return RedirectResponse(url="/pacientes/" + str(paciente_id), status_code=303)


TIEMPOS_MENU = ["desayuno", "colacion", "comida", "cena"]


def _lineas_a_lista(texto):
    """Convierte un textarea (una idea por linea) en una lista, sin lineas vacias."""
    if not texto:
        return []
    return [linea.strip() for linea in texto.split("\n") if linea.strip()]


def _lista_a_lineas(lista):
    """Inverso de _lineas_a_lista, para prellenar el formulario de edicion."""
    return "\n".join(lista or [])


def _filas_a_lineas_porciones(filas):
    """
    Convierte una lista de {"alimento":.., "cantidad":..} (formato de la
    Tabla de Porciones) en texto, una fila por linea, "Alimento - Cantidad".
    """
    lineas = []
    for f in filas or []:
        lineas.append((f.get("alimento") or "") + " - " + (f.get("cantidad") or ""))
    return "\n".join(lineas)


def _lineas_a_filas_porciones(texto):
    """Inverso de _filas_a_lineas_porciones."""
    filas = []
    for linea in (texto or "").split("\n"):
        linea = linea.strip()
        if not linea:
            continue
        if " - " in linea:
            alimento, cantidad = linea.split(" - ", 1)
        else:
            alimento, cantidad = linea, ""
        filas.append({"alimento": alimento.strip(), "cantidad": cantidad.strip()})
    return filas


@app.get("/pacientes/{paciente_id}/dieta/{dieta_id}/editar", response_class=HTMLResponse)
def formulario_editar_dieta(paciente_id: int, dieta_id: int, request: Request, db: Session = Depends(get_db)):
    paciente = obtener_paciente(db, paciente_id)
    dieta = db.query(models.DietaVersion).filter(models.DietaVersion.id == dieta_id).first()
    if not dieta:
        raise HTTPException(status_code=404, detail="Version de dieta no encontrada")
    if dieta.estado == "aprobada":
        raise HTTPException(status_code=400, detail="Una dieta ya aprobada no se puede editar.")

    guardado = _cargar_contenido(dieta)
    doc = guardado.get("documento", {})

    if dieta.tipo_documento == "porciones":
        ejemplos = doc.get("ejemplos") or {}
        return templates.TemplateResponse(
            request,
            "dieta_editar_porciones.html",
            {
                "paciente": paciente,
                "dieta": dieta,
                "meta_proteina": doc.get("meta_proteina", ""),
                "instruccion_general": doc.get("instruccion_general", ""),
                "tabla_proteinas_texto": _filas_a_lineas_porciones(doc.get("tabla_proteinas")),
                "objetivo_distribucion_texto": _lista_a_lineas(doc.get("objetivo_distribucion")),
                "carbohidratos_instruccion": doc.get("tabla_carbohidratos", {}).get("instruccion", ""),
                "carbohidratos_texto": _filas_a_lineas_porciones(doc.get("tabla_carbohidratos", {}).get("alimentos")),
                "grasas_instruccion": doc.get("tabla_grasas", {}).get("instruccion", ""),
                "grasas_texto": _filas_a_lineas_porciones(doc.get("tabla_grasas", {}).get("alimentos")),
                "nota_verduras": doc.get("nota_verduras", ""),
                "metas_diarias_texto": _lista_a_lineas(doc.get("metas_diarias")),
                "ejemplo_desayuno_texto": _lista_a_lineas(ejemplos.get("desayuno")),
                "ejemplo_comida_texto": _lista_a_lineas(ejemplos.get("comida")),
                "ejemplo_cena_texto": _lista_a_lineas(ejemplos.get("cena")),
            },
        )

    menu = doc.get("menu", {})
    campos_menu = {}
    for tiempo in TIEMPOS_MENU:
        datos = menu.get(tiempo, {})
        campos_menu[tiempo] = {
            "encabezado": datos.get("encabezado", ""),
            "opciones_texto": _lista_a_lineas(datos.get("opciones")),
        }

    return templates.TemplateResponse(
        request,
        "dieta_editar.html",
        {
            "paciente": paciente,
            "dieta": dieta,
            "objetivos_texto": _lista_a_lineas(doc.get("objetivos_clave")),
            "suplementacion_texto": _lista_a_lineas(doc.get("suplementacion")),
            "recomendaciones_texto": _lista_a_lineas(doc.get("recomendaciones")),
            "campos_menu": campos_menu,
            "tiempos_menu": TIEMPOS_MENU,
        },
    )


@app.post("/pacientes/{paciente_id}/dieta/{dieta_id}/editar")
async def guardar_edicion_dieta(paciente_id: int, dieta_id: int, request: Request, db: Session = Depends(get_db)):
    dieta = db.query(models.DietaVersion).filter(models.DietaVersion.id == dieta_id).first()
    if not dieta:
        raise HTTPException(status_code=404, detail="Version de dieta no encontrada")
    if dieta.estado == "aprobada":
        raise HTTPException(status_code=400, detail="Una dieta ya aprobada no se puede editar.")

    form = await request.form()

    if dieta.tipo_documento == "porciones":
        ejemplo_desayuno = _lineas_a_lista(form.get("ejemplo_desayuno", ""))
        ejemplo_comida = _lineas_a_lista(form.get("ejemplo_comida", ""))
        ejemplo_cena = _lineas_a_lista(form.get("ejemplo_cena", ""))
        ejemplos = None
        if ejemplo_desayuno or ejemplo_comida or ejemplo_cena:
            ejemplos = {"desayuno": ejemplo_desayuno, "comida": ejemplo_comida, "cena": ejemplo_cena}

        documento_editado = {
            "meta_proteina": form.get("meta_proteina", ""),
            "instruccion_general": form.get("instruccion_general", ""),
            "tabla_proteinas": _lineas_a_filas_porciones(form.get("tabla_proteinas", "")),
            "objetivo_distribucion": _lineas_a_lista(form.get("objetivo_distribucion", "")),
            "tabla_carbohidratos": {
                "instruccion": form.get("carbohidratos_instruccion", ""),
                "alimentos": _lineas_a_filas_porciones(form.get("carbohidratos_alimentos", "")),
            },
            "tabla_grasas": {
                "instruccion": form.get("grasas_instruccion", ""),
                "alimentos": _lineas_a_filas_porciones(form.get("grasas_alimentos", "")),
            },
            "nota_verduras": form.get("nota_verduras", ""),
            "metas_diarias": _lineas_a_lista(form.get("metas_diarias", "")),
            "ejemplos": ejemplos,
        }

        guardado = {
            "documento": documento_editado,
            "confiable": False,
            "problemas": [],
            "nota": "Editada manualmente, las cantidades no se verificaron contra la base de datos nutricional.",
        }
    else:
        menu_editado = {}
        for tiempo in TIEMPOS_MENU:
            menu_editado[tiempo] = {
                "encabezado": form.get("encabezado_" + tiempo, "") or "",
                "opciones": _lineas_a_lista(form.get("opciones_" + tiempo, "")),
            }

        documento_editado = {
            "objetivos_clave": _lineas_a_lista(form.get("objetivos_clave", "")),
            "suplementacion": _lineas_a_lista(form.get("suplementacion", "")),
            "menu": menu_editado,
            "recomendaciones": _lineas_a_lista(form.get("recomendaciones", "")),
        }

        guardado = {
            "documento": documento_editado,
            "confiable": False,
            "cobertura": 0,
            "nota": "Editada manualmente, las cantidades no se verificaron contra la base de datos nutricional.",
        }

    # Se guarda en el mismo borrador, sin crear una version nueva: mientras
    # no este aprobada, es un documento de trabajo. El historial de
    # versiones queda para hitos reales (aprobada, o un ajuste de la IA).
    dieta.contenido = json.dumps(guardado, ensure_ascii=False)
    db.commit()

    return RedirectResponse(
        url="/pacientes/" + str(paciente_id) + "/dieta/" + str(dieta_id), status_code=303
    )


@app.post("/pacientes/{paciente_id}/dieta/{dieta_id}/ajustar")
def ajustar_dieta(
    paciente_id: int,
    dieta_id: int,
    instruccion: str = Form(...),
    db: Session = Depends(get_db),
):
    anterior = db.query(models.DietaVersion).filter(models.DietaVersion.id == dieta_id).first()
    if not anterior:
        raise HTTPException(status_code=404, detail="Version de dieta no encontrada")

    anterior.estado = "reemplazada"
    guardado_anterior = _cargar_contenido(anterior)

    paciente = obtener_paciente(db, paciente_id)

    prompt_ajuste = (
        "Ajusta este documento de dieta segun la siguiente instruccion de la "
        "nutriologa. Cambia SOLO lo que se pide, deja todo lo demas exactamente "
        "igual.\n\n"
        "INSTRUCCION: " + instruccion + "\n\n"
        "DOCUMENTO ACTUAL:\n" + json.dumps(guardado_anterior["documento"], ensure_ascii=False) +
        "\n\nIMPORTANTE: tu respuesta debe tener EXACTAMENTE la misma estructura "
        "de JSON que el documento actual (las mismas claves de primer nivel: "
        "objetivos_clave, suplementacion, menu, recomendaciones, cierre; y dentro "
        "de menu, las mismas claves de tiempo de comida: desayuno, colacion, "
        "comida, cena, cada una con encabezado y opciones). No la reorganices, "
        "no muevas 'cena' o cualquier tiempo de comida fuera de 'menu'."
    )

    import claude_api
    nuevo_documento = claude_api.generar_json(
        prompt_ajuste,
        sistema=redactor._sistema(),
        temperatura=0.5,
    )

    # Salvaguarda: si a pesar de la instruccion Claude devuelve el menu
    # reorganizado fuera de "menu", lo reacomodamos antes de guardar.
    if "menu" not in nuevo_documento:
        tiempos = ["desayuno", "colacion", "comida", "cena"]
        menu_reconstruido = {}
        for tiempo in tiempos:
            if tiempo in nuevo_documento:
                menu_reconstruido[tiempo] = nuevo_documento.pop(tiempo)
        if menu_reconstruido:
            nuevo_documento["menu"] = menu_reconstruido

    numero_version = anterior.version + 1
    guardado = {
        "documento": nuevo_documento,
        "confiable": False,
        "cobertura": 0,
        "nota": "Ajustada manualmente, las cantidades no se volvieron a verificar contra la base de datos nutricional.",
    }

    dieta = models.DietaVersion(
        paciente_id=paciente_id,
        version=numero_version,
        contenido=json.dumps(guardado, ensure_ascii=False),
        estado="borrador_ia",
        creado_por="ia",
        instruccion_ajuste=instruccion,
        version_anterior_id=anterior.id,
    )
    db.add(dieta)
    db.commit()
    db.refresh(dieta)

    return RedirectResponse(url="/pacientes/" + str(paciente_id) + "/dieta/" + str(dieta.id), status_code=303)


@app.post("/pacientes/{paciente_id}/dieta/{dieta_id}/enviar-correo")
def enviar_dieta_por_correo(paciente_id: int, dieta_id: int, db: Session = Depends(get_db)):
    paciente = obtener_paciente(db, paciente_id)

    if not paciente.correo_electronico:
        return RedirectResponse(
            url="/pacientes/" + str(paciente_id) + "/dieta/" + str(dieta_id) + "?error=sin_correo",
            status_code=303,
        )

    dieta = db.query(models.DietaVersion).filter(models.DietaVersion.id == dieta_id).first()
    if not dieta:
        raise HTTPException(status_code=404, detail="Version de dieta no encontrada")

    guardado = _cargar_contenido(dieta)
    if dieta.tipo_documento == "porciones":
        ruta_pdf = pdf_gen.generar_porciones(guardado["documento"], paciente.nombre_completo)
    else:
        ruta_pdf = pdf_gen.generar(guardado["documento"], paciente.nombre_completo)

    correo.enviar_dieta(paciente.correo_electronico, paciente.nombre_completo, ruta_pdf)

    return RedirectResponse(
        url="/pacientes/" + str(paciente_id) + "/dieta/" + str(dieta_id) + "?enviado=1",
        status_code=303,
    )


@app.get("/pacientes/{paciente_id}/dieta/{dieta_id}/pdf")
def descargar_pdf(paciente_id: int, dieta_id: int, db: Session = Depends(get_db)):
    paciente = obtener_paciente(db, paciente_id)
    dieta = db.query(models.DietaVersion).filter(models.DietaVersion.id == dieta_id).first()
    if not dieta:
        raise HTTPException(status_code=404, detail="Version de dieta no encontrada")

    guardado = _cargar_contenido(dieta)
    if dieta.tipo_documento == "porciones":
        ruta_pdf = pdf_gen.generar_porciones(guardado["documento"], paciente.nombre_completo)
    else:
        ruta_pdf = pdf_gen.generar(guardado["documento"], paciente.nombre_completo)

    return FileResponse(ruta_pdf, media_type="application/pdf", filename=os.path.basename(ruta_pdf))


@app.post("/pacientes/{paciente_id}/dieta/{dieta_id}/eliminar")
def eliminar_dieta(paciente_id: int, dieta_id: int, db: Session = Depends(get_db)):
    dieta = (
        db.query(models.DietaVersion)
        .filter(models.DietaVersion.id == dieta_id)
        .filter(models.DietaVersion.paciente_id == paciente_id)
        .first()
    )
    if dieta:
        db.query(models.OpcionPrescrita).filter(models.OpcionPrescrita.dieta_id == dieta.id).delete()
        db.delete(dieta)
        db.commit()

    return RedirectResponse(url="/pacientes/" + str(paciente_id) + "#seccion-dietas", status_code=303)
