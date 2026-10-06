# vendor/ — librerías de terceros, servidas desde el propio sitio

El token de la autora vive en el navegador (`localStorage`, por dominio) y
cualquier script que corra en el sitio puede leerlo. Por eso ninguna página
carga scripts de un CDN: estas librerías se copian acá desde npm, con la
versión exacta, y no se tocan a mano.

| carpeta | paquete npm | archivos | sha256 |
|---|---|---|---|
| `pdfjs-3.11.174/` | `pdfjs-dist@3.11.174` | `build/pdf.min.js` | `5b5799e6f8c680663207ac5b42ee14eed2a406fa7af48f50c154f0c0b1566946` |
| | | `build/pdf.worker.min.js` | `feabdf309770ed24bba31a5467836cdc8cf639c705af27d52b585b041bb8527b` |
| `d3-7.9.0/` | `d3@7.9.0` | `dist/d3.min.js` | `f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539` |
| `katex-0.16.11/` | `katex@0.16.11` | `dist/katex.min.js` | `e6bfe5deebd4c7ccd272055bab63bd3ab2c73b907b6e6a22d352740a81381fd4` |
| | | `dist/katex.min.css` | `717bc9ae7853b61f0f76455dddf0ecd4f527a783f42de2ac24684899c1c46258` |
| | | `dist/contrib/auto-render.min.js` | `7b57d427ac6270677daf8d8380ded2cc73336f9149a167b8e1fe0d6ef66604ae` |
| | | `dist/fonts/*.woff2` | (las fuentes de la hoja de estilo) |
| `fuentes-5.3.0/` | `@fontsource-variable/newsreader`, `@fontsource-variable/eb-garamond`, `@fontsource/ibm-plex-mono`, `@fontsource/spectral`, `@fontsource/cormorant-garamond`, `@fontsource/im-fell-english-sc`, `@fontsource/almendra-display` (todos 5.3.0) | `files/*.woff2` (subconjuntos latin y latin-ext) y `fuentes.css` | (licencias OFL en `LICENSE-*`) |
| `baffle-0.3.6/` | `baffle@0.3.6` | `dist/baffle.min.js` | `b784b7689bf7331eae263ec61ee99e6cd145706e9f7fdeb0bcbce04a5cbf6e95` |
| `openpgp-6.3.2/` | `openpgp@6.3.2` | `dist/openpgp.min.js` (+ `LICENSE`, LGPL-3.0) | `e19bf4f04f34f24caded3ff3f3643099538b2674a0a94221e2faca75ac3e4aa1` |

Para comprobar que nada cambió: `cd sitio/vendor && sha256sum */*.js */*.css */*/*.js`
y comparar con la tabla.

Para actualizar una librería: `npm pack <paquete>@<versión>`, copiar los
mismos archivos a una carpeta nueva con la versión en el nombre, cambiar las
rutas en las páginas y anotar las huellas nuevas acá.

`fuentes-5.3.0/fuentes.css` reúne las reglas `@font-face` de esos paquetes con
los nombres de familia de siempre (`Newsreader`, `EB Garamond`, `IBM Plex
Mono`, `Spectral`, `Cormorant Garamond`, `IM Fell English SC`, `Almendra Display`), así que las
páginas no cambian su CSS. El navegador baja solo los archivos que usa cada
página.
