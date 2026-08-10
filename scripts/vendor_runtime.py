#!/usr/bin/env python3
"""Descarga el runtime de pygbag y lo sirve desde el propio sitio.

Por defecto el index.html que genera pygbag carga el interprete de Python, el
.wasm y la rueda de pygame desde pygame-web.github.io en cada visita. Eso
significa que la partida depende de un tercero: si ese dominio cae, el juego no
arranca, y si algun dia sirviera un fichero distinto, se ejecutaria en el
navegador de quien entre.

Este script copia esos ficheros a dist/runtime/ y reescribe index.html y el
indice de paquetes para que apunten ahi. El resultado es una web autocontenida.
La lista de ficheros salio de registrar las peticiones de una carga real
(scripts/list_requests.py), no de adivinar nombres.

Se ejecuta desde build.py; no hace falta llamarlo a mano.
"""

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

CDN_ROOT = "https://pygame-web.github.io/cdn/"

# Ficheros que el template referencia pero que ya no existen en el CDN.
# Se quitan del html en vez de intentar descargarlos.
BROKEN = ["browserfs.min.js"]


def detect_version(html):
    """Saca la version de pygbag del propio index.html generado."""
    m = re.search(r"https://pygame-web\.github\.io/cdn/(\d+\.\d+\.\d+)/", html)
    if not m:
        sys.exit("No encuentro la version del CDN en dist/index.html")
    return m.group(1)


def fetch(rel, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(CDN_ROOT + rel, timeout=180) as r:
            dest.write_bytes(r.read())
        return dest.stat().st_size
    except urllib.error.HTTPError as e:
        return -e.code
    except Exception:
        return -1


def pygame_wheel(index_path, py):
    """Resuelve el nombre real de la rueda de pygame desde el indice."""
    data = json.loads(index_path.read_text(encoding="utf-8"))
    tmpl = data.get("pygame")
    if not tmpl:
        return None
    return tmpl.replace("<abi>", f"cp{py}").replace("<api>", "wasm32_bi_emscripten")


def main():
    index = DIST / "index.html"
    if not index.is_file():
        sys.exit("No hay dist/index.html. Ejecuta antes: python build.py")

    html = index.read_text(encoding="utf-8")
    version = detect_version(html)
    py = "312"
    runtime = DIST / "runtime"

    files = [
        f"{version}/pythons.js",
        f"{version}/cpython{py}/main.js",
        f"{version}/cpython{py}/main.data",
        f"{version}/cpython{py}/main.wasm",
        f"{version}/cpythonrc.py",
        f"{version}/empty.html",
        f"index-{version}-cp{py}.json",
        "vtx.js",
        "vt/xterm.js",
        "vt/xterm.css",
        "vt/xterm-addon-image.js",
    ]

    print(f"Vendorizando el runtime de pygbag {version} en dist/runtime/:")
    total, missing = 0, []
    for rel in files:
        size = fetch(rel, runtime / rel)
        if size < 0:
            missing.append(rel)
            print(f"  FALTA  {rel}  (HTTP {-size})")
        else:
            total += size
            print(f"  ok     {rel}  ({size / 1024:.0f} KiB)")

    # La rueda de pygame no tiene nombre fijo: sale del indice de paquetes.
    index_json = runtime / f"index-{version}-cp{py}.json"
    wheel = pygame_wheel(index_json, py) if index_json.is_file() else None
    if wheel:
        size = fetch(wheel, runtime / wheel)
        if size < 0:
            missing.append(wheel)
            print(f"  FALTA  {wheel}  (HTTP {-size})")
        else:
            total += size
            print(f"  ok     {wheel}  ({size / 1024:.0f} KiB)")
    else:
        missing.append("rueda de pygame (no aparece en el indice)")

    # El indice apunta al CDN para resolver las ruedas: redirigirlo a la copia.
    if index_json.is_file():
        data = json.loads(index_json.read_text(encoding="utf-8"))
        data["-CDN-"] = "runtime/"
        index_json.write_text(json.dumps(data, indent=4), encoding="utf-8")
        print("  reescrito -CDN- del indice de paquetes -> runtime/")

    for name in BROKEN:
        html, n = re.subn(rf'\s*<script src="[^"]*{re.escape(name)}"></script>', "", html)
        if n:
            print(f"  quitado <script> roto: {name}")

    # El template mete un doble slash en algunas URLs; se normaliza de paso.
    html = html.replace(f"{CDN_ROOT}{version}//", f"runtime/{version}/")
    html = html.replace(f"{CDN_ROOT}{version}/", f"runtime/{version}/")
    html = html.replace(CDN_ROOT, "runtime/")

    # vtx.js hace un import() dinamico concatenando este valor, y un import()
    # solo acepta URL absoluta o especificador que empiece por ./ o ../: una
    # ruta relativa pelada da "Failed to resolve module specifier". Con el CDN
    # no se notaba porque era una URL https completa. Lo resolvemos contra
    # document.baseURI en tiempo de ejecucion, que ademas funciona igual si el
    # sitio cuelga de un subdirectorio (github.io/<repo>/) que de la raiz.
    html, n = re.subn(
        rf'cdn *: *"runtime/{re.escape(version)}/"',
        f'cdn : new URL("runtime/{version}/", document.baseURI).href',
        html,
    )
    if n != 1:
        print(f"  AVISO: esperaba 1 config 'cdn', encontre {n}")
    else:
        print("  cdn del runtime resuelto a URL absoluta en tiempo de ejecucion")

    # Red de seguridad: el indice de paquetes (y de ahi la rueda de pygame) se
    # pide desde el interprete ya dentro del .wasm, con la URL del CDN cocida
    # dentro, asi que reescribir el html no basta. En vez de perseguir donde se
    # construye cada URL, interceptamos fetch() y redirigimos al vendorizado.
    shim = (
        "<script>\n"
        "(function () {\n"
        '  var CDN = "https://pygame-web.github.io/cdn/";\n'
        '  var LOCAL = new URL("runtime/", document.baseURI).href;\n'
        "  function local(u) {\n"
        "    u = String(u);\n"
        "    return u.indexOf(CDN) === 0 ? LOCAL + u.slice(CDN.length) : u;\n"
        "  }\n"
        "  var _fetch = window.fetch;\n"
        "  window.fetch = function (input, init) {\n"
        '    if (typeof input === "string") input = local(input);\n'
        "    else if (input && input.url) input = new Request(local(input.url), input);\n"
        "    return _fetch.call(this, input, init);\n"
        "  };\n"
        "})();\n"
        "</script>\n"
    )
    if "var CDN =" not in html:
        html = re.sub(r"(<html[^>]*>)", r"\1" + shim, html, count=1)
        print("  inyectado shim que redirige el CDN al runtime local")

    index.write_text(html, encoding="utf-8")

    leftover = sorted(set(re.findall(r"https://pygame-web\.github\.io[^\s\"')]*", html)))
    # La URL dentro del shim es la que se intercepta, no una dependencia.
    leftover = [u for u in leftover if u.rstrip("/") != CDN_ROOT.rstrip("/")]
    print(f"\nRuntime local: {total / 1024 / 1024:.1f} MiB")

    if leftover:
        print("Quedan referencias al CDN en index.html:")
        for u in leftover:
            print("  ", u)
    else:
        print("index.html ya no referencia el CDN.")

    if missing:
        print(f"\nAVISO: {len(missing)} fichero(s) sin descargar:")
        for m in missing:
            print("  ", m)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
