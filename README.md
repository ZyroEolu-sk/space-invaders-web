# Space Invaders — versión web

Port a navegador de [space-invaders-game](https://github.com/ZyroEolu-sk/space-invaders-game),
el Space Invaders en Pygame hecho por [ZyroEolu-sk](https://github.com/ZyroEolu-sk)
y [pvinas23](https://github.com/pvinas23).

Este repo **no contiene el juego**: lo incluye como submódulo y solo añade lo
necesario para compilarlo a WebAssembly con [pygbag](https://github.com/pygame-web/pygbag)
y publicarlo como web estática. El código del juego no se toca nunca.

## Cómo está montado

```
.
├── game/                    submódulo -> space-invaders-game (solo lectura)
├── web/
│   ├── main.py              arranque del build web
│   └── storage.py           récord en localStorage
├── scripts/
│   ├── vendor_runtime.py    descarga el runtime de pygbag al propio sitio
│   ├── smoke_test.py        abre el juego en Chromium y comprueba que arranca
│   └── list_requests.py     lista las URLs externas de una carga real
├── build.py                 prepara el staging y compila
└── .github/workflows/       despliegue a GitHub Pages
```

`build.py` **lee** `game/`, escribe una copia transformada en `build/` y compila
esa copia. El submódulo nunca se modifica.

## Los cuatro ajustes que exige el navegador

1. **Bucle asíncrono.** El navegador es monohilo: un `while True` que nunca
   devuelve el control congela la pestaña. `build.py` convierte `run()` en
   corutina y le mete un `await asyncio.sleep(0)` por frame. Es lo único que se
   transforma del código original; el resto se copia tal cual.
2. **Submódulos de pygame.** pygbag los carga de forma perezosa, así que
   `import pygame` a secas deja `pygame.sprite` sin definir y `ui.py` revienta
   al importarse. `web/main.py` los fuerza antes de cargar el juego.
3. **Récord.** El sistema de ficheros de WebAssembly es efímero y `score.json`
   se perdería al recargar. `web/storage.py` usa `localStorage` en navegador y
   `score.json` en escritorio.
4. **Botón Quit.** En una pestaña no existe "cerrar el programa", así que
   `sys.exit()` pasa a devolver al jugador a la pantalla de inicio.

Además, `assets/audio/` no entra en el paquete mientras ningún módulo del juego
use sonido — son dos `.mp3` huérfanos, y pygbag aborta el build con MP3 porque
no es un formato válido en web. La comprobación se rehace en cada build: el día
que el juego use audio de verdad, vuelve a copiarse solo (y entonces conviene
que sea `.ogg`).

## Compilar en local

```bash
python -m venv .venv && source .venv/bin/activate
pip install pygbag
python build.py           # resultado en dist/
python build.py --serve   # y lo sirve en http://localhost:8000
```

## Actualizar el juego

El submódulo apunta a un commit concreto, así que la web es reproducible: no
cambia sola. Para traer los últimos cambios del original:

```bash
git submodule update --remote game
git commit -am "actualizar el juego"
git push
```

El push dispara el despliegue.

Si algún día `build.py` falla con un error de transformación, significa que el
bucle principal del juego cambió lo bastante como para que el patrón ya no
encaje. El mensaje dice qué patrón falló; se actualiza en `build.py`. Falla
ruidosamente a propósito: mejor eso que publicar una web rota en silencio.

## Nota sobre el runtime

Por defecto pygbag genera un `index.html` que descarga el intérprete de Python
(~22 MB) desde `pygame-web.github.io` en cada visita. `scripts/vendor_runtime.py`
se lo trae al propio sitio durante el build, de modo que la web publicada no
hace **ninguna** petición externa: ni depende de que ese dominio siga en pie, ni
de que sirva siempre lo mismo. Verificado bloqueando todo el tráfico externo:

```bash
python scripts/smoke_test.py --offline
```

Para volver al comportamiento por defecto: `python build.py --no-vendor`.

## Publicar

En GitHub: **Settings → Pages → Source: GitHub Actions**. A partir de ahí, cada
push a `main` compila y publica.
