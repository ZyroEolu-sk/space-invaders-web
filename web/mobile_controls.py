#!/usr/bin/env python3
"""Anade controles tactiles al index.html publicado.

El juego lee el teclado con pygame.key.get_pressed(), asi que en un movil sin
teclado no hay forma de moverse. En vez de tocar el codigo del juego, se
superpone una botonera HTML que sintetiza los mismos eventos de teclado que
mandaria un teclado fisico: flechas para moverse y un boton para disparar.

Los botones solo aparecen en pantallas tactiles (@media (hover: none)), asi que
en escritorio no se ve nada.

Se ejecuta desde build.py; no hace falta llamarlo a mano.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

MARK = "id=\"mobile-controls\""

OVERLAY = """
<style>
#mobile-controls { display: none; }

/* Solo en dispositivos sin raton: moviles y tablets. */
@media (hover: none) and (pointer: coarse) {
  #mobile-controls {
    display: flex;
    position: fixed;
    left: 0; right: 0; bottom: 0;
    padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    z-index: 2147483647;
    pointer-events: none;
    font-family: system-ui, sans-serif;
  }
  #mobile-controls .grupo { display: flex; gap: 16px; }
  #mobile-controls button {
    pointer-events: auto;
    width: 74px; height: 74px;
    border-radius: 50%;
    border: 2px solid rgba(255,255,255,.55);
    background: rgba(0,0,0,.45);
    color: #fff;
    font-size: 30px;
    line-height: 1;
    display: flex; align-items: center; justify-content: center;
    /* Sin esto, el navegador interpreta los toques como scroll o zoom. */
    touch-action: none;
    -webkit-user-select: none; user-select: none;
    -webkit-tap-highlight-color: transparent;
  }
  #mobile-controls button:active {
    background: rgba(255,255,255,.35);
    transform: scale(.94);
  }
  #mobile-controls .disparo {
    width: 92px; height: 92px;
    font-size: 16px; letter-spacing: .05em;
    border-color: rgba(255,120,120,.8);
  }
}
</style>

<div id="mobile-controls">
  <div class="grupo">
    <button type="button" data-tecla="ArrowLeft" aria-label="Izquierda">&#9664;</button>
    <button type="button" data-tecla="ArrowRight" aria-label="Derecha">&#9654;</button>
  </div>
  <div class="grupo">
    <button type="button" class="disparo" data-tecla="Space" aria-label="Disparar">FIRE</button>
  </div>
</div>

<script>
(function () {
  // El juego mueve la nave con pygame.key.get_pressed(), que se alimenta de
  // keydown/keyup. Sintetizamos exactamente esos eventos: asi los controles
  // tactiles y el teclado fisico recorren el mismo camino y el juego no
  // necesita saber que existe un movil.
  var TECLAS = {
    ArrowLeft:  { key: "ArrowLeft",  code: "ArrowLeft",  keyCode: 37 },
    ArrowRight: { key: "ArrowRight", code: "ArrowRight", keyCode: 39 },
    Space:      { key: " ",          code: "Space",      keyCode: 32 }
  };

  function manda(tipo, info) {
    var ev = new KeyboardEvent(tipo, {
      key: info.key, code: info.code,
      keyCode: info.keyCode, which: info.keyCode,
      bubbles: true, cancelable: true
    });
    // El canvas es quien tiene el foco para SDL; si no existe aun, al documento.
    var destino = document.getElementById("canvas") || document.body;
    destino.dispatchEvent(ev);
    document.dispatchEvent(ev);
  }

  document.querySelectorAll("#mobile-controls button").forEach(function (boton) {
    var info = TECLAS[boton.dataset.tecla];
    var pulsado = false;

    function abajo(e) {
      e.preventDefault();
      if (pulsado) return;
      pulsado = true;
      manda("keydown", info);
    }
    function arriba(e) {
      e.preventDefault();
      if (!pulsado) return;
      pulsado = false;
      manda("keyup", info);
    }

    boton.addEventListener("touchstart", abajo, { passive: false });
    boton.addEventListener("touchend", arriba, { passive: false });
    boton.addEventListener("touchcancel", arriba, { passive: false });
    // Raton, para poder probarlo en escritorio con el modo movil del navegador.
    boton.addEventListener("mousedown", abajo);
    boton.addEventListener("mouseup", arriba);
    boton.addEventListener("mouseleave", arriba);
  });
})();
</script>
"""


def main():
    index = DIST / "index.html"
    if not index.is_file():
        sys.exit("No hay dist/index.html. Ejecuta antes: python build.py")

    html = index.read_text(encoding="utf-8")
    if MARK in html:
        print("Los controles tactiles ya estaban puestos.")
        return 0

    html, n = re.subn(r"</body>", OVERLAY + "</body>", html, count=1)
    if n != 1:
        # El template de pygbag no siempre cierra body; caemos al final del html.
        html, n = re.subn(r"</html>", OVERLAY + "</html>", html, count=1)
    if n != 1:
        html += OVERLAY

    index.write_text(html, encoding="utf-8")
    print("Controles tactiles anadidos (solo visibles en pantallas tactiles).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
