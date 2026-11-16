# Casa de vacaciones

Modelo 3D de la casa de vacaciones de la familia, hecho en Blender a partir de los planos del arquitecto y de las variantes que fue dibujando mi padre.

## Visita virtual

**https://winnerplus.github.io/VacationHouse/**

Se abre en el navegador del móvil o del ordenador, sin instalar nada:

- Al entrar se ve la casa desde fuera. Se gira con el dedo o el ratón, y abajo se pueden quitar el tejado y las plantas.
- Con **«Entrar en la casa»** se pasea por dentro: se toca o se hace clic en el suelo para ir allí, como en Google Maps, y se arrastra para mirar alrededor.
- Los botones de abajo llevan directamente a cada estancia.

## Versiones de la casa

| Archivo | Qué es |
|---|---|
| `Casa de vacaciones.blend` | Primera versión, con los planos oficiales acotados |
| `Casa A - con despensa.blend` | Planos nuevos: planta baja con despensa, planta primera sin terraza |
| `Casa B - con terraza.blend` | Planos nuevos: planta baja sin despensa, planta primera con galería |
| `Casa C - atico replanteado.blend` | Como la B, con la bajocubierta replanteada para que la escalera tenga altura libre |
| `Casa D - diseño final.blend` | **Diseño elegido**: planos finales con los arreglos de altura libre |

Las vistas renderizadas de cada versión están en `renders/`, `renders_A/`, `renders_B/`, `renders_C/` y `renders_D/`.

## Cómo se genera

Todo sale de scripts de Python que se ejecutan con Blender 5.2 en segundo plano:

```
blender -b -P casa2_build.py -- . D                                  # construye la casa D
blender -b "Casa D - diseño final.blend" -P casa2_render.py -- renders_D
blender -b "Casa D - diseño final.blend" -P casa_export_web.py -- docs/casa-d.json
```

- `casa_build.py` y `casa_render.py`: primera versión.
- `casa2_build.py` y `casa2_render.py`: casas A, B, C y D (variante como segundo argumento).
- `casa_export_web.py`: exporta una casa a glTF para el visor web.
- `docs/index.html`: el visor (three.js), que es lo que publica GitHub Pages.
- `visita/`: la misma visita en la versión para las páginas de Claude.
- `servidor_local.ps1`: servidor mínimo para probar la visita en local.
