"""
Cliente de la API de Gemini, capa de analisis del sistema.

Rol en la arquitectura de dos motores:
  Gemini ANALIZA  -> lee el expediente, la knowledgebase y las reglas
                     clinicas, y produce un plan tecnico estructurado.
  Claude REDACTA  -> toma ese plan y escribe el documento en la voz de
                     Marifer.

La frontera entre ambos es un documento estructurado (JSON), no prosa.
Gemini nunca escribe para el paciente; Claude nunca calcula ni decide
clinicamente.

Por que Gemini para el analisis: ventana de contexto de 1M tokens en
todos sus modelos, lectura nativa de PDFs e imagenes, y costo bajo. Eso
permite inyectar la knowledgebase completa del caso sin fragmentarla,
y tambien leer reportes de InBody adjuntos como imagen.

NOTA SOBRE MODELOS (verificado ago 2026):
- Gemini 2.5 Flash se descontinua el 16 de octubre de 2026. No usar.
- La generacion vigente es la 3.x. El modelo se define en MODELO_ANALISIS
  y se puede cambiar sin tocar el resto del codigo.
- Usar listar_modelos() para ver que hay disponible con la clave actual.
- gemini-3.8-flash es multimodal (texto + imagen en la misma peticion),
  se reutiliza el mismo modelo para leer reportes de InBody.

La API key se lee de GEMINI_API_KEY en el archivo .env, nunca del codigo.
"""

import os
import json
import base64
import urllib.request
import urllib.error

BASE = "https://generativelanguage.googleapis.com/v1beta"

# Modelo para el analisis. Cambiar aqui si Google descontinua o mejora.
MODELO_ANALISIS = "gemini-3.8-flash"

# Alternativas conocidas, por si el alias deja de funcionar.
MODELOS_ALTERNATIVOS = [
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-flash-lite-latest",
]


def _api_key():
    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        raise RuntimeError(
            "Falta la variable de entorno GEMINI_API_KEY. "
            "Definirla en el archivo .env del servidor."
        )
    return clave


def _peticion(url, cuerpo=None):
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo else None
    req = urllib.request.Request(
        url,
        data=datos,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": _api_key(),
        },
        method="POST" if cuerpo else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", errors="replace")
        raise RuntimeError("Error " + str(e.code) + " de la API de Gemini: " + detalle)


def listar_modelos():
    """
    Devuelve los modelos disponibles con la clave actual.
    Util para saber que nombres exactos usar sin adivinar.
    """
    datos = _peticion(BASE + "/models")
    modelos = []
    for m in datos.get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            modelos.append({
                "nombre": m.get("name", "").replace("models/", ""),
                "titulo": m.get("displayName"),
                "contexto_entrada": m.get("inputTokenLimit"),
                "contexto_salida": m.get("outputTokenLimit"),
            })
    return modelos


def _generar_parts(parts, modelo=None, json_estricto=False, temperatura=0.4):
    """
    Version de bajo nivel: envia una lista de "parts" ya armada (texto,
    imagen, o ambos) y devuelve el texto de la respuesta. generar() y
    generar_con_imagen() son atajos sobre esta funcion.
    """
    modelo = modelo or MODELO_ANALISIS
    url = BASE + "/models/" + modelo + ":generateContent"

    cuerpo = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": temperatura,
            "maxOutputTokens": 32768,
        },
    }

    if json_estricto:
        cuerpo["generationConfig"]["responseMimeType"] = "application/json"

    datos = _peticion(url, cuerpo)

    candidatos = datos.get("candidates", [])
    if not candidatos:
        raise RuntimeError("Gemini no devolvio ninguna respuesta: " + json.dumps(datos)[:500])

    partes = candidatos[0].get("content", {}).get("parts", [])
    texto = "".join(p.get("text", "") for p in partes)

    if not texto:
        motivo = candidatos[0].get("finishReason", "desconocido")
        raise RuntimeError("Respuesta vacia de Gemini. Motivo: " + str(motivo))

    return texto


def generar(prompt, modelo=None, json_estricto=False, temperatura=0.4):
    """
    Envia un prompt de solo texto a Gemini y devuelve el texto de la
    respuesta.

    json_estricto: fuerza a que la respuesta sea JSON valido. Es lo que
    usamos para el plan tecnico, porque ese documento lo consume Claude
    despues, no un humano.
    """
    return _generar_parts(
        [{"text": prompt}], modelo=modelo, json_estricto=json_estricto, temperatura=temperatura
    )


def generar_con_imagen(prompt, imagen_bytes, mime_type, modelo=None, json_estricto=False, temperatura=0.2):
    """
    Como generar(), pero adjunta una imagen junto con el prompt de texto.
    Se usa para leer reportes de InBody (fotografia o captura de pantalla).

    imagen_bytes: contenido crudo del archivo, sin decodificar.
    mime_type: ej. "image/jpeg", "image/png".
    """
    imagen_b64 = base64.b64encode(imagen_bytes).decode("ascii")
    parts = [
        {"text": prompt},
        {"inline_data": {"mime_type": mime_type, "data": imagen_b64}},
    ]
    return _generar_parts(parts, modelo=modelo, json_estricto=json_estricto, temperatura=temperatura)


def _parsear_json_con_reintento(generador_texto):
    """
    Corre generador_texto() (una funcion sin argumentos que ya trae el
    prompt/imagen aplicados) y parsea el resultado como JSON. Si viene
    malformado, reintenta una vez mas antes de rendirse.
    """
    for intento in range(2):
        texto = generador_texto()
        try:
            return json.loads(texto)
        except json.JSONDecodeError as e:
            if intento == 0:
                continue
            pista = ""
            if "Unterminated" in str(e) or "Expecting" in str(e):
                pista = (
                    " PISTA: el JSON parece cortado a la mitad. Probablemente "
                    "la respuesta excedio maxOutputTokens. Subir ese valor en "
                    "gemini.py (el modelo admite hasta 65536)."
                )
            raise RuntimeError(
                "Gemini devolvio JSON invalido dos veces." + pista
                + " Inicio de la respuesta: " + texto[:300]
            )


def generar_json(prompt, modelo=None, temperatura=0.4):
    """
    Como generar(), pero devuelve el resultado ya parseado como
    diccionario. Si el JSON viene malformado, reintenta una vez.
    """
    return _parsear_json_con_reintento(
        lambda: generar(prompt, modelo=modelo, json_estricto=True, temperatura=temperatura)
    )


def generar_json_con_imagen(prompt, imagen_bytes, mime_type, modelo=None, temperatura=0.2):
    """
    Como generar_json(), pero adjuntando una imagen (ej. reporte de
    InBody). Si el JSON viene malformado, reintenta una vez.
    """
    return _parsear_json_con_reintento(
        lambda: generar_con_imagen(
            prompt, imagen_bytes, mime_type, modelo=modelo, json_estricto=True, temperatura=temperatura
        )
    )


def probar_conexion():
    """
    Verifica que la clave funcione y que el modelo configurado responda.
    Devuelve un diccionario con el diagnostico.
    """
    resultado = {"clave_presente": bool(os.environ.get("GEMINI_API_KEY"))}

    if not resultado["clave_presente"]:
        resultado["error"] = "Falta GEMINI_API_KEY en el entorno"
        return resultado

    try:
        modelos = listar_modelos()
        resultado["modelos_disponibles"] = len(modelos)
        nombres = [m["nombre"] for m in modelos]
        resultado["modelo_configurado"] = MODELO_ANALISIS
        resultado["modelo_configurado_existe"] = MODELO_ANALISIS in nombres
    except Exception as e:
        resultado["error_listado"] = str(e)[:300]
        return resultado

    try:
        respuesta = generar("Responde unicamente con la palabra: listo")
        resultado["prueba_generacion"] = respuesta.strip()[:50]
        resultado["funciona"] = True
    except Exception as e:
        resultado["error_generacion"] = str(e)[:300]
        resultado["funciona"] = False

    return resultado
