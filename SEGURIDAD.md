# Seguridad del sitio (www.p314b.space)

## Lo que ya hace el repo

Se aplica solo en cada publicación:

- **Cabeceras** (`web/_headers`, generadas por `sitio/publicar.py`):
  - Solo HTTPS (HSTS, un año). Sin `preload`: eso se agrega recién cuando
    todo el dominio sirva por HTTPS.
  - Política de contenido: solo se cargan scripts, estilos y fuentes del
    propio sitio, cdnjs, jsDelivr y Google Fonts. La única conexión externa
    es la API de GitHub (el token de la autora).
  - Nadie puede meter el sitio dentro de un iframe ajeno.
  - `nosniff` y referer mínimo.
  - Sin cámara, micrófono, ubicación ni pagos.

  Si algún día se suma una librería de otro CDN, hay que agregarlo en
  `CSP`, en `publicar.py`.
- **`robots.txt`**: los buscadores no indexan las herramientas (acceso,
  taller, matriz, fórmulas).
- **`wrangler.jsonc`**: apagadas las direcciones `*.workers.dev` y las de
  vista previa. El sitio solo se ve en el dominio.
- **Datos**: solo se publica `web/`. El repo es privado.

## Revisión del 01/10

Lo revisado y lo decidido:

- **Scripts de terceros (corregido).** El token de autora vive en el
  navegador (`localStorage`) y cualquier script del sitio puede leerlo. Las
  páginas cargaban pdf.js, d3, KaTeX y baffle desde cdnjs y jsDelivr, sin
  control de integridad: si un CDN servía un archivo alterado, se llevaba el
  token. Ahora se sirven desde `sitio/vendor/`, copiadas de npm con la versión
  exacta y sus huellas sha256 en `vendor/LEEME.md`. La política de contenido
  ya no permite scripts de ningún otro origen (`script-src 'self'`), ni
  workers ni conexiones a CDN. Desde el 03/10/2026 las fuentes también se
  sirven desde `vendor/fuentes-5.3.0/` y la política ya no permite Google
  Fonts.
- **Workflow de publicación (corregido).** El paso que arma el mensaje del
  commit pegaba los datos del disparo (`obra`, `eliminar`, `modo`) dentro del
  script de shell, lo que permitía inyectar comandos. Ahora pasan por
  variables de entorno, como en los otros pasos. Para explotarlo hacía falta
  el token, pero ya no depende de eso.
- **`autor.js` (bien).** El token se manda solo a `api.github.com`; si
  GitHub lo rechaza, se avisa y la página lee la copia publicada.
- **`servidor.py` (bien).** Escucha solo en `127.0.0.1`, exige un encabezado
  propio (una página ajena no puede mandarlo sin una consulta CORS que el
  servidor nunca aprueba) y rechaza otro `Host` (frena el DNS rebinding).
  Los slugs se validan antes de tocar archivos.
- **Secretos (bien).** No hay tokens ni claves en el repo ni en su historia.
- **Cabeceras (bien).** HSTS, `nosniff`, sin iframes ajenos, sin cámara,
  micrófono ni ubicación; las herramientas, sin indexar.

Queda en manos de la autora:

- El token vence (así tiene que ser). Cuando GitHub lo rechaza, se saca uno
  nuevo con los mismos permisos y se pega en `acceso.html`.
- Cloudflare Access sobre las herramientas (punto 5 de abajo): si está
  activo, el taller ni siquiera carga para otros.

## Lo que hay que configurar en el panel de Cloudflare (una vez)

1. **Dominio sin www.** Ya no hace falta crear el registro a mano:
   `wrangler.jsonc` declara `p314b.space` y `www.p314b.space` como *custom
   domains*, y en el próximo deploy Cloudflare crea el DNS y el certificado
   de los dos. El sitio responde igual en ambos; a los buscadores se les
   indica que la dirección principal es www.
   - **Opcional, recomendado:** redirigir siempre a www, para que haya una
     sola dirección (el token de autora se guarda por dirección). En
     **Rules → Redirect Rules**, creá una redirección 301 de
     `p314b.space/*` a `https://www.p314b.space/${1}`, conservando la
     consulta.
   - **Si el deploy falla por los dominios** («hostname already in use» o
     parecido): el nombre está conectado a otro Worker o proyecto de Pages,
     o tiene un registro DNS propio. En **Workers & Pages**, sacá ese
     dominio de donde esté; en **DNS**, borrá cualquier registro `A`, `AAAA`
     o `CNAME` de `p314b.space`. Después volvé a desplegar. Para volver
     atrás, alcanza con borrar el bloque `routes` de `wrangler.jsonc`.
2. **SSL/TLS**, en el resumen:
   - **Full (strict)**.
   - En **Edge Certificates**: *Always Use HTTPS* activado, *Automatic
     HTTPS Rewrites* activado, *Minimum TLS Version* 1.2 y *TLS 1.3*
     activado.
   - El HSTS ya lo manda el sitio: no hace falta activarlo también ahí.
3. **DNSSEC.** En **DNS → Settings**, activalo. Si el dominio no se compró
   en Cloudflare, copiá el registro DS que te muestra al registrador donde
   lo compraste.
4. **Security:**
   - *Bot Fight Mode* activado.
   - *Security Level* en Medium.
   - En **WAF**, reglas administradas gratuitas activadas.
5. **Las herramientas solo para vos (recomendado).** Con **Zero Trust →
   Access → Applications** (gratis hasta 50 personas), creá una
   aplicación *Self-hosted* para `www.p314b.space/acceso.html`,
   `/uploader-v1.html`, `/matriz.html` y `/formula_helper.html`, con una
   política *Allow* solo para tu correo. Sin el token ya no pueden hacer
   nada, pero así ni siquiera cargan para otros.
6. **Correo.** Si el dominio no manda mail, evitá que lo usen para
   suplantarte. En **DNS**, agregá:
   - `TXT @` → `v=spf1 -all`
   - `TXT _dmarc` → `v=DMARC1; p=reject;`
   - `MX @` → `0 .` (prioridad 0, destino `.`)
7. **Cuentas:**
   - Verificación en dos pasos en Cloudflare y en GitHub.
   - El token de `acceso.html` tiene que ser *fine-grained*: solo el repo
     p314b, Contents y Actions en lectura y escritura, con vencimiento.
     Cuando vence, el taller avisa «GitHub rechazó el token»: se genera
     uno nuevo con los mismos permisos y se pega en `acceso.html`.

## Al cambiar de dominio

El token de autora se guarda en el navegador, por dominio. Hay que volver
a pegarlo una vez en `https://www.p314b.space/acceso.html`, en cada
navegador que uses. En el dominio viejo convendría borrarlo: botón
«olvidar token».
