"""
Analisis de resultados de laboratorio (PDF o imagen) via Gemini.

A diferencia de InBody (formato fijo, 7 numeros), un laboratorio no
tiene una forma predecible: puede ser quimica sanguinea, perfil de
lipidos, perfil tiroideo, biometria hematica, perfil hormonal, etc.
Por eso la salida es texto en prosa para que Marifer lo lea, no un
JSON de campos fijos.

El archivo original NUNCA se guarda (decision explicita, igual que
InBody): solo se conserva el analisis redactado por Gemini.
"""

import gemini

PROMPT_ANALISIS = """
Eres un asistente que apoya a Marifer Utrilla, nutrióloga especializada en obesidad, diabetes, resistencia a la insulina, SOP, endometriosis, salud hormonal, fertilidad y embarazo, a interpretar resultados de laboratorio desde el punto de vista NUTRICIONAL.

Vas a recibir una imagen o PDF de un resultado de laboratorio (puede ser química sanguínea, perfil de lípidos, perfil tiroideo, biometría hemática, perfil hormonal, u otro tipo de estudio).

Escribe un análisis breve y claro, en español, dirigido a la nutrióloga (no al paciente), con esta estructura:

1. Un resumen de 1-2 frases del tipo de estudio y de qué fecha es (si aparece).
2. Los valores que estén fuera de rango de referencia (si los hay), cada uno con su valor, el rango normal, y si está alto o bajo.
3. Qué podría implicar cada hallazgo desde el punto de vista NUTRICIONAL (nunca diagnostiques ni sugieras un padecimiento; describe la relevancia nutricional, por ejemplo "una glucosa elevada sugiere reforzar el control de carbohidratos" en vez de "esto indica diabetes").
4. Si algo requiere atención médica y no nutricional, dilo explícitamente y con claridad, para que ella lo derive.

Si no logras leer el documento con claridad, o no reconoces qué tipo de estudio es, dilo directamente en vez de inventar valores.

No uses formato JSON. Responde en texto corrido con párrafos cortos, como si le estuvieras platicando el resumen a la nutrióloga.
"""


def analizar(archivo_bytes, mime_type):
    """
    Envia el laboratorio a Gemini y devuelve el analisis en texto.
    No guarda nada en la base de datos ni en el sistema de archivos:
    eso lo resuelve quien llama a esta funcion, una vez que Marifer
    confirme que quiere guardarlo.
    """
    return gemini.generar_con_imagen(PROMPT_ANALISIS, archivo_bytes, mime_type)
