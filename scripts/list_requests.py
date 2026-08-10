#!/usr/bin/env python3
"""Lista todas las URLs externas que pide una carga real del juego.

Sirve para saber exactamente que ficheros hay que vendorizar, en vez de
adivinar nombres. Requiere un dist/ recien construido y sin vendorizar.
"""
import functools, http.server, socketserver, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
PORT = 8769


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("127.0.0.1", PORT), functools.partial(Q, directory=str(DIST)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()

from playwright.sync_api import sync_playwright

seen = {}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(viewport={"width": 900, "height": 800})
    page.on("response", lambda r: seen.setdefault(r.url, r.status))
    page.goto(f"http://127.0.0.1:{PORT}/index.html")
    page.wait_for_timeout(30000)
    page.mouse.click(450, 400)
    page.wait_for_timeout(8000)
    b.close()
httpd.shutdown()

print("=== EXTERNAS ===")
for url, status in sorted(seen.items()):
    if "127.0.0.1" not in url:
        print(f"  {status}  {url}")
print("\n=== LOCALES ===")
for url, status in sorted(seen.items()):
    if "127.0.0.1" in url:
        print(f"  {status}  {url}")
