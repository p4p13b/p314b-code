# p314b-code

Código del sitio [p314b.space](https://www.p314b.space) y los workflows que
lo publican.

- **`.github/workflows/` y `.github/ci/`** son lo que está vivo: los
  workflows corren acá (en un repo público los minutos de Actions no se
  cobran) y trabajan sobre el repo privado de la autora, donde están las
  obras, los datos y `web/`. Ver `.github/ci/comun.sh`.
- **El resto** (`sitio/`, `worker/`, `tests/`…) es una copia del código al
  06/10/2026. El código vigente vive en el repo privado.

Los textos y las obras de p314b tienen su propia licencia (CC BY-NC-ND 4.0)
y no están en este repo.
