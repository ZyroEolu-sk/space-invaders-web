#!/usr/bin/env python3
"""Compila el juego a WebAssembly con pygbag.

El submodulo game/ es de solo lectura: este script nunca escribe dentro de el.
Lo que hace es copiar sus fuentes a build/stage/, aplicar ahi las pocas
transformaciones que el navegador exige, y compilar esa copia.

Por que transformar en vez de un .patch: un parche depende del contexto de las
lineas de alrededor y se rompe en cuanto se edita el bucle principal, que es
justo la parte del juego que mas se toca. Las sustituciones de abajo van
dirigidas a construcciones concretas y aguantan que el fichero se reordene. Si
alguna deja de encajar, el build falla con un mensaje explicito en lugar de
producir una web rota en silencio.

Uso:
    python build.py            # compila a dist/
    python build.py --serve    # compila y sirve en http://localhost:8000
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GAME_SRC = ROOT / "game" / "src"
GAME_ASSETS = ROOT / "game" / "assets"
WEB = ROOT / "web"
# El nombre de esta carpeta acaba siendo el del .apk que descarga el navegador.
STAGE = ROOT / "build" / "space-invaders"
DIST = ROOT / "dist"

APP_NAME = "space-invaders"
APP_TITLE = "Space Invaders"

# Mismo tamano que WINDOW_WIDTH/WINDOW_HEIGHT en settings.py: si el framebuffer
# no coincide, el navegador escala el juego y se ve borroso.
WIDTH, HEIGHT = 700, 650

# src/main.py se copia con otro nombre para que no choque con el main.py de
# arranque que pygbag exige en la raiz del paquete.
GAME_MAIN = "main.py"
GAME_MAIN_STAGED = "game_main.py"


# Si aparece cualquiera de estas pistas en el codigo, el juego usa audio.
AUDIO_HINTS = re.compile(r"mixer|\.mp3|\.ogg|\.wav|\.flac|Sound\(|music", re.IGNORECASE)


class TransformError(RuntimeError):
    """El codigo del juego cambio y una transformacion ya no encaja."""


def audio_is_used(sources):
    return any(AUDIO_HINTS.search(text) for text in sources)


def _sub(pattern, repl, text, expected, what):
    """Sustituye exigiendo un numero exacto de coincidencias."""
    new, found = re.subn(pattern, repl, text, flags=re.MULTILINE)
    if found != expected:
        raise TransformError(
            f"[{what}] esperaba {expected} coincidencia(s) en game/src/{GAME_MAIN}, "
            f"encontre {found}.\n"
            f"    El codigo del juego ha cambiado y la adaptacion a web ya no encaja.\n"
            f"    Revisa game/src/{GAME_MAIN} y actualiza el patron en build.py."
        )
    return new


def transform_game_main(text):
    """Convierte el bucle principal en asincrono.

    Es lo unico que no se puede resolver desde fuera: el navegador es
    monohilo, y un `while True` que nunca devuelve el control congela la
    pestana entera. Cediendo una vez por frame, el navegador puede repintar y
    atender eventos. En escritorio un `await asyncio.sleep(0)` a 60 fps no
    tiene efecto observable.
    """
    text = _sub(
        r"^import pygame$",
        "import pygame\nimport asyncio",
        text,
        1,
        "importar asyncio",
    )
    text = _sub(
        r"^    def run\(self\):$",
        "    async def run(self):",
        text,
        1,
        "convertir run() en corutina",
    )
    text = _sub(
        r"^([ \t]*)pygame\.display\.update\(\)$",
        r"\1pygame.display.update()\n\1await asyncio.sleep(0)",
        text,
        2,
        "ceder el control una vez por frame",
    )
    return text


def stage():
    """Prepara build/stage/ con el layout que espera pygbag."""
    if not GAME_SRC.is_dir():
        sys.exit(
            "No encuentro game/src/. El submodulo no esta inicializado.\n"
            "    Ejecuta: git submodule update --init --recursive"
        )

    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / "src").mkdir(parents=True)

    # El layout src/ + assets/ se conserva tal cual para que el BASE_DIR que
    # settings.py calcula a partir de __file__ siga apuntando donde debe.
    modules = sorted(GAME_SRC.glob("*.py"))
    if not any(m.name == GAME_MAIN for m in modules):
        raise TransformError(f"No encuentro game/src/{GAME_MAIN}")

    sources = []
    for module in modules:
        text = module.read_text(encoding="utf-8")
        sources.append(text)
        name = module.name
        if name == GAME_MAIN:
            text = transform_game_main(text)
            name = GAME_MAIN_STAGED
        (STAGE / "src" / name).write_text(text, encoding="utf-8")
        print(f"  src/{module.name} -> src/{name}")

    # pygbag rechaza el mp3 en web: intenta convertirlo a ogg con ffmpeg y, si
    # no lo encuentra, aborta el build entero. El juego arrastra dos mp3 que no
    # usa nadie, asi que no tiene sentido meterlos en el paquete. La condicion
    # se recalcula en cada build: el dia que el juego use audio de verdad,
    # vuelven a copiarse solos.
    ignore = None
    if audio_is_used(sources):
        print("  assets/ -> assets/  (el juego usa audio: se copia entero)")
    else:
        ignore = shutil.ignore_patterns("audio")
        print("  assets/ -> assets/  (sin audio: el juego no lo usa)")

    shutil.copytree(GAME_ASSETS, STAGE / "assets", ignore=ignore)

    for extra in ("main.py", "storage.py"):
        shutil.copy(WEB / extra, STAGE / extra)
        print(f"  web/{extra} -> {extra}")


def compile_web(serve):
    cmd = [
        sys.executable, "-m", "pygbag",
        "--app_name", APP_NAME,
        "--title", APP_TITLE,
        "--width", str(WIDTH),
        "--height", str(HEIGHT),
        # Por defecto pygbag espera un gesto del usuario antes de arrancar el
        # interprete, pensado para juegos con audio. Este no usa audio, asi que
        # el bloqueo solo anade una pantalla intermedia inutil.
        "--ume_block", "0",
    ]
    if not serve:
        cmd.append("--build")
    cmd.append(str(STAGE))

    print(f"\n$ {' '.join(cmd)}\n")
    subprocess.run(cmd, check=True)


def collect():
    """Copia el resultado de pygbag a dist/."""
    built = STAGE / "build" / "web"
    if not built.is_dir():
        sys.exit(f"pygbag no dejo nada en {built}")

    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(built, DIST)


def dist_size():
    return sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--serve",
        action="store_true",
        help="tras compilar, levanta un servidor local para probarlo",
    )
    parser.add_argument(
        "--no-vendor",
        action="store_true",
        help="no descargar el runtime; la web dependera del CDN de pygbag",
    )
    args = parser.parse_args()

    # Sin esto los prints del script salen despues de los del subproceso.
    sys.stdout.reconfigure(line_buffering=True)

    print("Preparando el staging desde el submodulo (solo lectura):")
    try:
        stage()
    except TransformError as exc:
        sys.exit(f"\nERROR: {exc}")

    compile_web(args.serve)

    if args.serve:
        return

    collect()

    if args.no_vendor:
        print("\nAVISO: sin vendorizar, la web dependera del CDN de pygbag.")
    else:
        print()
        rc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "vendor_runtime.py")]
        ).returncode
        if rc != 0:
            sys.exit(
                "\nEl vendorizado del runtime no se completo. La web puede "
                "seguir dependiendo del CDN de pygbag."
            )

    print()
    if subprocess.run([sys.executable, str(WEB / "mobile_controls.py")]).returncode != 0:
        sys.exit("No se pudieron anadir los controles tactiles.")

    print(f"\nListo: {DIST}  ({dist_size() / 1024 / 1024:.1f} MiB)")


if __name__ == "__main__":
    main()
