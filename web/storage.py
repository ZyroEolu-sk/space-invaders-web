"""Persistencia del record maximo.

En el navegador el sistema de ficheros de WebAssembly es efimero: cualquier
cosa que escribamos desaparece al recargar la pagina. Por eso ahi guardamos en
localStorage, que si sobrevive entre sesiones. En escritorio seguimos usando un
score.json normal para no cambiar el comportamiento original.
"""

import json
import os
import sys

KEY = "space_invaders_highscore"
IS_WEB = sys.platform == "emscripten"

_LOCAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "score.json")


def _browser_storage():
    """Devuelve el localStorage del navegador, o None si no estamos en uno."""
    if not IS_WEB:
        return None
    try:
        from platform import window

        return window.localStorage
    except Exception:
        return None


def load_highscore():
    """Lee el record guardado. Devuelve 0 si no hay ninguno o si falla la lectura."""
    store = _browser_storage()
    if store is not None:
        try:
            raw = store.getItem(KEY)
            return int(raw) if raw else 0
        except Exception:
            return 0

    try:
        with open(_LOCAL_FILE, "r") as f:
            return int(json.load(f).get("score", 0))
    except Exception:
        return 0


def save_highscore(score):
    """Guarda el record. Un fallo aqui nunca debe tumbar la partida."""
    store = _browser_storage()
    if store is not None:
        try:
            store.setItem(KEY, str(score))
        except Exception:
            pass
        return

    try:
        with open(_LOCAL_FILE, "w") as f:
            json.dump({"score": score}, f)
    except Exception:
        pass
