import json
import os
from fastapi import FastAPI, Request, Form, Depends, HTTPException
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
import plan_generador as plan_gen
import redactor
import pdf as pdf_gen

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SESSION_SECRET_KEY"],
    max_age=60 * 60 * 12,  # 12 horas
)

RUTAS_PUBLICAS = {"/login", "/olvide-password", "/restablecer-password"}


class RequiereLoginMiddleware(BaseHTTPMiddleware):
    """
    Bloquea toda la aplicacion salvo /login hasta que la sesion tenga
    la marca de autenticado. Es deliberadamente simple: un solo
    operador, una sola contraseña, sin roles ni permisos distintos.
    """
    async def dispatch(self, request: Request, call_next):
        if request.url.path in RUTAS_PUBLICAS:
            return await call_next(request)

        if not request.session.get("autenticado"):
            return RedirectResponse(url="/login", status_code=303)

        return await call_next(request)


app.add_middleware(RequiereLoginMiddleware)


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

    return templates.TemplateResponse(
        request,
        "expediente.html",
        {"paciente": paciente, "citas": citas, "historia": historia, "followups": followups},
    )


@app.get("/pacientes/{paciente_id}/historia", response_class=HTMLResponse)
def ver_historia(paciente_id: int, request: Request, db: Session = Depends(get_db)):
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
        {"paciente": paciente, "h": historia},
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
    obtener_paciente(db, paciente_id)

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

    db.commit()

    return RedirectResponse(url="/pacientes/" + str(paciente_id), status_code=303)


@app.post("/pacientes/{paciente_id}/citas/nueva")
def nueva_cita(
    paciente_id: int,
    fecha: str = Form(...),
    hora: str = Form(...),
    notas: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    obtener_paciente(db, paciente_id)

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

    return RedirectResponse(url="/pacientes/" + str(cita.paciente_id), status_code=303)


@app.post("/citas/{cita_id}/reagendar")
def reagendar_cita(
    cita_id: int,
    fecha: str = Form(...),
    hora: str = Form(...),
    db: Session = Depends(get_db),
):
    cita_anterior = db.query(models.Cita).filter(models.Cita.id == cita_id).first()
    if not cita_anterior:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    cita_anterior.estado = "cancelada"

    cita_nueva = models.Cita(
        paciente_id=cita_anterior.paciente_id,
        fecha_hora=datetime.fromisoformat(fecha + "T" + hora),
        tipo=cita_anterior.tipo,
        estado="agendada",
        notas_breves=cita_anterior.notas_breves,
    )
    db.add(cita_nueva)
    db.commit()

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


@app.get("/pacientes/{paciente_id}/dieta/nueva")
def generar_dieta(paciente_id: int, db: Session = Depends(get_db)):
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

    resultado_plan = plan_gen.generar_plan(paciente_dict, historia_dict, medicion_dict, padecimientos=padecimientos)
    resultado_doc = redactor.redactar(resultado_plan["plan"], nombre_paciente=paciente.nombre_completo)

    ultima = (
        db.query(models.DietaVersion)
        .filter(models.DietaVersion.paciente_id == paciente_id)
        .order_by(models.DietaVersion.version.desc())
        .first()
    )
    numero_version = (ultima.version + 1) if ultima else 1

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
        version_anterior_id=ultima.id if ultima else None,
    )
    db.add(dieta)
    db.commit()
    db.refresh(dieta)

    return RedirectResponse(url="/pacientes/" + str(paciente_id) + "/dieta/" + str(dieta.id), status_code=303)


@app.get("/pacientes/{paciente_id}/dieta/{dieta_id}", response_class=HTMLResponse)
def ver_dieta(paciente_id: int, dieta_id: int, request: Request, db: Session = Depends(get_db)):
    paciente = obtener_paciente(db, paciente_id)
    dieta = db.query(models.DietaVersion).filter(models.DietaVersion.id == dieta_id).first()
    if not dieta:
        raise HTTPException(status_code=404, detail="Version de dieta no encontrada")

    guardado = _cargar_contenido(dieta)

    return templates.TemplateResponse(
        request,
        "ver_dieta.html",
        {
            "paciente": paciente,
            "dieta": dieta,
            "doc": guardado["documento"],
            "menu": guardado["documento"].get("menu", {}),
            "confiable": guardado.get("confiable", False),
        },
    )


@app.post("/pacientes/{paciente_id}/dieta/{dieta_id}/aprobar")
def aprobar_dieta(paciente_id: int, dieta_id: int, db: Session = Depends(get_db)):
    dieta = db.query(models.DietaVersion).filter(models.DietaVersion.id == dieta_id).first()
    if not dieta:
        raise HTTPException(status_code=404, detail="Version de dieta no encontrada")

    dieta.estado = "aprobada"
    db.commit()

    return RedirectResponse(url="/pacientes/" + str(paciente_id), status_code=303)


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


@app.get("/pacientes/{paciente_id}/dieta/{dieta_id}/pdf")
def descargar_pdf(paciente_id: int, dieta_id: int, db: Session = Depends(get_db)):
    paciente = obtener_paciente(db, paciente_id)
    dieta = db.query(models.DietaVersion).filter(models.DietaVersion.id == dieta_id).first()
    if not dieta:
        raise HTTPException(status_code=404, detail="Version de dieta no encontrada")

    guardado = _cargar_contenido(dieta)
    ruta_pdf = pdf_gen.generar(guardado["documento"], paciente.nombre_completo)

    return FileResponse(ruta_pdf, media_type="application/pdf", filename=os.path.basename(ruta_pdf))
