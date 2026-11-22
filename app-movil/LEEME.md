# Tallercito: la app del celular

App nativa de Android (Kotlin + Jetpack Compose, sin navegador adentro) para
escribir notas en el celular, sin conexión, y subirlas a la bandeja del
taller como borrador. Nada se publica desde el celular.

- **A · principal**: «＋ nuevo» → nuevo borrador (nota). Lista de los
  borradores que están en el celular, cada uno con su interruptor; abajo,
  «descartar» (pide desbloquear el celular) y «subir a la bandeja».
- **B · editor**: título, fechas, alineación, letra, tamaño, B / I / N
  (normal) y el cuadro de texto. Un borrador armado sumando notas se recorre
  por partes con ‹ ›. «Vista previa» → «regresar» / «siguiente».
- **C · destino**: ¿posteo nuevo? sí / no. Con «no», sumar al final de una
  nota o texto del sitio, o de otro borrador del tallercito (acumulación).
  «Guardar borrador» / «retornar a la pantalla principal» (si hay cambios
  sin guardar, pregunta si se descartan).
- Copias del taller («↓ al tallercito»): llegan como borrador; al subirlas,
  el taller compara los cambios y los incorpora en el mismo posteo.

Todo se guarda en el celular (`borradores.json` en la memoria de la app).
La llave que da el taller al vincular se guarda cifrada con el almacén de
claves de Android.

El buzón es `worker/tallercito.js` del repo privado; el lado del taller,
`sitio/tallercito-taller.js`.

## Armar

La arma el workflow `.github/workflows/tallercito.yml` (Gradle 8.9, JDK 17,
SDK 34). En main la APK queda en
https://github.com/p4p13b/p314b-code/releases/download/tallercito/tallercito.apk

En una máquina con el SDK de Android: `cd app-movil && gradle assembleDebug`.
