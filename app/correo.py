"""
Envio de correos del sistema, via Resend.

Se cambio de SMTP directo a Resend porque DigitalOcean bloquea por
politica los puertos 25, 465 y 587 en todos sus droplets, para evitar
abuso de spam en su plataforma. Resend evita el problema por completo:
se conecta via su API sobre HTTPS (puerto 443, siempre abierto), no por
SMTP tradicional.

Sirve para dos cosas: el enlace de recuperacion de contraseña, y mas
adelante el envio de la dieta al paciente.

Variable de entorno requerida en .env:
  RESEND_API_KEY

Remitente: requiere que el dominio mafernut.com este verificado en el
panel de Resend (registros DNS en Cloudflare). Antes de verificarlo,
solo se puede enviar de prueba con el dominio resend.dev.
"""

import os
import base64

import resend

REMITENTE = "Marifer Utrilla <contacto@mafernut.com>"


def _configurar():
    clave = os.environ.get("RESEND_API_KEY")
    if not clave:
        raise RuntimeError(
            "Falta la variable de entorno RESEND_API_KEY. "
            "Definirla en el archivo .env del servidor."
        )
    resend.api_key = clave


def enviar(destinatario, asunto, cuerpo_html, cuerpo_texto=None, adjunto_ruta=None):
    """
    Envia un correo via Resend.

    adjunto_ruta: ruta a un archivo local para adjuntar (ej. el PDF de
    la dieta). Opcional. Resend pide el contenido en base64.
    """
    _configurar()

    parametros = {
        "from": REMITENTE,
        "to": [destinatario],
        "subject": asunto,
        "html": cuerpo_html,
    }

    if cuerpo_texto:
        parametros["text"] = cuerpo_texto

    if adjunto_ruta and os.path.exists(adjunto_ruta):
        with open(adjunto_ruta, "rb") as f:
            contenido_b64 = base64.b64encode(f.read()).decode("ascii")
        parametros["attachments"] = [{
            "filename": os.path.basename(adjunto_ruta),
            "content": contenido_b64,
        }]

    return resend.Emails.send(parametros)


def enviar_recuperacion(destinatario, enlace):
    """Correo con el enlace de un solo uso para restablecer la contraseña."""
    asunto = "Restablecer contraseña, Sistema de Marifer"

    texto = (
        "Se solicito restablecer la contraseña del sistema.\n\n"
        "Abre este enlace para elegir una nueva (valido por 30 minutos):\n"
        + enlace + "\n\n"
        "Si tu no lo solicitaste, ignora este correo."
    )

    html = (
        "<p>Se solicitó restablecer la contraseña del sistema.</p>"
        "<p><a href='" + enlace + "' "
        "style='background:#1E8B3C;color:#fff;padding:10px 20px;"
        "border-radius:6px;text-decoration:none;'>Elegir nueva contraseña</a></p>"
        "<p style='color:#888;font-size:13px;'>Válido por 30 minutos. "
        "Si tú no lo solicitaste, ignora este correo.</p>"
    )

    return enviar(destinatario, asunto, html, cuerpo_texto=texto)


def probar_conexion(destinatario_prueba=None):
    """
    Verifica que la clave funcione. Si se da destinatario_prueba, manda
    un correo real de prueba usando el dominio resend.dev (funciona
    incluso antes de verificar mafernut.com).
    """
    try:
        _configurar()

        if not destinatario_prueba:
            return {"clave_presente": True, "prueba_enviada": False}

        resultado = resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": [destinatario_prueba],
            "subject": "Prueba, Sistema de Marifer",
            "html": "<p>Si ves esto, Resend esta funcionando correctamente.</p>",
        })

        return {"clave_presente": True, "prueba_enviada": True, "id": resultado.get("id")}

    except Exception as e:
        return {"clave_presente": bool(os.environ.get("RESEND_API_KEY")), "error": str(e)[:300]}
