from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import Optional

from database import get_db, engine
import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")


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
