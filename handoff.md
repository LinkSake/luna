# Handoff — sitio de Luna Sophia Terra

> Documento de continuidad. Si una sesión se corta, empieza aquí: lee esto, revisa `git log` y sigue con la primera casilla sin marcar.
> Plan completo: `~/.claude/plans/de-la-manera-m-s-compiled-locket.md` (copia resumida abajo).

## Objetivo
Sitio de autora en Hugo (tema propio `themes/luna-terra`) que replica el diseño de https://www.julia-ulrich-art.com/ con el contenido que redactó Luna. Ese contenido estaba en `base/` y ya se migró a `content/`; la carpeta se eliminó. Se publica en GitHub Pages (`LinkSake/luna`) con el dominio `luna.eltelar.xyz`.

## Decisiones tomadas
- **Correo:** `luna@eltelar.xyz` en `hugo.toml` → `params.email`.
- **Footer:** «© {año} Luna Sophia Terra» a la izquierda y «Diseño: Luis Angel Ortega» (link a https://luisangel.me/) a la derecha.
- **Blog:** las 26 entradas de Transcisthor (WordPress).
  - `origen` es solo un texto en el front matter («Transcisthor»), no una taxonomía; no hay rutas `/origen/`.
  - Etiquetas en `/tags/`.
  - Los posts sin título toman su primera línea.
  - Imágenes descargadas al bundle.
  - Script: `scripts/import_blogs.py` (solo stdlib; se corre con `python3 -I scripts/import_blogs.py`; es idempotente).
- **Deploy:** igual que `LinkSake/metwo`:
  - `.github/workflows/hugo.yaml` (Actions + `actions/deploy-pages`, `HUGO_VERSION 0.152.2`).
  - Pages con `build_type=workflow`.
  - CNAME configurado por API, no con un archivo.
- **Privacidad:**
  - Todas las imágenes originales se re-guardaron sin EXIF, porque dos fotos traían coordenadas GPS. El commit inicial se reescribió (`839066b`) antes de tener remoto.
  - Las páginas con fotos y el blog (vía `cascade` en `content/blog/_index.md`) usan `build.publishResources: false`, así que solo se publican derivados WebP redimensionados. El template del post reescribe los `src` de su contenido.
- **Tipografía y colores** (sacados del CSS de Pixpa):
  - Lora (auto-hospedada en `themes/luna-terra/static/fonts/`) para títulos y navegación; sans-serif gris para el cuerpo.
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
README.md                     documentación de uso y edición
```

## Checkpoints
- [x] **CP0** — EXIF/GPS eliminado, `.gitignore`, commit inicial reescrito, scaffold de Hugo, workflow.
- [x] **CP1a** — Tema: header, footer, menú móvil, home, sobre mí, obras, archivo, contacto, lightbox.
- [x] **CP1b** — Blog importado: 26 posts de Transcisthor con sus imágenes locales.
- [x] **CP2** — Templates del blog (lista paginada, filtro por origen, post con anterior/siguiente) revisados con posts reales.
- [x] **CP3** — QA:
  - Build limpio, 0 links rotos y 0 GPS en `public/`. Screenshots en desktop y móvil.
  - Correcciones del revisor de código:
    - El importador quita EXIF/XMP de las imágenes del blog, rechaza URLs de iframe ambiguas (con `\` o userinfo) y no descarga desde hosts privados.
    - Paginación con canonical y título propios.
    - Contraste AA (`--c-faint #767676`).
    - El foco ya no se escapa del lightbox ni del menú móvil (`inert`).
    - Arreglado el overflow de URLs largas y los márgenes de `<figure>`.
- [x] **CP4** — Deploy:
  - Repo público https://github.com/LinkSake/luna, Pages con `build_type=workflow` y CNAME `luna.eltelar.xyz`.
  - Workflow en verde. Todas las páginas responden 200 (verificado contra la IP de GitHub Pages con `Host: luna.eltelar.xyz`); /no-existe/ da 404.

## Cómo verificar en local
```bash
hugo server            # http://localhost:1313
hugo --gc --minify     # build de producción a public/
```
Screenshots sin la extensión de Chrome: usar el chromium headless de Playwright (`~/Library/Caches/ms-playwright/chromium_headless_shell-*/…/chrome-headless-shell --screenshot`).

## Pendientes para Luna o el usuario
- [x] Correo real de contacto: `luna@eltelar.xyz`.
- [x] Portada provisional (teaser «Coming soon») de *Pista Transcendental No. 9* en `content/obras/pista-transcendental-9-portada.jpg`. Cuando exista la definitiva, reemplaza ese archivo; el estado sigue diciendo «portada e ilustraciones pendientes».
- [x] DNS: `luna.eltelar.xyz` ya resuelve y el sitio está en línea.
- [x] HTTPS forzado en Pages; deploy re-ejecutado para generar URLs `https://`.
- [x] El segundo blog (Blogspot) se eliminó por completo a pedido de Luna: posts, soporte en el importador e historial de git.

## Notas del blog importado
- «La Guerra y la Nieve»: el video de YouTube incrustado (`0fdgjcsACkg`) probablemente ya no se puede reproducir.
- La alineación centrada o a la derecha se conserva como `<div class="align-center|align-right">`.

## Registro
- 2026-11-17 — CP0 y CP1a completos.
- 2026-11-17 — CP1b y CP2 completos (blog importado y templates).
- 2026-11-17 — CP3 completo (QA y correcciones de la revisión).
- 2026-11-17 — CP4 completo: publicado en GitHub Pages. Falta el DNS.
- 2026-11-17 — DNS y HTTPS listos; correo real y portada provisional de *Pista Transcendental No. 9*.
- Moño de luto para Zoren en «Sobre mí», en el texto y en el pie de foto (shortcode `{{< luto >}}` y opción `|luto` de `gallery`).
- Arreglo: las páginas de etiquetas y de origen (`/tags/<x>/`, `/origen/<x>/`) salían vacías desde el primer deploy. Hugo 0.152 les aplicaba `_default/taxonomy.html`. Las plantillas pasaron a `layouts/term.html` y `layouts/taxonomy.html`, y los textos a español («Etiqueta», «Etiquetas»).
- 2026-11-17 — Eliminado por completo el blog de Blogspot, a pedido de Luna, que reserva ese material para novelas:
  - Se borraron sus posts e imágenes.
  - El importador ya no lo trae.
  - Se quitaron la taxonomía `origen` y el filtro del blog.
  - Se reescribió el historial de git (`git filter-branch`) y se hizo force-push, así que **cambiaron los hashes desde el commit del importador en adelante**. Cualquier clon anterior debe volver a clonarse.

## Mejoras aplicadas (2026-11-17, segunda ronda)
- [x] Lora auto-hospedada; ya no hay llamadas a Google Fonts.
- [x] El blog ya no publica imágenes originales: solo derivados WebP (máximo 1440px). El sitio bajó de 25 MB a 19 MB.
- [x] `aria-current` correcto en la paginación del blog.
- [x] Alineación de epígrafes conservada en el importador.
- [x] Carpeta `base/` eliminada y `README.md` agregado.

## Mejora pendiente (opcional)
- El workflow toma el `baseURL` de Pages (hoy `http://`). Se podría usar el de `hugo.toml` y evitar volver a correr el deploy al activar HTTPS. No se hizo para respetar el esquema de `metwo`.
