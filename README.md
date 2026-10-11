# Fitnova

Web autosuficiente que recopila noticias de fitness, salud y autocuidado de medios de todo el mundo y las traduce al español.

## Estructura

```
fitnova/
├── fitnova.py        # el programa: lee feeds, traduce, clasifica y genera la web
├── feeds.json        # lista de fuentes RSS (añade o quita las que quieras)
├── plantilla.html    # diseño de la web; Python le inyecta las noticias
├── requirements.txt  # librerías necesarias
├── data/noticias.json  # se crea solo: noticias guardadas (evita re-traducir)
└── site/index.html     # se crea solo: la web final
```

## Cómo ejecutarlo

```bash
pip install -r requirements.txt
python fitnova.py --demo   # prueba sin internet, con noticias de ejemplo
python fitnova.py          # ejecución real
```

Después abre `site/index.html` en el navegador.

## Cómo añadir una fuente

Añade una línea a `feeds.json` con su nombre, idioma (`en`, `es`, `fr`, `de`, `it`, `pt`…) y la URL del feed RSS.
Para buscar cualquier tema en Google News, en cualquier idioma:
`https://news.google.com/rss/search?q=TU+BUSQUEDA+when:7d&hl=IDIOMA&gl=PAIS&ceid=PAIS:IDIOMA`

## Publicación automática (GitHub Actions + GitHub Pages)

`.github/workflows/actualizar.yml` se ejecuta en los servidores de GitHub, gratis:
cada 4 horas, cada vez que subes un cambio y cuando pulsas "Run workflow" a mano.
Busca y traduce las noticias, guarda `data/noticias.json` en el repositorio
(para no volver a traducir lo mismo) y publica `site/` en GitHub Pages.

Configuración única: Settings → Pages → Source: **GitHub Actions**.

## Próximas fases

1. ~~Prototipo~~ ✅
2. ~~Automatización con GitHub Actions y GitHub Pages~~ ✅
3. Mejoras: traducción y clasificación con IA, resúmenes propios, detección de duplicados entre idiomas.
4. Crecimiento: SEO, newsletter semanal y monetización.
