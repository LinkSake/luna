# Luna Sophia Terra

Sitio de autora de **Luna Sophia Terra** (Lulietfly): escritora, gestora cultural y artista multidisciplinaria de Chihuahua, México.

🌙 https://luna.eltelar.xyz

Hecho con [Hugo](https://gohugo.io/) y un tema propio (`themes/luna-terra`), inspirado en el portafolio de [Julia Ulrich](https://www.julia-ulrich-art.com/). Se publica en GitHub Pages.

## Requisitos

- Hugo **extended** 0.152.2 (versión fijada en `.tool-versions`; con asdf: `asdf install`).
- Python 3, solo si vas a volver a importar los blogs viejos.

## Uso

```bash
hugo server            # vista previa en http://localhost:1313
hugo --gc --minify     # build de producción en public/
```

Cada push a `main` construye y publica el sitio con `.github/workflows/hugo.yaml`.

## Estructura

```
hugo.toml                  configuración: menú, redes, correo, crédito de diseño
content/
  _index.md                Inicio: frase y botón (la foto está en assets/images/)
  sobre-mi/index.md        Sobre mí: bio, reconocimientos y cita (front matter) + fotos
  obras/index.md           Obras: libros y antologías en el front matter + portadas
  archivo/index.md         Archivo: galerías y trayectoria
  contacto/index.md        Contacto: foto (correo y redes salen de hugo.toml)
  blog/                    entradas importadas (un bundle por post)
themes/luna-terra/         plantillas, estilos, JS, fuente Lora auto-hospedada
scripts/import_blogs.py    importador de los blogs anteriores
```

## Editar contenido

- **Correo y redes:** `hugo.toml` → `[params]` (`email`, `[[params.social]]`).
- **Un libro o una antología:** agrega una entrada en `libros:` o `antologias:` de `content/obras/index.md` y pon la portada en esa misma carpeta. Si una obra no tiene `imagen:`, se muestra una portada provisional.
- **Fotos en una página:** guárdalas en la carpeta de la página y usa los shortcodes:
  ```
  {{< figure src="foto.jpg" alt="Descripción" caption="Pie de foto" >}}
  {{< gallery images="a.jpg|Pie, b.jpg" alt="Texto alternativo" cols="3" >}}
  ```
  Para poner un moño de luto junto a un nombre: `{{< luto >}}` en el texto o `foto.jpg|Nombre|luto` en una galería.
  Las imágenes se publican como WebP redimensionado y sin metadatos. Los originales no se publican.
- **Nueva entrada de blog:** crea `content/blog/AAAA-MM-DD-titulo/index.md` con este front matter:
  ```yaml
  ---
  title: "Título"
  date: 2026-11-17T10:00:00-06:00
  origen: ["Luna Sophia Terra"]
  tags: ["…"]
  ---
  ```
  `origen` es opcional: es solo el texto que se muestra junto a la fecha (por ejemplo «Transcisthor» en las entradas importadas).
- **Ocultar una entrada** sin borrarla: agrega `draft: true` a su front matter.

## Blogs anteriores

`scripts/import_blogs.py` trae las entradas de [Transcisthor](https://transcisthor.wordpress.com/) (WordPress) por su API pública:
- Limpia el HTML y conserva alineaciones y videos.
- Descarga las imágenes sin metadatos.
- Escribe un bundle por entrada.

```bash
python3 -I scripts/import_blogs.py
```

Solo usa la biblioteca estándar. Es idempotente: reescribe las carpetas `content/blog/AAAA-MM-DD-*` y no toca `content/blog/_index.md`. Ojo: también sobrescribe los cambios manuales que hayas hecho a esas entradas.

## Dominio

GitHub Pages está configurado con el dominio `luna.eltelar.xyz`. En el DNS de `eltelar.xyz` debe existir el registro `CNAME luna → linksake.github.io`.

## Créditos

- Contenido y fotografías: © Luna Sophia Terra.
- Diseño y desarrollo: [Luis Angel Ortega](https://luisangel.me/).
- Fuente [Lora](https://github.com/cyrealtype/Lora-Cyrillic), bajo la SIL Open Font License 1.1 (`themes/luna-terra/static/fonts/OFL.txt`).
