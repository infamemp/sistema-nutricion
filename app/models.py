from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Paciente(Base):
    __tablename__ = "pacientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre_completo = Column(String, nullable=False)
    fecha_nacimiento = Column(Date)
    sexo = Column(String)
    celular = Column(String)
    correo_electronico = Column(String)
    profesion = Column(String)
    motivo_consulta = Column(Text)
    referido_por = Column(String)
    fecha_alta = Column(DateTime, default=datetime.utcnow)
    activo = Column(Integer, default=1)
    origen_consulta = Column(String, default="privado")
    estatura = Column(Float)

    historia_clinica = relationship("HistoriaClinica", back_populates="paciente", uselist=False)
    mediciones_inbody = relationship("MedicionInBody", back_populates="paciente")
    ids_inbody = relationship("IdInBodyConocido", back_populates="paciente")
    follow_ups = relationship("FollowUp", back_populates="paciente")
    dietas = relationship("DietaVersion", back_populates="paciente")
    laboratorios = relationship("Laboratorio", back_populates="paciente")
    citas = relationship("Cita", back_populates="paciente")
    notas = relationship("NotaPaciente", back_populates="paciente")


class HistoriaClinica(Base):
    __tablename__ = "historias_clinicas"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), unique=True, nullable=False)

    objetivo_que_espera = Column(Text)
    objetivo_tiempo = Column(Text)
    objetivo_importante = Column(Text)

    antecedente_diabetes = Column(Text)
    antecedente_obesidad = Column(Text)
    antecedente_tiroides = Column(Text)
    antecedente_hipertension = Column(Text)
    antecedente_cardiovascular = Column(Text)
    antecedente_cancer = Column(Text)
    antecedente_otros = Column(Text)

    padecimientos_diagnosticados = Column(Text)
    cirugias = Column(Text)
    tratamiento_medico_actual = Column(Text)

    gineco_menarca = Column(String)
    gineco_ciclo = Column(Text)
    gineco_anticonceptivo = Column(String)
    gineco_embarazos = Column(Text)
    gineco_busca_embarazo = Column(String)
    gineco_menopausia = Column(String)

    peso_maximo = Column(Float)
    peso_minimo = Column(Float)
    edad_inicio_sobrepeso = Column(String)
    dietas_previas = Column(Text)

    sint_gastrointestinal = Column(Text)
    sint_distension = Column(Text)
    sint_hormigueo = Column(Text)
    sint_caida_pelo = Column(Text)
    sint_unas_debiles = Column(Text)
    sint_dolor_cabeza = Column(Text)
    sint_memoria = Column(Text)
    sint_fatiga = Column(Text)
    sint_piel_seca = Column(Text)
    sint_acantosis = Column(Text)
    sint_otro = Column(Text)

    alergias = Column(Text)
    intolerancias = Column(Text)
    alimentos_evitar = Column(Text)
    restricciones_eleccion = Column(Text)

    recordatorio_desayuno = Column(Text)
    recordatorio_comida = Column(Text)
    recordatorio_cena = Column(Text)
    recordatorio_snacks = Column(Text)
    hidratacion = Column(String)
    quien_cocina = Column(Text)

    ejercicio_rutina = Column(Text)
    alcohol = Column(String)
    tabaco = Column(String)
    sueno = Column(Text)
    nivel_estres = Column(Integer)

    suplementos = Column(Text)
    medicamentos = Column(Text)

    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    paciente = relationship("Paciente", back_populates="historia_clinica")


class MedicionInBody(Base):
    __tablename__ = "mediciones_inbody"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    fecha_medicion = Column(DateTime, default=datetime.utcnow)
    peso = Column(Float)
    imc = Column(Float)
    porcentaje_grasa = Column(Float)
    masa_grasa_kg = Column(Float)
    mme = Column(Float)
    grasa_visceral = Column(Float)
    tasa_metabolica_basal = Column(Float)
    origen = Column(String, default="manual")
    pdf_original_path = Column(String)
    id_inbody_reporte = Column(String)

    paciente = relationship("Paciente", back_populates="mediciones_inbody")


class IdInBodyConocido(Base):
    __tablename__ = "ids_inbody_conocidos"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    id_inbody = Column(String, nullable=False)
    clinica = Column(String)
    fecha_primer_uso = Column(DateTime, default=datetime.utcnow)

    paciente = relationship("Paciente", back_populates="ids_inbody")


class FollowUp(Base):
    __tablename__ = "follow_ups"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    numero_consulta = Column(Integer)
    fecha_consulta = Column(DateTime, default=datetime.utcnow)
    proxima_cita = Column(Date)
    porcentaje_apego = Column(Float)
    promedio_dias_ejercicio = Column(Float)
    que_le_gusto = Column(Text)
    que_no_le_gusto = Column(Text)
    cambios_que_hizo = Column(Text)
    en_que_puede_mejorar = Column(Text)
    estatus_tratamiento_medico = Column(Text)
    notas_libres = Column(Text)
    ajustes_acordados = Column(Text)
    medicion_inbody_id = Column(Integer, ForeignKey("mediciones_inbody.id"), nullable=True)

    paciente = relationship("Paciente", back_populates="follow_ups")


class DietaVersion(Base):
    __tablename__ = "dietas_versiones"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    version = Column(Integer, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    contenido = Column(Text)
    estado = Column(String, default="borrador_ia")
    creado_por = Column(String)
    instruccion_ajuste = Column(Text)
    version_anterior_id = Column(Integer, ForeignKey("dietas_versiones.id"), nullable=True)
    tipo_documento = Column(String, default="menu")

    paciente = relationship("Paciente", back_populates="dietas")
    opciones = relationship("OpcionPrescrita", back_populates="dieta")


class OpcionPrescrita(Base):
    __tablename__ = "opciones_prescritas"

    id = Column(Integer, primary_key=True, index=True)
    dieta_id = Column(Integer, ForeignKey("dietas_versiones.id"), nullable=False)
    tipo_comida = Column(String)
    descripcion = Column(Text)
    fecha_prescrita = Column(DateTime, default=datetime.utcnow)

    dieta = relationship("DietaVersion", back_populates="opciones")


class Laboratorio(Base):
    __tablename__ = "laboratorios"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    fecha_subida = Column(DateTime, default=datetime.utcnow)
    archivo_path = Column(String)
    analisis_ia = Column(Text)

    paciente = relationship("Paciente", back_populates="laboratorios")


class Cita(Base):
    __tablename__ = "citas"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    fecha_hora = Column(DateTime, nullable=False)
    tipo = Column(String, default="primera_consulta")
    estado = Column(String, default="agendada")
    notas_breves = Column(Text)
    google_event_id = Column(String, nullable=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    paciente = relationship("Paciente", back_populates="citas")


class NotaPaciente(Base):
    __tablename__ = "notas_pacientes"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    texto = Column(Text, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    paciente = relationship("Paciente", back_populates="notas")
