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
/* Ocultos por defecto. Estas dos reglas van ANTES del media query: tienen la
   misma especificidad, asi que si fueran despues ganarian ellas y los botones
   no se verian nunca. */
#mobile-controls { display: none; }
#mobile-pause { display: none; }

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

  /* La pausa va arriba y pequena: se usa poco y no debe estorbar al pulgar. */
  #mobile-pause {
    display: block;
    position: fixed;
    top: calc(10px + env(safe-area-inset-top));
    right: 10px;
    z-index: 2147483647;
    width: 46px; height: 46px;
    border-radius: 10px;
    border: 2px solid rgba(255,255,255,.45);
    background: rgba(0,0,0,.45);
    color: #fff;
    font-size: 17px;
    touch-action: none;
    -webkit-user-select: none; user-select: none;
    -webkit-tap-highlight-color: transparent;
  }
  #mobile-pause:active { background: rgba(255,255,255,.35); }
}
</style>

<button type="button" id="mobile-pause" data-tecla="Escape" aria-label="Pausa">&#10074;&#10074;</button>

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
    Space:      { key: " ",          code: "Space",      keyCode: 32 },
    // El juego alterna la pausa en el KEYDOWN de Escape, asi que el mismo
    // boton pausa y reanuda. Importa: los botones Resume/Quit del menu de
    // pausa se pulsan con raton, y en un movil puede no haber raton.
    Escape:     { key: "Escape",     code: "Escape",     keyCode: 27 }
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

  // Puente toque -> raton. pygbag NO convierte los toques en eventos de raton,
  // y el juego usa MOUSEBUTTONDOWN para "press to start" y para los botones
  // Resume / Retry / Quit. Sin esto, en un movil se puede jugar pero no se
  // puede empezar ni reintentar: te quedas mirando la pantalla de Game Over.
  (function puenteTactil() {
    var canvas = document.getElementById("canvas");
    if (!canvas) { setTimeout(puenteTactil, 300); return; }

    function raton(tipo, toque) {
      canvas.dispatchEvent(new MouseEvent(tipo, {
        clientX: toque.clientX, clientY: toque.clientY,
        button: 0, buttons: tipo === "mousedown" ? 1 : 0,
        bubbles: true, cancelable: true
      }));
    }

    canvas.addEventListener("touchstart", function (e) {
      if (e.changedTouches.length) raton("mousedown", e.changedTouches[0]);
      e.preventDefault();
    }, { passive: false });

    canvas.addEventListener("touchend", function (e) {
      if (e.changedTouches.length) raton("mouseup", e.changedTouches[0]);
      e.preventDefault();
    }, { passive: false });
  })();

  // Si el juego revienta, main.py deja el traceback en localStorage. Lo
  // sacamos en pantalla: un jugador no va a abrir la consola del navegador,
  // pero si puede hacer una foto de esto.
  (function muestraErrores() {
    var CLAVE = "space_invaders_last_error";
    setInterval(function () {
      var texto;
      try { texto = localStorage.getItem(CLAVE); } catch (e) { return; }
      if (!texto || document.getElementById("error-juego")) return;

      var caja = document.createElement("div");
      caja.id = "error-juego";
      caja.style.cssText =
        "position:fixed;inset:0;z-index:2147483647;overflow:auto;" +
        "background:rgba(0,0,0,.92);color:#ff8080;padding:20px;" +
        "font:12px/1.45 ui-monospace,Menlo,Consolas,monospace;white-space:pre-wrap";
      // Ojo: \\n escapado, porque esto vive dentro de una cadena de Python y
      // un salto de linea real romperia el literal de JavaScript.
      caja.textContent =
        "El juego ha fallado. Haz una captura de esto y pasasela a quien lo mantiene:\\n\\n" + texto;

      var cerrar = document.createElement("button");
      cerrar.textContent = "Cerrar y borrar";
      cerrar.style.cssText =
        "display:block;margin-top:20px;padding:10px 18px;font-size:14px;" +
        "background:#333;color:#fff;border:1px solid #888;border-radius:8px";
      cerrar.onclick = function () {
        try { localStorage.removeItem(CLAVE); } catch (e) {}
        caja.remove();
      };
      caja.appendChild(cerrar);
      document.body.appendChild(caja);
    }, 1000);
  })();

  var botones = document.querySelectorAll("#mobile-controls button, #mobile-pause");
  botones.forEach(function (boton) {
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

    # El reemplazo va como lambda a proposito: re.sub interpreta las secuencias
    # de escape de la cadena de reemplazo, asi que un "\\n" del JavaScript se
    # convertiria en un salto de linea real y romperia el literal.
    html, n = re.subn(r"</body>", lambda _: OVERLAY + "</body>", html, count=1)
    if n != 1:
        # El template de pygbag no siempre cierra body; caemos al final del html.
        html, n = re.subn(r"</html>", lambda _: OVERLAY + "</html>", html, count=1)
    if n != 1:
        html += OVERLAY

    index.write_text(html, encoding="utf-8")
    print("Controles tactiles anadidos (solo visibles en pantallas tactiles).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
