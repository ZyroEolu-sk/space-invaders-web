#!/usr/bin/env python3
"""Prueba de humo del build web.

Sirve dist/ con un servidor estatico pelado (que es justo lo que es GitHub
Pages: sin cabeceras especiales, sin nada) y lo abre en Chromium para
comprobar que el juego arranca de verdad, no solo que compila.

Uso:
    python scripts/smoke_test.py [--headed] [--shots DIR]
"""

import argparse
import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
PORT = 8765


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    handler = functools.partial(QuietHandler, directory=str(DIST))
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--shots", default=str(ROOT / "build" / "shots"))
    parser.add_argument(
        "--offline",
        action="store_true",
        help="bloquea toda peticion fuera de localhost; si el juego sigue "
             "arrancando, la web es autocontenida de verdad",
    )
    args = parser.parse_args()

    if not (DIST / "index.html").is_file():
        sys.exit("No hay dist/index.html. Ejecuta antes: python build.py")

    shots = Path(args.shots)
    shots.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    httpd = serve()
    errors, logs = [], []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 900, "height": 800})

        page.on("console", lambda m: (logs.append(f"{m.type}: {m.text}"),
                                      errors.append(m.text) if m.type == "error" else None))
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        blocked = []
        if args.offline:
            def guard(route, request):
                if "127.0.0.1" in request.url or "localhost" in request.url:
                    route.continue_()
                else:
                    blocked.append(request.url)
                    route.abort()

            page.route("**/*", guard)

        page.goto(f"http://127.0.0.1:{PORT}/index.html")

        # pygbag tapa el canvas con un overlay de "pulsa para empezar" hasta que
        # hay una interaccion del usuario; el navegador lo exige para el audio.
        page.wait_for_timeout(3000)
        page.mouse.click(450, 400)

        # Descargar el runtime, montar el .apk y arrancar el interprete tarda.
        page.wait_for_timeout(25000)
        page.screenshot(path=str(shots / "01-arranque.png"))

        # Pasar de la pantalla de inicio a la partida.
        page.mouse.click(450, 400)
        page.wait_for_timeout(4000)
        page.screenshot(path=str(shots / "02-partida.png"))

        # Mover y disparar, para confirmar que responde al teclado.
        for _ in range(3):
            page.keyboard.press("ArrowLeft")
            page.keyboard.press("Space")
            page.wait_for_timeout(300)
        page.wait_for_timeout(2000)
        page.screenshot(path=str(shots / "03-input.png"))

        browser.close()

    httpd.shutdown()

    print(f"Capturas en {shots}")

    if args.offline:
        if blocked:
            print(f"\n--- {len(blocked)} PETICION(ES) EXTERNA(S) BLOQUEADA(S) ---")
            for u in sorted(set(blocked)):
                print(" ", u)
        else:
            print("\nCero peticiones externas: la web es autocontenida.")

    print(f"\n--- consola ({len(logs)} lineas) ---")
    for line in logs:
        print(" ", line)

    real = [e for e in errors if "favicon" not in e.lower()]
    if real:
        print(f"\n--- {len(real)} ERROR(ES) ---")
        for e in real[:20]:
            print(" ", e)
        sys.exit(1)

    print("\nSin errores de consola.")


if __name__ == "__main__":
    main()
