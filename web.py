"""
Sudor y Ciencia · Generador de la web estática.

Convierte las noticias (data/noticias.json), las guías (guias/*.md) y las páginas
(paginas/*.md) en una web completa dentro de site/, lista para GitHub Pages:

  site/index.html               portada
  site/temas/<tema>.html        una página por tema
  site/noticias/<slug>.html     una página por noticia
  site/guias/index.html         listado de guías
  site/guias/<slug>.html        una página por guía
  site/<pagina>.html            sobre, privacidad…
  site/buscar.html + buscar.json   buscador
  site/sitemap.xml, robots.txt, 404.html

Para cambiar de dominio basta con editar "url" en config.json.
"""

import html
import json
import re
import shutil
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

CARPETA = Path(__file__).parent
SALIDA = CARPETA / "site"
PLANTILLAS = CARPETA / "plantillas"
CONFIG = json.loads((CARPETA / "config.json").read_text("utf-8"))

TEMAS = ["Entrenamiento", "Nutrición", "Sueño", "Salud mental", "Salud general"]
DIAS_PORTADA = 7
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
IDIOMAS = {"en": "inglés", "fr": "francés", "de": "alemán", "it": "italiano", "pt": "portugués"}


# ---------------------------------------------------------------- Utilidades
def slug(texto: str, maximo: int = 70) -> str:
    """'¿Cuánta proteína necesitas?' -> 'cuanta-proteina-necesitas'"""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto.lower()).strip("-")
    return texto[:maximo].rstrip("-") or "noticia"


RUTA_BASE = urlparse(CONFIG["url"]).path.rstrip("/")   # "/fitnova" en GitHub Pages, "" con dominio propio


def ruta(destino: str = "") -> str:
    """Enlace interno: ruta('noticias/x.html') -> '/fitnova/noticias/x.html'"""
    return f"{RUTA_BASE}/{destino.lstrip('/')}"


def url_absoluta(destino: str = "") -> str:
    return f"{CONFIG['url'].rstrip('/')}/{destino.lstrip('/')}"


def fecha_corta(iso: str) -> str:
    fecha = datetime.fromisoformat(iso)
    return f"{fecha.day} {MESES[fecha.month - 1]} {fecha.year}"


# Productos de afiliado en las guías de compra. En el Markdown se escriben así, en una línea propia:
#   {{producto: B0XXXXXXXX | Nombre del producto | Para quién o por qué lo recomendamos}}
# Solo se muestran si config.json tiene "amazon_tag" (el identificador de Afiliados de Amazon).
PATRON_PRODUCTO = re.compile(r"^\{\{producto:(.+?)\}\}\s*$", re.MULTILINE)


def _tarjeta_producto(coincidencia: re.Match) -> str:
    partes = [p.strip() for p in coincidencia.group(1).split("|")]
    if len(partes) != 3 or not re.fullmatch(r"[A-Z0-9]{10}", partes[0]):
        raise ValueError(f"Producto mal escrito (formato: ASIN | Nombre | Motivo): {coincidencia.group(0)}")
    asin, nombre, motivo = (html.escape(p) for p in partes)
    enlace = f"https://www.amazon.es/dp/{asin}?tag={html.escape(CONFIG['amazon_tag'])}"
    return (f'\n<div class="producto">\n<div><p class="producto-nombre">{nombre}</p>'
            f'<p class="producto-motivo">{motivo}</p></div>\n'
            f'<a class="boton" href="{enlace}" target="_blank" rel="sponsored nofollow noopener">'
            f'Ver en Amazon <i class="ph ph-arrow-up-right" aria-hidden="true"></i></a>\n</div>\n')


def leer_markdown(archivo: Path) -> tuple[dict, str]:
    """Lee un .md con cabecera entre '---' (clave: valor) y devuelve (datos, html).
    datos["productos"] indica cuántos productos de afiliado se han mostrado."""
    texto = archivo.read_text("utf-8")
    datos = {}
    if texto.startswith("---"):
        _, cabecera, texto = texto.split("---", 2)
        for linea in cabecera.strip().splitlines():
            if ":" in linea:
                clave, valor = linea.split(":", 1)
                datos[clave.strip()] = valor.strip()
    if CONFIG.get("amazon_tag"):
        texto, datos["productos"] = PATRON_PRODUCTO.subn(_tarjeta_producto, texto)
    else:
        texto, _ = PATRON_PRODUCTO.subn("", texto)   # sin identificador de afiliado, no se muestran
        datos["productos"] = 0
    contenido = markdown.markdown(texto, extensions=["extra", "sane_lists"])
    # Los enlaces externos se abren en otra pestaña
    contenido = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener"', contenido)
    return datos, contenido


def comentario_de(noticia: dict) -> str:
    """La opinión revisada por el autor, si existe: comentarios/<id>.md"""
    archivo = CARPETA / "comentarios" / f"{noticia['id']}.md"
    return leer_markdown(archivo)[1] if archivo.exists() else ""


# ---------------------------------------------------------------- Generación
def generar(noticias: list[dict], demo: bool = False) -> int:
    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    (SALIDA / "noticias").mkdir(parents=True)
    (SALIDA / "temas").mkdir()
    (SALIDA / "guias").mkdir()

    entorno = Environment(loader=FileSystemLoader(PLANTILLAS), autoescape=select_autoescape(["html", "xml"]),
                          trim_blocks=True, lstrip_blocks=True)
    ahora = datetime.now(timezone.utc)
    entorno.globals.update(
        config=CONFIG, ruta=ruta, url_absoluta=url_absoluta, temas=TEMAS, slug=slug,
        idiomas=IDIOMAS, actualizado=ahora.isoformat(), anio=ahora.year,
    )
    entorno.filters["fecha_corta"] = fecha_corta
    paginas = []   # (ruta, indexable) para el sitemap

    def escribir(destino: str, plantilla: str, indexable: bool = True, lastmod: str = "", **datos):
        archivo = SALIDA / destino
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(entorno.get_template(plantilla).render(pagina=destino, **datos), "utf-8")
        paginas.append((destino, indexable, (lastmod or ahora.isoformat())[:10]))

    for noticia in noticias:
        if not CONFIG.get("mostrar_imagenes"):
            noticia["imagen"] = ""   # las fotos pertenecen a cada medio: solo se muestran si se activa en config.json
        noticia["comentario"] = comentario_de(noticia)
        # Solo pedimos a Google que indexe fichas con sustancia: explicación de la IA y una entradilla
        # original suficiente (o la opinión revisada del editor)
        noticia["indexable"] = bool(noticia.get("explicacion")) and (
            len(noticia.get("resumen_original", "")) >= 120 or bool(noticia["comentario"]))
        noticia["url"] = ruta(f"noticias/{noticia['slug']}.html")

    # Portada: lo de la última semana (o lo último que haya)
    limite = (ahora - timedelta(days=DIAS_PORTADA)).isoformat()
    semana = [n for n in noticias if n["fecha"] >= limite] or noticias[:30]
    guias = cargar_guias()

    if noticias:
        lider, recientes = semana[0], semana[1:5]
        arriba = {lider["id"], *(n["id"] for n in recientes)}
        # Destacados: lo mejor de la semana que no esté ya arriba (primero lo revisado por el editor)
        destacados = sorted([n for n in semana if n.get("puntuacion") and n["id"] not in arriba],
                            key=lambda n: (bool(n["comentario"]), n["puntuacion"], n["fecha"]), reverse=True)[:5]
        ya_mostradas = arriba | {n["id"] for n in destacados}
        resto = [n for n in semana if n["id"] not in ya_mostradas]
    else:
        lider, recientes, destacados, resto = None, [], [], []
    escribir("index.html", "portada.html", lider=lider, recientes=recientes, destacados=destacados,
             resto=resto, guias=guias[:3], total_semana=len(semana),
             fuentes=len({n["fuente"] for n in semana}), idiomas_n=len({n["idioma"] for n in semana}))

    # Una página por tema
    for tema in TEMAS:
        del_tema = [n for n in noticias if n["categoria"] == tema]
        escribir(f"temas/{slug(tema)}.html", "tema.html", tema=tema, noticias=del_tema, guias=guias)

    # Una página por noticia. Solo se indexan en Google las que tienen explicación propia.
    for noticia in noticias:
        relacionadas = [n for n in noticias if n["categoria"] == noticia["categoria"] and n["id"] != noticia["id"]][:4]
        guias_tema = [g for g in guias if g["categoria"] == noticia["categoria"] and g["revisado"]][:2]
        escribir(f"noticias/{noticia['slug']}.html", "noticia.html", lastmod=noticia["fecha"],
                 indexable=noticia["indexable"], n=noticia, relacionadas=relacionadas, guias_tema=guias_tema)

    # Guías
    escribir("guias/index.html", "guias.html", guias=guias)
    for guia in guias:
        escribir(f"guias/{guia['slug']}.html", "guia.html", indexable=guia["revisado"], lastmod=guia["actualizado_iso"], guia=guia, otras=[g for g in guias if g is not guia])

    # Páginas fijas (sobre, privacidad…)
    for archivo in sorted((CARPETA / "paginas").glob("*.md")):
        datos, contenido = leer_markdown(archivo)
        escribir(f"{archivo.stem}.html", "pagina.html", titulo=datos.get("titulo", archivo.stem),
                 descripcion=datos.get("descripcion", ""), contenido=contenido)

    # Buscador: índice ligero que se consulta desde el navegador
    indice = [{"t": n["titulo"], "r": n.get("resumen", ""), "c": n["categoria"], "f": n["fuente"],
               "d": n["fecha"], "u": n["url"]} for n in noticias]
    indice += [{"t": g["titulo"], "r": g["descripcion"], "c": "Guía", "f": CONFIG["nombre"],
                "d": g["fecha_iso"], "u": ruta(f"guias/{g['slug']}.html")} for g in guias]
    (SALIDA / "buscar.json").write_text(json.dumps(indice, ensure_ascii=False), "utf-8")
    escribir("buscar.html", "buscar.html", indexable=False)
    escribir("404.html", "404.html", indexable=False)

    # Archivos estáticos
    for estatico in ("estilos.css", "app.js"):
        shutil.copy(PLANTILLAS / estatico, SALIDA / estatico)
    shutil.copytree(PLANTILLAS / "recursos", SALIDA / "recursos")   # tipografías e iconos propios

    # Seguridad editorial: ninguna página de noticia puede contener enlaces de Amazon
    for pagina_noticia in (SALIDA / "noticias").glob("*.html"):
        if re.search(r"amazon\.[a-z.]+/(dp|gp|s\?)|amzn\.to", pagina_noticia.read_text("utf-8")):
            raise RuntimeError(f"Enlace de Amazon en una noticia, no permitido: {pagina_noticia.name}")

    # SEO: sitemap y robots
    urls = [(url_absoluta("" if destino == "index.html" else destino), fecha)
            for destino, indexable, fecha in paginas if indexable]
    (SALIDA / "sitemap.xml").write_text(entorno.get_template("sitemap.xml").render(urls=urls), "utf-8")
    (SALIDA / "robots.txt").write_text(
        ("User-agent: *\nDisallow: /\n" if demo else "User-agent: *\nAllow: /\n")
        + f"Sitemap: {url_absoluta('sitemap.xml')}\n", "utf-8")
    return len(paginas)


def cargar_guias() -> list[dict]:
    guias = []
    for archivo in sorted((CARPETA / "guias").glob("*.md")):
        datos, contenido = leer_markdown(archivo)
        fecha = datos.get("fecha", "2026-01-01")
        guias.append({
            "slug": archivo.stem,
            "titulo": datos.get("titulo", archivo.stem),
            "descripcion": datos.get("descripcion", ""),
            "categoria": datos.get("categoria", "Salud general"),
            "fecha_iso": f"{fecha}T00:00:00+00:00",
            "actualizado_iso": f"{datos.get('actualizado', fecha)}T00:00:00+00:00",
            "revisado": datos.get("revisado", "no").lower() in ("si", "sí", "yes", "true"),
            "verificado_iso": f"{datos['verificado']}T00:00:00+00:00" if datos.get("verificado") else "",
            "tipo": datos.get("tipo", "guia"),        # "compra" para las guías de compra
            "productos": datos["productos"],
            "lectura": max(1, round(len(re.sub(r"<[^>]+>", " ", contenido).split()) / 200)),
            "contenido": contenido,
        })
    return sorted(guias, key=lambda g: g["fecha_iso"], reverse=True)
