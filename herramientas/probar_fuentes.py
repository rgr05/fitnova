"""
Sudor y Ciencia · Diagnóstico de fuentes RSS.

Prueba las fuentes de herramientas/candidatas.json y guarda en data/prueba_fuentes.json, para cada una:
si funciona, cuántas noticias trae, cuándo publicó por última vez, qué proporción trae una entradilla
útil (120 caracteres o más) y algunos titulares de ejemplo.

Se lanza desde GitHub: pestaña Actions → «Probar fuentes» → Run workflow.
"""

import json
import re
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

import feedparser

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fitnova import fecha_de, limpiar_texto  # noqa: E402

socket.setdefaulttimeout(20)
CARPETA = Path(__file__).resolve().parent.parent
candidatas = json.loads((CARPETA / "herramientas" / "candidatas.json").read_text("utf-8"))
ahora = datetime.now(timezone.utc)
informe = []

for fuente in candidatas:
    try:
        datos = feedparser.parse(fuente["url"], agent="Mozilla/5.0 (compatible; SudorYCienciaBot/1.0)")
        entradas = datos.entries
        estado = datos.get("status")
        if not entradas:
            informe.append({**fuente, "funciona": False, "http": estado,
                            "error": str(datos.get("bozo_exception", "sin noticias"))[:160]})
            continue
        resumenes = [limpiar_texto(e.get("summary", "")) for e in entradas]
        fechas = sorted((fecha_de(e) for e in entradas), reverse=True)
        informe.append({
            **fuente, "funciona": True, "http": estado,
            "titulo_canal": limpiar_texto(datos.feed.get("title", "")),
            "noticias": len(entradas),
            "ultima_publicacion": fechas[0].isoformat(),
            "dias_desde_ultima": round((ahora - fechas[0]).total_seconds() / 86400, 1),
            "con_entradilla_util": round(sum(len(r) >= 120 for r in resumenes) / len(resumenes), 2),
            "longitud_media_entradilla": round(sum(map(len, resumenes)) / len(resumenes)),
            "con_imagen": round(sum(bool(e.get("media_content") or e.get("media_thumbnail") or e.get("enclosures"))
                                    for e in entradas) / len(entradas), 2),
            "ejemplos": [limpiar_texto(e.get("title", ""))[:110] for e in entradas[:5]],
        })
    except Exception as error:
        informe.append({**fuente, "funciona": False, "error": f"{type(error).__name__}: {error}"[:160]})
    print(("✓" if informe[-1]["funciona"] else "✗"), fuente["nombre"])

(CARPETA / "data").mkdir(exist_ok=True)
(CARPETA / "data" / "prueba_fuentes.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), "utf-8")
