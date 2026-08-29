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

    return templates.TemplateResponse(
        request,
        "expediente.html",
        {"paciente": paciente, "citas": citas, "historia": historia},
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
