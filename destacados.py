"""
Sudor y Ciencia · Lista semanal de noticias para revisar.

Escribe en pantalla (en formato Markdown) las noticias más importantes de los últimos 7 días
que aún no tienen comentario del editor. El workflow semanal la publica como un aviso
(issue) en GitHub para que Raúl las revise.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import web

CARPETA = Path(__file__).parent
CANTIDAD = 5

noticias = json.loads((CARPETA / "data" / "noticias.json").read_text("utf-8"))
limite = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
candidatas = [
    n for n in noticias
    if n["fecha"] >= limite and n.get("relevante", True) and n.get("explicacion") and "slug" in n
    and not (CARPETA / "comentarios" / f"{n['id']}.md").exists()
]
candidatas.sort(key=lambda n: (n.get("puntuacion", 0), n["fecha"]), reverse=True)
repositorio = "https://github.com/rgr05/fitnova"

print("Estas son las noticias más importantes de la semana que aún no tienen tu opinión.\n")
print("Para cada una: lee la noticia original, comprueba la ficha y pulsa **Escribir mi opinión**. "
      "Se abrirá el archivo ya creado con el nombre correcto: escribe 2-5 frases y pulsa *Commit changes*.\n")
for posicion, n in enumerate(candidatas[:CANTIDAD], 1):
    print(f"### {posicion}. {n['titulo']}")
    print(f"{n['categoria']} · {n['fuente']} · importancia {n.get('puntuacion', '?')}/10\n")
    print(f"> {n.get('resumen', '')}\n")
    print(f"- [Ver en Sudor y Ciencia]({web.url_absoluta('noticias/' + n['slug'] + '.html')})")
    print(f"- [Noticia original]({n['enlace']})")
    print(f"- **[Escribir mi opinión]({repositorio}/new/main/comentarios?filename={n['id']}.md)** (código `{n['id']}`)\n")
if not candidatas:
    print("_No hay noticias pendientes de revisar esta semana._")
print("\nCierra este aviso cuando termines.")
