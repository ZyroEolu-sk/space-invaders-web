#!/usr/bin/env python3
"""Prueba el juego con toques reales, no con clicks de raton emulados.

Comprueba tres cosas que en un movil pueden fallar por separado:
  1. que un toque en el lienzo arranque la partida (los menus del juego usan
     MOUSEBUTTONDOWN, y un dedo no es un raton),
  2. que el boton de pausa pause,
  3. que vuelva a reanudar, sin depender de los botones Resume/Quit del menu.
"""
import argparse, functools, http.server, socketserver, sys, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
PORT = 8772


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def firma(page):
    """Huella del lienzo entero, para detectar si la imagen cambia o se congela.

    Muestrear solo la franja de arriba no vale: es casi toda negra y la firma
    no cambia aunque el juego este corriendo. Hay que barrer todo el lienzo y
    con paso fino, porque lo que se mueve (estrellas, balas) son pocos pixeles.
    """
    return page.evaluate("""() => {
        const c = document.getElementById('canvas');
        const g = c.getContext('2d');
        if (!g) return null;
        const d = g.getImageData(0, 0, c.width, c.height).data;
        let s = 0, n = 0;
        for (let i = 0; i < d.length; i += 4) {
            if (d[i] + d[i+1] + d[i+2] > 40) { s = (s + i) % 1000000007; n++; }
        }
        return s + ':' + n;
    }""")


def hay_menu_pausa(page):
    """Detecta el menu de pausa por el marco blanco del boton Resume.

    No sirve mirar si el lienzo se congela: draw_bg_and_ui() se llama fuera
    del `if not self.paused`, asi que las estrellas siguen moviendose en pausa.
    Button("Resume", 40, 220, 80, 240, 240) -> marco blanco en (238,238)-(462,322).
    """
    return page.evaluate("""() => {
        const c = document.getElementById('canvas');
        const g = c.getContext('2d');
        if (!g) return 0;
        const d = g.getImageData(238, 238, 226, 6).data;
        let blancos = 0;
        for (let i = 0; i < d.length; i += 4) {
            if (d[i] > 240 && d[i+1] > 240 && d[i+2] > 240) blancos++;
        }
        return blancos;
    }""")


def se_mueve(page, ms=1200):
    """True si el lienzo cambia en ese intervalo (o sea, el juego avanza)."""
    a = firma(page)
    page.wait_for_timeout(ms)
    return a != firma(page)


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

    shots = ROOT / "build" / "shots-touch"
    shots.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    fallos = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3, is_mobile=True, has_touch=True,
        )
        page = ctx.new_page()
        print(f"Cargando {target}")
        page.goto(target, wait_until="commit")
        page.wait_for_timeout(30000)
        page.screenshot(path=str(shots / "01-inicio.png"))

        # 1. Toque real en el lienzo para salir de la pantalla de inicio.
        page.touchscreen.tap(195, 420)
        page.wait_for_timeout(4000)
        page.screenshot(path=str(shots / "02-tras-toque.png"))

        arrancado = se_mueve(page)  # en partida las estrellas se mueven
        print(f"1. Toque arranca la partida: {'SI' if arrancado else 'NO'}")
        if not arrancado:
            fallos.append("un toque en el lienzo no arranca la partida")

        # 2. El boton debe estar VISIBLE, no solo existir en el DOM.
        visible = page.locator("#mobile-pause").is_visible()
        print(f"2a. Boton de pausa visible en movil: {'SI' if visible else 'NO'}")
        if not visible:
            fallos.append("el boton de pausa no se ve en movil")

        # 2b. Pausa con el boton.
        page.locator("#mobile-pause").dispatch_event("touchstart")
        page.locator("#mobile-pause").dispatch_event("touchend")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(shots / "03-pausa.png"))
        pausado = hay_menu_pausa(page) > 100

        # En pausa el fondo tampoco debe moverse.
        quieto = not se_mueve(page)
        print(f"2c. El fondo se queda quieto en pausa: {'SI' if quieto else 'NO'}")
        if not quieto:
            fallos.append("las estrellas siguen moviendose en pausa")
        print(f"2b. El boton de pausa abre el menu: {'SI' if pausado else 'NO'}")
        if not pausado:
            fallos.append("el boton de pausa no pausa")

        # 3. Reanudar con el mismo boton.
        page.locator("#mobile-pause").dispatch_event("touchstart")
        page.locator("#mobile-pause").dispatch_event("touchend")
        page.wait_for_timeout(1500)
        reanudado = hay_menu_pausa(page) < 50
        print(f"3. El mismo boton reanuda: {'SI' if reanudado else 'NO'}")
        if not reanudado:
            fallos.append("no se puede reanudar tras pausar")
        page.screenshot(path=str(shots / "04-reanudado.png"))

        ctx.close()
        b.close()
    if httpd:
        httpd.shutdown()

    print(f"\nCapturas en {shots}")
    if fallos:
        print("\nFALLOS:")
        for f in fallos:
            print("  -", f)
        return 1
    print("\nTodo OK con toques reales.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
