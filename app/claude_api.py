"""
Cliente de la API de Anthropic, capa de redaccion del sistema.

Rol en la arquitectura de dos motores:
  Gemini ANALIZA  -> produce el plan tecnico en JSON
  Claude REDACTA  -> convierte ese plan en el documento con la voz de
                     Marifer

Claude nunca calcula ni decide clinicamente. Recibe un plan ya resuelto y
verificado, y su unico trabajo es escribirlo como lo escribiria ella.

Por que Claude para la redaccion: mejor manejo del matiz, del tono y de
las instrucciones de estilo. El STYLE_SPEC.md tiene decenas de reglas
sobre vocabulario, construcciones y prohibiciones, y respetarlas todas a
la vez es justo donde destaca.

Costo estimado: entre 2 y 5 USD al mes al volumen actual, porque solo
redacta sobre un plan ya hecho, sin cargar la knowledgebase.

La API key se lee de ANTHROPIC_API_KEY en el archivo .env.
"""

import os
import json
import urllib.request
import urllib.error

BASE = "https://api.anthropic.com/v1/messages"
VERSION_API = "2023-06-01"

# Modelo para la redaccion. Se puede cambiar sin tocar el resto del codigo.
MODELO_REDACCION = "claude-sonnet-5"

MODELOS_ALTERNATIVOS = [
    "claude-sonnet-5",
    "claude-opus-5",
    "claude-haiku-4-5-20251001",
]


def _api_key():
    clave = os.environ.get("ANTHROPIC_API_KEY")
    if not clave:
        raise RuntimeError(
            "Falta la variable de entorno ANTHROPIC_API_KEY. "
            "Definirla en el archivo .env del servidor."
        )
    return clave


def _peticion(cuerpo):
    datos = json.dumps(cuerpo).encode("utf-8")
    req = urllib.request.Request(
        BASE,
        data=datos,
        headers={
            "Content-Type": "application/json",
            "x-api-key": _api_key(),
            "anthropic-version": VERSION_API,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            "Error " + str(e.code) + " de la API de Anthropic: " + detalle[:400]
        )


def generar(prompt, sistema=None, modelo=None, temperatura=0.7, max_tokens=8000):
    """
    Envia un prompt a Claude y devuelve el texto de la respuesta.

    sistema: instrucciones de rol y estilo. Aqui es donde va el
    STYLE_SPEC.md, porque son reglas que aplican a toda la respuesta.

    temperatura: 0.7 por defecto. Mas alta que en el analisis, porque la
    redaccion se beneficia de algo de variedad. Las dietas no deben
    sonar identicas entre pacientes.
    """
    cuerpo = {
        "model": modelo or MODELO_REDACCION,
        "max_tokens": max_tokens,
        "temperature": temperatura,
        "messages": [{"role": "user", "content": prompt}],
    }

    if sistema:
        cuerpo["system"] = sistema

    datos = _peticion(cuerpo)

    bloques = datos.get("content", [])
    if not bloques:
        raise RuntimeError("Claude no devolvio contenido: " + json.dumps(datos)[:400])

    texto = "".join(b.get("text", "") for b in bloques if b.get("type") == "text")

    if not texto:
        motivo = datos.get("stop_reason", "desconocido")
        raise RuntimeError("Respuesta vacia de Claude. Motivo: " + str(motivo))

    return texto


def generar_json(prompt, sistema=None, modelo=None, temperatura=0.4, max_tokens=8000):
    """
    Como generar(), pero espera y parsea una respuesta en JSON.
    Reintenta una vez si el JSON viene malformado.
    """
    instruccion = (
        "\n\nResponde unicamente con JSON valido, sin texto antes ni despues, "
        "sin bloques de codigo markdown."
    )

    for intento in range(2):
        texto = generar(
            prompt + instruccion,
            sistema=sistema,
            modelo=modelo,
            temperatura=temperatura,
            max_tokens=max_tokens,
        )

        limpio = texto.strip()
        if limpio.startswith("```"):
            limpio = limpio.split("```")[1]
            if limpio.startswith("json"):
                limpio = limpio[4:]
            limpio = limpio.strip()

        try:
            return json.loads(limpio)
        except json.JSONDecodeError as e:
            if intento == 0:
                continue
            pista = ""
            if "Unterminated" in str(e) or "Expecting" in str(e):
                pista = (
                    " PISTA: el JSON parece cortado. Probablemente excedio "
                    "max_tokens. Subir ese valor."
                )
            raise RuntimeError(
                "Claude devolvio JSON invalido dos veces." + pista
                + " Inicio: " + limpio[:300]
            )


def probar_conexion():
    """Verifica que la clave funcione y el modelo responda."""
    resultado = {"clave_presente": bool(os.environ.get("ANTHROPIC_API_KEY"))}

    if not resultado["clave_presente"]:
        resultado["error"] = "Falta ANTHROPIC_API_KEY en el entorno"
        return resultado

    resultado["modelo_configurado"] = MODELO_REDACCION

    try:
        respuesta = generar(
            "Responde unicamente con la palabra: listo",
            temperatura=0,
            max_tokens=20,
        )
        resultado["prueba_generacion"] = respuesta.strip()[:50]
        resultado["funciona"] = True
    except Exception as e:
        resultado["error_generacion"] = str(e)[:400]
        resultado["funciona"] = False

    return resultado
