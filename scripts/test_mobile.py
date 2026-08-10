#!/usr/bin/env python3
"""Comprueba que los controles tactiles mueven la nave de verdad.

Emula un movil (viewport pequeno, touch, sin raton) y compara el pixel de la
nave antes y despues de mantener pulsada una flecha. Si no se mueve, falla.
"""
import argparse, functools, http.server, socketserver, sys, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
PORT = 8771


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    args = ap.parse_args()

    httpd = None
    if not args.url:
        socketserver.TCPServer.allow_reuse_address = True
        httpd = socketserver.TCPServer(("127.0.0.1", PORT), functools.partial(Q, directory=str(DIST)))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
    target = args.url or f"http://127.0.0.1:{PORT}/index.html"

    shots = ROOT / "build" / "shots-mobile"
    shots.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        # iPhone-ish: pantalla tactil, sin raton -> la media query debe activarse.
        ctx = b.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
        )
        page = ctx.new_page()
        print(f"Cargando {target}")
        page.goto(target, wait_until="commit")
        page.wait_for_timeout(30000)

        visible = page.evaluate("""() => {
            const c = document.getElementById('mobile-controls');
            if (!c) return 'NO EXISTE';
            return getComputedStyle(c).display;
        }""")
        print(f"Botonera: display={visible}  (debe ser 'flex' en movil)")

        page.mouse.click(195, 400)   # pantalla de inicio -> partida
        page.wait_for_timeout(3000)
        page.screenshot(path=str(shots / "01-movil.png"))

        def pos_nave():
            # La nave es lo unico coloreado en la franja inferior del canvas.
            return page.evaluate("""() => {
                const c = document.getElementById('canvas');
                const g = c.getContext('2d');
                if (!g) return null;
                const y = Math.floor(c.height * 0.93);
                const d = g.getImageData(0, y, c.width, 1).data;
                let suma = 0, n = 0;
                for (let x = 0; x < c.width; x++) {
                    const i = x * 4;
                    if (d[i] + d[i+1] + d[i+2] > 90) { suma += x; n++; }
                }
                return n ? suma / n : null;
            }""")

        antes = pos_nave()
        print(f"Nave antes: {antes}")

        caja = page.locator('#mobile-controls button[data-tecla="ArrowLeft"]')
        caja.dispatch_event("touchstart")
        page.wait_for_timeout(1200)
        caja.dispatch_event("touchend")
        page.wait_for_timeout(500)

        despues = pos_nave()
        print(f"Nave despues de mantener IZQUIERDA: {despues}")
        page.screenshot(path=str(shots / "02-tras-izquierda.png"))

        ctx.close()
        b.close()
    if httpd:
        httpd.shutdown()

    if antes is None or despues is None:
        sys.exit("No pude localizar la nave en el canvas.")
    if despues < antes - 5:
        print(f"\nOK: la nave se movio {antes - despues:.0f} px a la izquierda.")
        return 0
    sys.exit(f"\nFALLO: la nave no se movio (antes={antes:.0f}, despues={despues:.0f}).")


if __name__ == "__main__":
    sys.exit(main())
