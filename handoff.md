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
- [ ] **CP1b** — Importación de blogs (subagente): verificar los 110 bundles y hacer commit de `content/blog` + `scripts/`.
- [ ] **CP2** — Templates del blog (lista, término, post) revisados contra posts reales (imágenes, embeds, poemas con `<br>`).
- [ ] **CP3** — QA: `hugo --gc --minify` limpio, screenshots desktop/móvil, revisión de código, links rotos.
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

## Registro
- 2026-11-17 — CP0 y CP1a completos. El subagente de importación de blogs sigue corriendo.
