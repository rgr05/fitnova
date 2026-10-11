"""
Fitnova · Procesado de noticias con la IA de Claude.

Para cada noticia, Claude:
  - decide si es relevante para Fitnova (fitness, nutrición, sueño, salud mental, autocuidado),
  - escribe un titular natural en español y una entradilla,
  - la clasifica en una categoría,
  - redacta una explicación en tres partes: qué dice, contexto y "ten en cuenta",
  - le da una puntuación de importancia (para elegir los destacados de la semana).

Necesita la variable de entorno ANTHROPIC_API_KEY (en GitHub: un "secret" del repositorio).
Si no está, Fitnova sigue funcionando solo con traducción automática.
"""

import json
import os
import re

MODELO = os.environ.get("FITNOVA_MODELO", "claude-haiku-5-5")
CATEGORIAS = ["Entrenamiento", "Nutrición", "Sueño", "Salud mental", "Salud general"]

INSTRUCCIONES = f"""Eres el editor de Fitnova, una web en español que explica a personas corrientes las noticias
de fitness, nutrición, sueño, salud mental y autocuidado. Recibes el titular y la entradilla de una
noticia publicada por otro medio (en cualquier idioma) y preparas la ficha de Fitnova.

Reglas importantes:
- Usa SOLO la información que te doy sobre la noticia. No inventes cifras, nombres, revistas ni
  resultados del estudio. Si la entradilla es corta, dilo con naturalidad en vez de rellenar.
- En "contexto" puedes explicar conocimiento general bien establecido sobre el tema, pero sin
  presentarlo como resultado de este estudio.
- En "ten_en_cuenta" señala las limitaciones razonables (por ejemplo: un solo estudio, estudio en
  animales, estudio observacional que no demuestra causa, falta de detalles en la noticia).
- No des consejos médicos personales. Tono claro, cercano y riguroso. Español de España neutro.
- Es "relevante" solo si interesa a alguien que quiere cuidar su salud física o mental en el día a
  día (ejercicio, alimentación, descanso, bienestar, prevención). NO son relevantes: noticias de
  empresas, aperturas de gimnasios, juicios, política, deporte profesional, ofertas de empleo,
  sucesos, ganadería o temas sin aplicación para el lector.
- "puntuacion" del 1 al 10: cuánto le importaría al lector medio (10 = hallazgo sólido y útil).

Responde SOLO con un objeto JSON válido, sin texto antes ni después, con esta forma:
{{
  "relevante": true,
  "titulo": "titular en español, natural, máximo 110 caracteres, sin clickbait",
  "resumen": "entradilla de 1-2 frases (máximo 260 caracteres)",
  "categoria": "una de: {', '.join(CATEGORIAS)}",
  "que_dice": "2-4 frases: qué cuenta la noticia",
  "contexto": "2-4 frases: por qué importa y qué se sabe en general del tema",
  "ten_en_cuenta": "1-3 frases: limitaciones y matices",
  "puntuacion": 7
}}
Si no es relevante, devuelve igualmente el JSON completo con "relevante": false."""


def disponible() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


_cliente = None


def _cliente_anthropic():
    global _cliente
    if _cliente is None:
        import anthropic   # solo se importa si hay clave
        _cliente = anthropic.Anthropic(max_retries=3, timeout=60)
    return _cliente


def _extraer_json(texto: str) -> dict:
    """Saca el objeto JSON de la respuesta aunque venga con algún texto alrededor."""
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fin == -1:
        raise ValueError("la respuesta no contiene JSON")
    return json.loads(texto[inicio:fin + 1])


def _validar(datos: dict) -> dict:
    """Comprueba la respuesta y la deja limpia y con tipos correctos."""
    obligatorios = ["relevante", "titulo", "resumen", "categoria", "que_dice", "contexto", "ten_en_cuenta", "puntuacion"]
    faltan = [campo for campo in obligatorios if campo not in datos]
    if faltan:
        raise ValueError(f"faltan campos: {faltan}")
    categoria = datos["categoria"] if datos["categoria"] in CATEGORIAS else "Salud general"
    try:
        puntuacion = max(1, min(10, int(datos["puntuacion"])))
    except (TypeError, ValueError):
        puntuacion = 5
    limpio = lambda t: re.sub(r"\s+", " ", str(t or "")).strip()
    return {
        "relevante": bool(datos["relevante"]),
        "titulo": limpio(datos["titulo"])[:140],
        "resumen": limpio(datos["resumen"])[:320],
        "categoria": categoria,
        "explicacion": {
            "que_dice": limpio(datos["que_dice"]),
            "contexto": limpio(datos["contexto"]),
            "ten_en_cuenta": limpio(datos["ten_en_cuenta"]),
        },
        "puntuacion": puntuacion,
    }


def procesar(noticia: dict) -> dict:
    """Envía la noticia a Claude y devuelve los campos nuevos. Lanza una excepción si falla."""
    entrada = (
        f"Idioma original: {noticia['idioma']}\n"
        f"Medio: {noticia['fuente']}\n"
        f"Titular: {noticia['titulo_original']}\n"
        f"Entradilla: {noticia['resumen_original'] or '(el medio no incluye entradilla)'}"
    )
    respuesta = _cliente_anthropic().messages.create(
        model=MODELO,
        max_tokens=900,
        system=INSTRUCCIONES,
        messages=[{"role": "user", "content": entrada}],
    )
    texto = "".join(bloque.text for bloque in respuesta.content if bloque.type == "text")
    return _validar(_extraer_json(texto))
