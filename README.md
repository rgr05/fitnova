# Sudor y Ciencia

(Antes llamado Fitnova. El código conserva ese nombre en algunos archivos, como `fitnova.py`.)

Web autosuficiente que recopila noticias de fitness, salud y autocuidado de medios de todo el mundo y las traduce al español.

## Estructura

```
fitnova/
├── fitnova.py         # programa principal: lee feeds, procesa noticias y guarda datos
├── ia.py              # explicación de cada noticia con la IA de Claude
├── web.py             # genera la web completa (portada, temas, noticias, guías, sitemap…)
├── destacados.py      # lista semanal de noticias para revisar
├── config.json        # nombre, dirección (url) y autor de la web
├── feeds.json         # fuentes RSS
├── plantillas/        # diseño: HTML (Jinja2), estilos.css y app.js
├── guias/             # guías en Markdown (una por archivo)
├── paginas/           # páginas fijas: sobre, privacidad
├── comentarios/       # tu opinión sobre las noticias destacadas (ver su README)
└── data/              # se actualiza solo: noticias.json e informe.json
```

## Configuración en GitHub (una sola vez)

- **Settings → Pages → Source: GitHub Actions.**
- **Settings → Secrets and variables → Actions → New repository secret:**
  `ANTHROPIC_API_KEY` con tu clave de https://console.anthropic.com. Sin ella, la web
  funciona solo con traducción automática.

## Google Search Console

Al dar de alta la web, elige el método «Etiqueta HTML», copia solo el código del atributo `content`
y pégalo en `google_site_verification` dentro de `config.json`.

## Tipografías e iconos

Se sirven desde `plantillas/recursos/` (sin Google Fonts ni CDN). El archivo de iconos solo contiene
los iconos usados; para añadir uno de Phosphor, regenera `phosphor.woff2` con `pyftsubset` incluyendo
su código y añade su clase en `iconos.css`.

## Revisión semanal

Cada lunes se abre un aviso (pestaña *Issues*) con las 5 noticias más importantes de la semana.
Pulsa «Escribir mi opinión» en cada una, escribe 2-5 frases y guarda. La noticia pasa a mostrarse
como «Revisado» con tu opinión firmada.

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
3. ~~Página propia por noticia explicada con IA, guías, SEO y revisión semanal~~ ✅
4. Crecimiento: SEO, newsletter semanal y monetización.
