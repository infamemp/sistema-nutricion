"""
Generador del PDF del paciente.

Toma el documento ya redactado por Claude y produce la lamina con la
identidad visual de Marifer: fondo verde, tarjetas blancas, su logo, y
el pie con sus datos de contacto.

MAQUETACION DE FLUJO, la decision de diseno central:
Las cajas se dibujan alrededor del texto, no al reves. Se usa WeasyPrint,
que convierte HTML y CSS a PDF, de modo que el motor de renderizado se
encarga de ajustar cada tarjeta a su contenido y paginar cuando no cabe.

Por que importa: en el proceso manual actual, las cajas son de tamano
fijo y el texto se pega dentro. Si crece, se desborda o se corta. Se
observo en material real de la clinica: una guia con el texto cortado a
media frase y tapado por el logo. Con este enfoque, el desbordamiento
deja de ser posible por construccion, no se evita con cuidado.

Paginacion: la maneja WeasyPrint de forma nativa via @page. El fondo
verde, el encabezado y el pie viven en los margenes de la pagina, no en
un contenedor del documento, asi que se repiten correctamente en cada
hoja real. Los bloques llevan break-inside: avoid, de modo que un tiempo
de comida nunca se parte entre dos hojas.
"""

import os
import base64
from datetime import date, datetime
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

BASE_DIR = os.path.dirname(__file__)
RUTA_PLANTILLAS = os.path.join(BASE_DIR, "templates")
# Logo con el tagline vigente "Nutricion y Salud Hormonal".
# NO usar Mafer_Logo_Grande.png: ese trae el tagline antiguo
# "Nutricion y Vida en Equilibrio", que ya no se usa.
RUTA_LOGO = os.path.join(BASE_DIR, "static", "marifer-logo.png")
RUTA_SALIDA = os.path.join(BASE_DIR, "pdfs")

# Datos de contacto confirmados por la nutriologa
PIE_NOMBRE = "Marifer Utrilla Lack"
PIE_TITULO = "Nutrióloga y Especialista en Salud Hormonal, Educadora en Diabetes"
PIE_TELEFONO = "+52 238 390 0875"

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

ORDEN_TIEMPOS = ["desayuno", "colacion", "comida", "cena"]

TITULOS_TIEMPO = {
    "desayuno": "DESAYUNO",
    "colacion": "COLACIÓN",
    "comida": "COMIDA",
    "cena": "CENA",
}


def _fecha_larga(f=None):
    f = f or datetime.now(ZoneInfo("America/Mexico_City")).date()
    return str(f.day) + " de " + MESES[f.month - 1] + " de " + str(f.year)


def _logo_embebido():
    """
    Incrusta el logo en el HTML como data URI, para que el PDF no
    dependa de rutas externas al generarse.

    Detecta el tipo por la extension: el SVG se marca como image/svg+xml
    para que WeasyPrint lo dibuje vectorialmente.
    """
    if not os.path.exists(RUTA_LOGO):
        return None

    tipo = "image/svg+xml" if RUTA_LOGO.lower().endswith(".svg") else "image/png"

    with open(RUTA_LOGO, "rb") as f:
        datos = base64.b64encode(f.read()).decode("ascii")

    return "data:" + tipo + ";base64," + datos


def _armar_bloques(documento):
    """
    Convierte el documento redactado en una lista de bloques ordenados,
    listos para la plantilla.
    """
    bloques = []

    if documento.get("objetivos_clave"):
        bloques.append({
            "tipo": "lista",
            "titulo": "OBJETIVOS CLAVE",
            "elementos": documento["objetivos_clave"],
        })

    if documento.get("suplementacion"):
        bloques.append({
            "tipo": "lista",
            "titulo": "SUPLEMENTACIÓN",
            "elementos": documento["suplementacion"],
        })

    menu = documento.get("menu") or {}
    for tiempo in ORDEN_TIEMPOS:
        datos = menu.get(tiempo)
        if not datos:
            continue
        opciones = datos.get("opciones") or []
        if not opciones:
            continue
        bloques.append({
            "tipo": "menu",
            "titulo": TITULOS_TIEMPO.get(tiempo, tiempo.upper()),
            "instruccion": datos.get("encabezado", ""),
            "opciones": opciones,
        })

    if documento.get("recomendaciones"):
        bloques.append({
            "tipo": "lista",
            "titulo": "RECOMENDACIONES",
            "elementos": documento["recomendaciones"],
        })

    if documento.get("cierre"):
        bloques.append({
            "tipo": "texto",
            "titulo": "PARA TENER PRESENTE",
            "texto": documento["cierre"],
        })

    return bloques


def generar(documento, nombre_paciente, proxima_cita=None,
            fecha_documento=None, ruta_salida=None):
    """
    Genera el PDF del paciente.

    documento: el resultado de redactor.redactar()
    nombre_paciente: como aparecera en el encabezado
    proxima_cita: texto libre, ej. "15 de septiembre de 2026"

    Devuelve la ruta del archivo generado.
    """
    bloques = _armar_bloques(documento)
    if not bloques:
        raise ValueError("El documento no tiene contenido que imprimir.")

    entorno = Environment(loader=FileSystemLoader(RUTA_PLANTILLAS))
    plantilla = entorno.get_template("plan_pdf.html")

    html = plantilla.render(
        bloques=bloques,
        paciente=nombre_paciente,
        fecha=_fecha_larga(fecha_documento),
        proxima_cita=proxima_cita,
        logo=_logo_embebido(),
        pie_nombre=PIE_NOMBRE,
        pie_titulo=PIE_TITULO,
        pie_telefono=PIE_TELEFONO,
    )

    if not ruta_salida:
        os.makedirs(RUTA_SALIDA, exist_ok=True)
        limpio = "".join(
            c for c in nombre_paciente if c.isalnum() or c in (" ", "_")
        ).strip().replace(" ", "_")
        nombre = "plan_" + limpio + "_" + datetime.now(ZoneInfo("America/Mexico_City")).date().isoformat() + ".pdf"
        ruta_salida = os.path.join(RUTA_SALIDA, nombre)

    HTML(string=html, base_url=BASE_DIR).write_pdf(ruta_salida)

    return ruta_salida


def generar_html(documento, nombre_paciente, proxima_cita=None,
                 fecha_documento=None):
    """
    Devuelve el HTML sin convertirlo a PDF.
    Util para la vista previa en pantalla antes de aprobar.
    """
    bloques = _armar_bloques(documento)

    entorno = Environment(loader=FileSystemLoader(RUTA_PLANTILLAS))
    plantilla = entorno.get_template("plan_pdf.html")

    return plantilla.render(
        bloques=bloques,
        paciente=nombre_paciente,
        fecha=_fecha_larga(fecha_documento),
        proxima_cita=proxima_cita,
        logo=_logo_embebido(),
        pie_nombre=PIE_NOMBRE,
        pie_titulo=PIE_TITULO,
        pie_telefono=PIE_TELEFONO,
    )
