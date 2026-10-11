"""
Fitnova · Recopilador de noticias de fitness, salud y autocuidado.

Qué hace, paso a paso:
  1. Lee los feeds RSS de feeds.json (en cualquier idioma).
  2. Limpia cada noticia y descarta las antiguas y las repetidas.
  3. Traduce título y resumen al español (solo las noticias nuevas).
  4. Clasifica cada noticia en una categoría.
  5. Guarda todo en data/noticias.json y genera la web en site/index.html.

Uso:
  python fitnova.py          -> ejecución real (necesita internet)
  python fitnova.py --demo   -> usa noticias de ejemplo, sin internet
"""

import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from urllib.parse import urlencode
from urllib.request import Request, urlopen

import feedparser

# ---------------------------------------------------------------- Ajustes
CARPETA = Path(__file__).parent
FEEDS = CARPETA / "feeds.json"
DATOS = CARPETA / "data" / "noticias.json"
PLANTILLA = CARPETA / "plantilla.html"
WEB = CARPETA / "site" / "index.html"
INFORME = CARPETA / "data" / "informe.json"   # resumen de la última ejecución

DIAS_A_CONSERVAR = 7        # noticias más antiguas se descartan
MAX_POR_FEED = 15           # para no saturar la web con una sola fuente
MAX_CARACTERES_RESUMEN = 280

# Palabras clave (en español, porque clasificamos DESPUÉS de traducir).
# Van de más específica a más general: la primera que encaje gana; si ninguna encaja -> "Salud general".
CATEGORIAS = {
    "Sueño":         ["sueño", "dormir", "insomnio", "descanso", "siesta"],
    "Salud mental":  ["estrés", "ansiedad", "depresión", "mental", "meditación",
                      "bienestar emocional", "felicidad", "soledad", "mindfulness"],
    "Entrenamiento": ["entrenamiento", "ejercicio", "fuerza", "músculo", "muscular",
                      "gimnasio", "correr", "carrera", "cardio", "hipertrofia",
                      "pesas", "atleta", "deporte", "caminar", "yoga", "fitness"],
    "Nutrición":     ["nutrición", "dieta", "alimento", "comida", "proteína",
                      "vitamina", "suplemento", "ayuno", "azúcar", "calorías",
                      "obesidad", "peso", "comer", "bebida"],
}


# ---------------------------------------------------------------- Utilidades
def limpiar_texto(texto: str) -> str:
    """Quita etiquetas HTML, entidades (&amp;...) y espacios sobrantes."""
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    texto = html.unescape(texto)
    return re.sub(r"\s+", " ", texto).strip()


def recortar(texto: str, maximo: int) -> str:
    if len(texto) <= maximo:
        return texto
    return texto[:maximo].rsplit(" ", 1)[0] + "…"


def clave_duplicado(titulo: str) -> str:
    """Versión 'normalizada' del título para detectar noticias repetidas."""
    return re.sub(r"[^a-z0-9áéíóúñü]", "", titulo.lower())[:80]


def fecha_de(entrada) -> datetime:
    """Fecha de publicación de una entrada RSS. Si no trae, usamos 'ahora'."""
    for campo in ("published_parsed", "updated_parsed"):
        valor = entrada.get(campo)
        if valor:
            return datetime(*valor[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def imagen_de(entrada) -> str:
    """Busca una imagen en la entrada RSS. Cada medio la pone en un sitio distinto."""
    for campo in ("media_content", "media_thumbnail"):
        for media in entrada.get(campo, []):
            if media.get("url") and media.get("medium", "image") == "image":
                return media["url"]
    for enlace in entrada.get("links", []) + entrada.get("enclosures", []):
        if enlace.get("type", "").startswith("image/") and enlace.get("href"):
            return enlace["href"]
    # Último recurso: la primera <img> dentro del resumen o el contenido
    html_bruto = entrada.get("summary", "") + "".join(c.get("value", "") for c in entrada.get("content", []))
    encontrada = re.search(r'<img[^>]+src=["\']([^"\']+)', html_bruto)
    return encontrada.group(1) if encontrada else ""


def clasificar(texto: str) -> str:
    texto = texto.lower()
    for categoria, palabras in CATEGORIAS.items():
        if any(p in texto for p in palabras):
            return categoria
    return "Salud general"


# ---------------------------------------------------------------- Traducción
# Probamos primero Google y, si nos bloquea, MyMemory (ambos gratuitos).
# Si un servicio falla 3 veces seguidas, dejamos de usarlo en esta ejecución.
ESTADISTICAS = {"google": 0, "mymemory": 0, "errores": []}
_fallos_seguidos = {"google": 0, "mymemory": 0}
MAX_FALLOS_SEGUIDOS = 3


def _pedir_json(url: str) -> dict | list:
    peticion = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(peticion, timeout=10) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def _google(texto: str, idioma: str) -> str:
    url = "https://translate.googleapis.com/translate_a/single?" + urlencode(
        {"client": "gtx", "sl": idioma, "tl": "es", "dt": "t", "q": texto})
    datos = _pedir_json(url)
    return "".join(frase[0] for frase in datos[0] if frase and frase[0])


def _mymemory(texto: str, idioma: str) -> str:
    parametros = {"q": texto[:500], "langpair": f"{idioma}|es"}
    if os.environ.get("MYMEMORY_EMAIL"):          # opcional: sube el límite diario
        parametros["de"] = os.environ["MYMEMORY_EMAIL"]
    datos = _pedir_json("https://api.mymemory.translated.net/get?" + urlencode(parametros))
    traducido = datos.get("responseData", {}).get("translatedText", "")
    if datos.get("responseStatus") != 200 or "MYMEMORY WARNING" in traducido:
        raise RuntimeError(f"MyMemory: {datos.get('responseStatus')} {traducido[:120]}")
    return traducido


def traducir(texto: str, idioma: str) -> str | None:
    """Traduce al español. Devuelve None si ningún servicio lo consigue,
    para reintentarlo en la siguiente ejecución."""
    if not texto or idioma == "es":
        return texto
    for nombre, servicio in (("google", _google), ("mymemory", _mymemory)):
        if _fallos_seguidos[nombre] >= MAX_FALLOS_SEGUIDOS:
            continue
        try:
            traducido = html.unescape(servicio(texto, idioma)).strip()
            if traducido:
                _fallos_seguidos[nombre] = 0
                ESTADISTICAS[nombre] += 1
                return traducido
            raise RuntimeError("respuesta vacía")
        except Exception as error:
            _fallos_seguidos[nombre] += 1
            mensaje = f"{nombre}: {type(error).__name__}: {error}"[:200]
            print(f"   ! {mensaje}")
            if mensaje not in ESTADISTICAS["errores"] and len(ESTADISTICAS["errores"]) < 6:
                ESTADISTICAS["errores"].append(mensaje)
    return None


def necesita_traduccion(noticia: dict) -> bool:
    """True si la noticia está en otro idioma y aún no tiene traducción válida."""
    if noticia["idioma"] == "es":
        return False
    return not noticia.get("traducida") or noticia.get("titulo") == noticia["titulo_original"]


# ---------------------------------------------------------------- Recogida
def leer_feed(feed: dict) -> list[dict]:
    datos = feedparser.parse(feed["url"])
    if datos.get("bozo") and not datos.entries:
        print(f" ✗ {feed['nombre']}: {datos.get('bozo_exception')}")
        return []

    noticias = []
    for entrada in datos.entries[:MAX_POR_FEED]:
        titulo = limpiar_texto(entrada.get("title", ""))
        fuente = feed["nombre"]
        # Google News añade " - Nombre del medio" al final del título
        if "news.google.com" in feed["url"] and " - " in titulo:
            titulo, fuente = titulo.rsplit(" - ", 1)
        resumen = limpiar_texto(entrada.get("summary", ""))
        if resumen.startswith(titulo[:40]):   # Google News repite el título
            resumen = ""
        noticias.append({
            "titulo_original": titulo,
            "resumen_original": recortar(resumen, MAX_CARACTERES_RESUMEN),
            "idioma": feed["idioma"],
            "fuente": fuente,
            "enlace": entrada.get("link", ""),
            "imagen": imagen_de(entrada),
            "fecha": fecha_de(entrada).isoformat(),
        })
    print(f" ✓ {feed['nombre']}: {len(noticias)} noticias")
    return noticias


def noticias_demo() -> list[dict]:
    """Noticias inventadas (ya traducidas) para probar la web sin conexión.
    Las imágenes son de relleno (picsum.photos); algunas van sin imagen a propósito."""
    ahora = datetime.now(timezone.utc)
    ejemplos = [
        ("en", "Only one workout helped older adults lose fat and keep muscle",
         "Solo un tipo de entrenamiento ayudó a los mayores a perder grasa y mantener músculo",
         "Un ensayo comparó tres rutinas en personas de más de 65 años durante doce semanas.", "entreno-mayores"),
        ("fr", "Le manque de sommeil augmente l'envie de sucre",
         "La falta de sueño aumenta las ganas de azúcar",
         "Dormir menos de seis horas altera las hormonas que regulan el hambre.", "sueno-noche"),
        ("de", "Krafttraining senkt das Risiko für Herzerkrankungen",
         "El entrenamiento de fuerza reduce el riesgo de enfermedades cardíacas",
         "Dos sesiones semanales ya muestran beneficios según un estudio con miles de adultos.", "pesas-gimnasio"),
        ("es", "Cinco minutos de meditación al día reducen el estrés laboral",
         "Cinco minutos de meditación al día reducen el estrés laboral",
         "Los participantes notaron mejoras en la concentración tras tres semanas.", ""),
        ("it", "Proteine vegetali: quante ne servono davvero",
         "Proteínas vegetales: cuántas necesitas de verdad en tu dieta",
         "Legumbres, tofu y frutos secos pueden cubrir las necesidades si se combinan bien.", "legumbres-cocina"),
        ("pt", "Hidratação e pele: o que diz a ciência",
         "Hidratación y piel: lo que dice la ciencia",
         "Beber más agua no siempre se traduce en una piel más hidratada.", ""),
        ("en", "Walking after meals helps control blood sugar",
         "Caminar después de comer ayuda a controlar el azúcar en sangre",
         "Bastan diez minutos de paseo para reducir los picos de glucosa.", "paseo-parque"),
        ("de", "Wie Einsamkeit die Gesundheit beeinflusst",
         "Cómo afecta la soledad a la salud física",
         "Los expertos la comparan con otros factores de riesgo conocidos.", ""),
        ("en", "Stretching before running: what the evidence says",
         "Estirar antes de correr: qué dice la evidencia",
         "El calentamiento dinámico parece más útil que los estiramientos estáticos.", "corredora-calle"),
    ]
    return [{
        "titulo_original": orig, "resumen_original": "", "titulo": es, "resumen": resumen, "traducida": True,
        "idioma": idioma, "fuente": "Fuente de ejemplo", "enlace": "https://example.com",
        "imagen": f"https://picsum.photos/seed/{semilla}/1200/800" if semilla else "",
        "fecha": (ahora - timedelta(hours=4 * n + 1)).isoformat(),
    } for n, (idioma, orig, es, resumen, semilla) in enumerate(ejemplos)]


# ---------------------------------------------------------------- Programa
def main():
    demo = "--demo" in sys.argv

    # 1. Noticias que ya teníamos (así no volvemos a traducirlas)
    guardadas = json.loads(DATOS.read_text("utf-8")) if DATOS.exists() and not demo else []
    por_clave = {clave_duplicado(n["titulo_original"]): n for n in guardadas}

    # 2. Noticias nuevas
    print("Leyendo fuentes…")
    if demo:
        recogidas, recuento_fuentes = noticias_demo(), {}
    else:
        feeds = json.loads(FEEDS.read_text("utf-8"))
        recogidas, recuento_fuentes = [], {}
        for feed in feeds:
            leidas = leer_feed(feed)
            recuento_fuentes[feed["nombre"]] = len(leidas)
            recogidas += leidas

    # 3. Añadir las nuevas (sin repetir) y traducir lo que falte
    for noticia in recogidas:
        clave = clave_duplicado(noticia["titulo_original"])
        if clave and clave not in por_clave:
            por_clave[clave] = noticia

    # Quitamos las antiguas antes de traducir, para no gastar tiempo en ellas
    limite = datetime.now(timezone.utc) - timedelta(days=DIAS_A_CONSERVAR)
    noticias = [n for n in por_clave.values() if datetime.fromisoformat(n["fecha"]) >= limite]

    nuevas = fallidas = 0
    for noticia in noticias:
        if "titulo" in noticia and not necesita_traduccion(noticia):
            continue   # ya estaba traducida
        titulo = traducir(noticia["titulo_original"], noticia["idioma"])
        resumen = traducir(noticia["resumen_original"], noticia["idioma"]) if titulo else None
        noticia["traducida"] = titulo is not None
        noticia["titulo"] = titulo or noticia["titulo_original"]
        noticia["resumen"] = resumen if resumen is not None else noticia["resumen_original"]
        noticia["categoria"] = clasificar(noticia["titulo"] + " " + noticia["resumen"])
        if noticia["traducida"]:
            nuevas += 1
        else:
            fallidas += 1
        if all(f >= MAX_FALLOS_SEGUIDOS for f in _fallos_seguidos.values()):
            print("Ningún traductor responde: lo reintentaremos en la próxima ejecución.")
            break
        time.sleep(0.3)   # no saturar al traductor
    print(f"Traducidas {nuevas} noticias; {fallidas} fallidas (se reintentarán la próxima vez).")

    # 4. Ordenar de más reciente a más antigua
    noticias.sort(key=lambda n: n["fecha"], reverse=True)

    # 5. Guardar datos y generar la web
    if not demo:   # en demo no ensuciamos los datos reales
        DATOS.parent.mkdir(exist_ok=True)
        DATOS.write_text(json.dumps(noticias, ensure_ascii=False, indent=2), "utf-8")
        informe = {
            "fecha": datetime.now(timezone.utc).isoformat(),
            "por_fuente": recuento_fuentes,
            "noticias_publicadas": len(noticias),
            "traducidas_ahora": nuevas,
            "traducciones_fallidas": fallidas,
            "pendientes_de_traducir": sum(necesita_traduccion(n) for n in noticias),
            "traducidas_por_servicio": {k: ESTADISTICAS[k] for k in ("google", "mymemory")},
            "errores_de_traduccion": ESTADISTICAS["errores"],
        }
        INFORME.write_text(json.dumps(informe, ensure_ascii=False, indent=2), "utf-8")

    web = PLANTILLA.read_text("utf-8")
    web = web.replace("__NOTICIAS__", json.dumps(noticias, ensure_ascii=False).replace("</", "<\\/"))
    web = web.replace("__ACTUALIZADO__", datetime.now(timezone.utc).isoformat())
    WEB.parent.mkdir(exist_ok=True)
    WEB.write_text(web, "utf-8")
    print(f"Web generada con {len(noticias)} noticias -> {WEB}")


if __name__ == "__main__":
    main()
