"""
Integracion con Google Calendar para sincronizar citas del sistema.

Direccion unica: Sistema -> Google. No se lee Google Calendar, no se
detectan cambios hechos directo ahi.

Dos cuentas de Google independientes, cada una con su propio archivo
de token (generado una sola vez via autorizacion manual):

- "privado": maferul2309@gmail.com, calendario privado de Marifer
- "unido":   nutricion.unido@gmail.com, consultas de pacientes de UniDO

El campo origen_consulta del paciente ("privado" / "unido") decide
cual de los dos se usa en cada caso.
"""
import json
import os
import time
from datetime import timedelta

import requests

CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]

CONFIG_CALENDARIOS = {
    "privado": {
        "calendar_id": "maferul2309@gmail.com",
        "token_file": "/opt/sistema-nutricion/google-token-privado.json",
    },
    "unido": {
        "calendar_id": "nutricion.unido@gmail.com",
        "token_file": "/opt/sistema-nutricion/google-token-unido.json",
    },
}


def _leer_token(token_file):
    with open(token_file) as f:
        return json.load(f)


def _guardar_token(token_file, data):
    with open(token_file, "w") as f:
        json.dump(data, f)
    os.chmod(token_file, 0o600)


def _access_token_valido(token_file):
    """Devuelve un access_token vigente, renovandolo si ya vencio o esta por vencer."""
    data = _leer_token(token_file)
    obtenido_en = data.get("obtenido_en", 0)
    vencido = time.time() > obtenido_en + data.get("expires_in", 0) - 120

    if not vencido:
        return data["access_token"]

    respuesta = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": data["refresh_token"],
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    respuesta.raise_for_status()
    nuevo = respuesta.json()

    data["access_token"] = nuevo["access_token"]
    data["expires_in"] = nuevo["expires_in"]
    data["obtenido_en"] = time.time()
    _guardar_token(token_file, data)

    return data["access_token"]


def _config_para(origen_consulta):
    config = CONFIG_CALENDARIOS.get(origen_consulta)
    if not config:
        raise ValueError(f"origen_consulta desconocido: {origen_consulta!r}")
    return config


def crear_evento(origen_consulta, resumen, fecha_hora_inicio, duracion_minutos=60, descripcion=""):
    """
    Crea un evento en el calendario correspondiente a origen_consulta.
    fecha_hora_inicio: datetime naive, se asume America/Mexico_City.
    Devuelve el event_id de Google (guardar en Cita.google_event_id
    para poder borrarlo despues si se cancela o reagenda).
    """
    config = _config_para(origen_consulta)
    token = _access_token_valido(config["token_file"])

    fecha_hora_fin = fecha_hora_inicio + timedelta(minutes=duracion_minutos)

    evento = {
        "summary": resumen,
        "description": descripcion,
        "start": {"dateTime": fecha_hora_inicio.isoformat(), "timeZone": "America/Mexico_City"},
        "end": {"dateTime": fecha_hora_fin.isoformat(), "timeZone": "America/Mexico_City"},
    }

    respuesta = requests.post(
        f"https://www.googleapis.com/calendar/v3/calendars/{config['calendar_id']}/events",
        headers={"Authorization": f"Bearer {token}"},
        json=evento,
        timeout=10,
    )
    respuesta.raise_for_status()
    return respuesta.json()["id"]


def eliminar_evento(origen_consulta, event_id):
    """Borra un evento. Si ya no existe (404/410), lo trata como exito silencioso."""
    if not event_id:
        return

    config = _config_para(origen_consulta)
    token = _access_token_valido(config["token_file"])

    respuesta = requests.delete(
        f"https://www.googleapis.com/calendar/v3/calendars/{config['calendar_id']}/events/{event_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if respuesta.status_code not in (204, 404, 410):
        respuesta.raise_for_status()


def probar_conexion(origen_consulta):
    """Prueba rapida: pide 1 evento del calendario, para confirmar que el token funciona."""
    config = _config_para(origen_consulta)
    token = _access_token_valido(config["token_file"])

    respuesta = requests.get(
        f"https://www.googleapis.com/calendar/v3/calendars/{config['calendar_id']}/events",
        headers={"Authorization": f"Bearer {token}"},
        params={"maxResults": 1},
        timeout=10,
    )
    respuesta.raise_for_status()
    return respuesta.json()
