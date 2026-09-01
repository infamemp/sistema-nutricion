"""
Lectura automatica de reportes de InBody (imagen o foto), para
pacientes de UniDO. Gemini hace la extraccion visual; este modulo
arma el prompt y valida sensatez.

La identificacion del paciente y el guardado en la base de datos se
resuelven en main.py, ya que dependen del expediente que este abierto
en ese momento (el archivo se sube desde dentro del expediente de un
paciente ya elegido, no hace falta buscarlo).
"""

import gemini

PROMPT_EXTRACCION = """
Eres un asistente que lee reportes de composicion corporal InBody (dispositivos InBody370S u otros modelos similares) a partir de una imagen o fotografia.

Devuelve UNICAMENTE un JSON con esta estructura exacta, sin texto adicional antes ni despues:

{
  "id_inbody": "el ID impreso en el reporte, tal cual aparece",
  "nombre_impreso": "el nombre impreso en el reporte, tal cual aparece (puede venir truncado)",
  "edad": numero entero o null,
  "sexo": "Masculino" o "Femenino" o null,
  "estatura_cm": numero (la altura en centimetros) o null,
  "historial": [
    {
      "fecha": "YYYY-MM-DD",
      "peso": numero en kg o null,
      "imc": numero o null,
      "porcentaje_grasa": numero (PGC, porcentaje de grasa corporal) o null,
      "masa_grasa_kg": numero en kg o null,
      "mme": numero en kg (Masa de Musculo Esqueletico) o null,
      "grasa_visceral": numero (nivel de grasa visceral) o null,
      "tasa_metabolica_basal": numero en kcal o null
    }
  ]
}

Reglas importantes:
- El arreglo "historial" debe incluir el registro de la fecha de la prueba actual (usa la fecha impresa como "Fecha / Hora de la prueba"), con TODOS los campos que el reporte muestre para esa fecha.
- Si el reporte tiene ademas una seccion de "Historial de Composicion Corporal" con puntos de fechas anteriores, agregalos tambien como entradas adicionales del arreglo "historial", cada una con su propia fecha. Esas entradas antiguas normalmente solo muestran peso, MME y/o porcentaje de grasa en una grafica de puntos; deja en null cualquier campo que el reporte no muestre para esa fecha especifica, no inventes ni calcules valores que no esten impresos.
- Si algun dato no es legible o no aparece en la imagen, usa null en ese campo especifico, no rechaces el resto del reporte por eso.
- Las fechas en el reporte suelen venir en formato DD.MM.AAAA; conviertelas a YYYY-MM-DD.
- No agregues comentarios, explicaciones, ni texto fuera del JSON.
"""


def procesar_reporte(imagen_bytes, mime_type):
    """
    Envia la imagen a Gemini, extrae los datos, y aplica un chequeo de
    sensatez basico (peso entre 20 y 300 kg) a cada punto del historial,
    descartando solo el campo peso de ese punto si esta fuera de rango
    (probable error de lectura), sin rechazar el punto completo.

    Devuelve el diccionario ya validado. No guarda nada en la base de
    datos ni en el sistema de archivos: eso lo resuelve quien llama a
    esta funcion.
    """
    resultado = gemini.generar_json_con_imagen(PROMPT_EXTRACCION, imagen_bytes, mime_type)

    historial_valido = []
    for punto in resultado.get("historial", []):
        peso = punto.get("peso")
        if peso is not None and not (20 <= peso <= 300):
            punto["peso"] = None
        historial_valido.append(punto)

    resultado["historial"] = historial_valido
    return resultado
