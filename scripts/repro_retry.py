#!/usr/bin/env python3
"""Reproduce el fallo al pulsar Retry en la pantalla de Game Over.

Deja que el jugador muera solo, pulsa Retry y captura consola y traceback.
"""
import argparse, functools, http.server, socketserver, sys, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
PORT = 8770

# El juego mide 700x650 y se dibuja escalado dentro del viewport de 900x800.
GAME_W, GAME_H = 700, 650
VIEW_W, VIEW_H = 900, 800
SCALE = VIEW_H / GAME_H
OFFSET_X = (VIEW_W - GAME_W * SCALE) / 2


def to_page(x, y):
    return OFFSET_X + x * SCALE, y * SCALE


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def dom_traceback(page):
    """Los tracebacks de Python de pygbag se pintan en el DOM, no en la consola JS."""
    return page.evaluate(r"""() => {
        const hits = [];
        const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        let n;
        while ((n = walk.nextNode())) {
            const t = (n.nodeValue || '').trim();
            if (/Traceback|ZeroDivision|Error:|Exception/.test(t) && !/globalThis|function|console\./.test(t)) {
                hits.push(t.slice(0, 300));
            }
        }
        return hits.join('\n');
    }""")


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

    shots = ROOT / "build" / "shots-retry"
    shots.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    logs = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page(viewport={"width": VIEW_W, "height": VIEW_H})
        page.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
        page.on("pageerror", lambda e: logs.append(f"PAGEERROR: {e}"))

        print(f"Cargando {target}")
        page.goto(target, wait_until="commit")
        page.wait_for_timeout(28000)

        # Pantalla de inicio -> partida
        page.mouse.click(VIEW_W / 2, VIEW_H / 2)
        page.wait_for_timeout(1500)

        # Jugar de verdad: moverse y disparar para pasar de nivel.
        print("Jugando...")
        import itertools
        for i in itertools.count():
            page.keyboard.press("Space")
            page.keyboard.press("ArrowLeft" if (i // 4) % 2 else "ArrowRight")
            page.wait_for_timeout(120)
            if i % 50 == 0 and dom_traceback(page):
                print(f"\n!!! Traceback JUGANDO (iteracion {i}) !!!")
                print(dom_traceback(page))
                break
            if i > 700:
                break

        page.screenshot(path=str(shots / "01-antes-de-retry.png"))

        marca = len(logs)
        tb_antes = dom_traceback(page)

        # Boton Retry: Button("Retry", 25, 90, 40, WINDOW_WIDTH/2-45, 450)
        bx, by = to_page(GAME_W / 2 - 45 + 45, 450 + 20)
        print(f"Click en Retry -> pagina ({bx:.0f}, {by:.0f})")
        page.mouse.click(bx, by)
        page.wait_for_timeout(3000)

        # Tras el Retry, seguir jugando: si el fallo esta en el estado que
        # reset_game() no limpia, saltara al reanudarse la partida.
        for i in range(120):
            page.keyboard.press("Space")
            page.keyboard.press("ArrowLeft" if (i // 4) % 2 else "ArrowRight")
            page.wait_for_timeout(120)

        page.screenshot(path=str(shots / "02-despues-de-retry.png"))
        tb_despues = dom_traceback(page)

        b.close()
    if httpd:
        httpd.shutdown()

    print(f"\n--- consola DESPUES de pulsar Retry ({len(logs) - marca} lineas) ---")
    for line in logs[marca:]:
        print(" ", line)
    if len(logs) == marca:
        print("  (nada nuevo en consola JS)")

    print("\n--- TRACEBACK EN EL DOM ---")
    print("ANTES de Retry:", tb_antes or "(ninguno)")
    print("DESPUES de Retry:", tb_despues or "(ninguno)")

    print(f"\nCapturas en {shots}")


if __name__ == "__main__":
    main()
