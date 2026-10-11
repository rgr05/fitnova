"""
Sudor y Ciencia · Procesado de noticias con la IA de Claude.

Para cada noticia, Claude:
  - decide si es relevante para Sudor y Ciencia (fitness, nutrición, sueño, salud mental, autocuidado),
  - escribe un titular natural en español y una entradilla,
  - la clasifica en una categoría,
  - redacta una explicación en tres partes: qué dice, contexto y "ten en cuenta",
  - le da una puntuación de importancia (para elegir los destacados de la semana).

Necesita la variable de entorno ANTHROPIC_API_KEY (en GitHub: un "secret" del repositorio).
Si no está, Sudor y Ciencia sigue funcionando solo con traducción automática.
"""

import json
import os
import re

# Si cambian las instrucciones, sube VERSION: las noticias recientes se vuelven a procesar.
VERSION = 2
MODELO = os.environ.get("FITNOVA_MODELO", "claude-haiku-5-5")
CATEGORIAS = ["Entrenamiento", "Nutrición", "Sueño", "Salud mental", "Salud general"]

INSTRUCCIONES = f"""Eres el editor de Sudor y Ciencia, una web en español que explica a personas corrientes las noticias
de fitness, nutrición, sueño, salud mental y autocuidado. Recibes el titular y la entradilla de una
noticia publicada por otro medio (en cualquier idioma) y preparas la ficha de Sudor y Ciencia.

La fiabilidad es lo más importante, por encima de que la ficha resulte atractiva:
- Usa SOLO la información que te doy sobre la noticia. No inventes ni deduzcas cifras, porcentajes,
  tamaños de muestra, nombres, universidades, revistas, fechas ni resultados.
- En "titulo", "resumen" y "que_dice" no escribas ningún número que no aparezca literalmente en el
  titular o la entradilla originales.
- Si la entradilla es corta o falta, "que_dice" debe limitarse a lo que dice el titular y decir con
  naturalidad que la noticia original no da más detalles.
- No exageres: usa verbos prudentes ("sugiere", "se asocia con", "según el estudio") salvo que la
  fuente hable de algo plenamente establecido. Una asociación no es una causa.
- En "contexto" explica solo conocimiento general sólido y ampliamente aceptado (el que recogen la
  OMS o las sociedades científicas), sin cifras concretas salvo que sean recomendaciones oficiales muy
  conocidas, y sin presentarlo como resultado de este estudio. Si no estás seguro de algo, no lo digas.
- En "ten_en_cuenta" señala las limitaciones razonables: un solo estudio, estudio en animales o
  células, estudio observacional que no demuestra causa, muestra pequeña, falta de detalles en la
  noticia, o que conviene consultar a un profesional.
- "tipo_estudio": elige entre "ensayo en humanos", "estudio observacional", "revisión o metaanálisis",
  "estudio en animales o células", "opinión o recomendación" o "no especificado". Usa "no especificado"
  si la noticia no lo deja claro: no lo adivines.
- No des consejos médicos personales. Tono claro, cercano y riguroso. Español de España neutro.
- Es "relevante" solo si interesa a alguien que quiere cuidar su salud física o mental en el día a
  día (ejercicio, alimentación, descanso, bienestar, prevención). NO son relevantes: noticias de
  empresas, aperturas de gimnasios, juicios, política, deporte profesional, ofertas de empleo,
  sucesos, ganadería, publicidad de productos, pseudociencias o temas sin aplicación para el lector.
- "puntuacion" del 1 al 10: cuánto le importaría al lector medio y cuán sólida parece la evidencia
  (10 = hallazgo sólido y útil; un estudio en animales o una noticia sin detalles no pasa de 5).

Responde SOLO con un objeto JSON válido, sin texto antes ni después, con esta forma:
{{
  "relevante": true,
  "titulo": "titular en español, natural, máximo 110 caracteres, sin clickbait",
  "resumen": "entradilla de 1-2 frases (máximo 260 caracteres)",
  "categoria": "una de: {', '.join(CATEGORIAS)}",
  "tipo_estudio": "no especificado",
  "que_dice": "2-4 frases (máximo 70 palabras): qué cuenta la noticia",
  "contexto": "2-4 frases (máximo 70 palabras): por qué importa y qué se sabe en general del tema",
  "ten_en_cuenta": "1-3 frases (máximo 50 palabras): limitaciones y matices",
  "puntuacion": 6
}}
Si no es relevante, devuelve igualmente el JSON completo con "relevante": false."""

TIPOS_ESTUDIO = ["ensayo en humanos", "estudio observacional", "revisión o metaanálisis",
                 "estudio en animales o células", "opinión o recomendación", "no especificado"]


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
    tipo = str(datos.get("tipo_estudio", "")).strip().lower()
    return {
        "tipo_estudio": tipo if tipo in TIPOS_ESTUDIO else "no especificado",
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


def _numeros(texto: str) -> set[str]:
    """Cifras de un texto, normalizadas: '1,5' y '1.5' -> '1.5'; '7.000' y '7000' -> '7000'."""
    cifras = set()
    for cifra in re.findall(r"\d+(?:[.,]\d+)*", texto or ""):
        partes = re.split(r"[.,]", cifra)
        if len(partes) > 1 and all(len(p) == 3 for p in partes[1:]):
            cifras.add("".join(partes))                 # separador de miles
        else:
            cifras.add(cifra.replace(",", "."))
    return cifras


def cifras_inventadas(resultado: dict, noticia: dict) -> set[str]:
    """Cifras que la IA ha escrito en titular, entradilla o 'qué dice' y que no están en el original."""
    originales = _numeros(noticia["titulo_original"] + " " + noticia["resumen_original"])
    escritas = _numeros(" ".join([resultado["titulo"], resultado["resumen"], resultado["explicacion"]["que_dice"]]))
    return escritas - originales


def _pedir(entrada: str) -> dict:
    respuesta = _cliente_anthropic().messages.create(
        model=MODELO,
        max_tokens=2500,
        system=INSTRUCCIONES,
        messages=[{"role": "user", "content": entrada}],
    )
    if respuesta.stop_reason == "max_tokens":
        raise ValueError("respuesta cortada por longitud")
    texto = "".join(bloque.text for bloque in respuesta.content if bloque.type == "text")
    return _validar(_extraer_json(texto))


def procesar(noticia: dict) -> dict:
    """Envía la noticia a Claude y devuelve los campos nuevos. Lanza una excepción si falla.

    Protección contra datos inventados: si la ficha contiene cifras que no están en la noticia
    original, se pide de nuevo avisando del problema. Si vuelve a ocurrir, se descarta la
    explicación (la noticia se publica solo con titular y entradilla, y no se indexa en Google)."""
    entrada = (
        f"Idioma original: {noticia['idioma']}\n"
        f"Medio: {noticia['fuente']}\n"
        f"Titular: {noticia['titulo_original']}\n"
        f"Entradilla: {noticia['resumen_original'] or '(el medio no incluye entradilla)'}"
    )
    resultado = _pedir(entrada)
    inventadas = cifras_inventadas(resultado, noticia)
    if inventadas:
        resultado = _pedir(entrada + "\n\nATENCIÓN: en un intento anterior escribiste cifras que no están en la "
                           f"noticia original ({', '.join(sorted(inventadas))}). No uses ninguna cifra que no "
                           "aparezca literalmente en el titular o la entradilla.")
        inventadas = cifras_inventadas(resultado, noticia)
    if inventadas:
        resultado["explicacion"] = None
        resultado["revision_necesaria"] = f"cifras no presentes en el original: {', '.join(sorted(inventadas))}"
        resultado["titulo"] = ""   # se usará la traducción automática del titular
    return resultado
