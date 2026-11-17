# Handoff — sitio de Luna Sophia Terra

> Documento de continuidad. Si una sesión se corta, empieza aquí: lee esto, revisa `git log` y sigue con la primera casilla sin marcar.
> Plan completo: `~/.claude/plans/de-la-manera-m-s-compiled-locket.md` (copia resumida abajo).

## Objetivo
Sitio de autora en Hugo (tema propio `themes/luna-terra`) que replica el diseño de https://www.julia-ulrich-art.com/ con el contenido de `base/`. Se publica en GitHub Pages (`LinkSake/luna`) con el dominio `luna.eltelar.xyz`.

## Decisiones tomadas
- **Correo:** placeholder `hola@ejemplo.com` en `hugo.toml` → `params.email`. **PENDIENTE** el correo real.
- **Footer:** «© {año} Luna Sophia Terra» a la izquierda y «Diseño: Luis Angel Ortega» (link a https://luisangel.me/) a la derecha.
- **Blog:** importar los dos blogs completos: Transcisthor (WordPress, 26 posts) y El Canto de Lemuria (Blogspot, 84 posts).
  - Taxonomía `origen` para filtrar.
  - Los posts sin título toman su primera línea.
  - Imágenes descargadas al bundle.
  - Script: `scripts/import_blogs.py` (solo stdlib; se corre con `python3 -I scripts/import_blogs.py`; es idempotente).
- **Deploy:** igual que `LinkSake/metwo`:
  - `.github/workflows/hugo.yaml` (Actions + `actions/deploy-pages`, `HUGO_VERSION 0.152.2`).
  - Pages con `build_type=workflow`.
  - CNAME configurado por API, no con un archivo.
- **Privacidad:**
  - Todas las imágenes de `base/` se re-guardaron sin EXIF, porque dos fotos traían coordenadas GPS. El commit inicial se reescribió (`839066b`) antes de tener remoto.
  - Las páginas con fotos usan `build.publishResources: false`, así que solo se publican derivados WebP redimensionados.
- **Tipografía y colores** (sacados del CSS de Pixpa):
  - Lora para títulos y navegación; sans-serif gris para el cuerpo.
  - Colores: `#192E2F` títulos y botón, `#3B3B3B` nav, `#6F6F6F` cuerpo, `#F3F3F3` fondos suaves.

## Estructura
```
hugo.toml                     config, menú, redes, email, diseñador
content/_index.md             Inicio (hero: frase + botón a /obras/; imagen en assets/images/foto-inicio.jpg)
content/sobre-mi/index.md     bundle; layout "sobre-mi"; reconocimientos y cita en front matter
content/obras/index.md        bundle; layout "obras"; libros/antologías en front matter
content/archivo/index.md      bundle; shortcodes gallery/timeline/figure
content/contacto/index.md     bundle; layout "contacto"
content/blog/                 _index.md + 110 bundles importados (index.html con front matter)
themes/luna-terra/            layouts, shortcodes (figure, gallery, spotify, timeline), assets/css/main.css, assets/js
scripts/import_blogs.py       importador de blogs
base/                         contenido original redactado por Luna (fuente de verdad; Hugo no lo lee)
```

## Checkpoints
- [x] **CP0** — EXIF/GPS eliminado, `.gitignore`, commit inicial reescrito, scaffold de Hugo, workflow.
- [x] **CP1a** — Tema: header, footer, menú móvil, home, sobre mí, obras, archivo, contacto, lightbox.
- [x] **CP1b** — Blogs importados: 110 bundles (26 Transcisthor + 84 El Canto de Lemuria), 82 imágenes locales, 0 fallos.
- [x] **CP2** — Templates del blog (lista paginada, filtro por origen, post con anterior/siguiente) revisados con posts reales.
- [x] **CP3** — QA:
  - Build limpio, 0 links rotos y 0 GPS en `public/`. Screenshots en desktop y móvil.
  - Correcciones del revisor de código:
    - El importador quita EXIF/XMP de las imágenes del blog, rechaza URLs de iframe ambiguas (con `\` o userinfo) y no descarga desde hosts privados.
    - Paginación con canonical y título propios.
    - Contraste AA (`--c-faint #767676`).
    - El foco ya no se escapa del lightbox ni del menú móvil (`inert`).
    - Arreglado el overflow de URLs largas y los márgenes de `<figure>`.
- [ ] **CP4** — Deploy: `gh repo create LinkSake/luna --public --source . --push`, habilitar Pages (workflow), CNAME `luna.eltelar.xyz`.

## Cómo verificar en local
```bash
hugo server            # http://localhost:1313
hugo --gc --minify     # build de producción a public/
```
Screenshots sin la extensión de Chrome: usar el chromium headless de Playwright (`~/Library/Caches/ms-playwright/chromium_headless_shell-*/…/chrome-headless-shell --screenshot`).

## Pendientes para Luna o el usuario
- [ ] Correo real de contacto → `hugo.toml` `params.email`.
- [ ] Portada de *Pista Transcendental No. 9* → agregar `imagen:` en `content/obras/index.md` y el archivo en ese bundle.
- [ ] DNS: registro `CNAME luna → linksake.github.io` en el proveedor de `eltelar.xyz`; después activar «Enforce HTTPS» en Settings → Pages.
- [ ] Revisar posts viejos de Blogspot: para ocultar uno, agrega `draft: true` en su front matter.

## Notas del blog importado
- 7 posts de Blogspot no tenían título; el importador les puso su primera línea (por ejemplo «Muerde, muerde mis sombras Belial»).
- «My Best Band» y «My Best Band 2» solo tenían un reproductor Flash muerto. Quedaron con la nota «Esta entrada contenía un reproductor multimedia antiguo que ya no está disponible.» Candidatos a `draft: true`.
- «La Guerra y la Nieve»: el video de YouTube incrustado (`0fdgjcsACkg`) probablemente ya no se puede reproducir.
- Se perdió la alineación centrada o a la derecha de algunos epígrafes, porque se quitan los `style`.

## Registro
- 2026-11-17 — CP0 y CP1a completos.
- 2026-11-17 — CP1b y CP2 completos (blog importado y templates).
- 2026-11-17 — CP3 completo (QA y correcciones de la revisión).

## Mejoras opcionales (no bloquean)
- Auto-hospedar la fuente Lora en lugar de Google Fonts, por privacidad de las visitas.
- Las `featured.jpg` de WordPress se publican también como originales (hasta 1.4 MB, sin EXIF). Se podría poner `publishResources: false` en el blog y reescribir los `src` del contenido a derivados WebP.
