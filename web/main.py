"""Punto de entrada del build web.

Este fichero no vive en el repo del juego: se copia al directorio de staging
que prepara build.py, junto a una copia ya transformada del codigo original.
Todo lo que se pueda resolver desde fuera se resuelve aqui, para que build.py
tenga que tocar el codigo del juego lo menos posible.
"""

import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

# En pygbag los submodulos de pygame se cargan de forma perezosa, asi que
# `import pygame` a secas deja `pygame.sprite` sin definir. Los modulos del
# juego lo usan en tiempo de importacion (ui.py lo hace en la propia linea de
# `class Button(pygame.sprite.Sprite)`), asi que hay que forzarlos antes.
import pygame  # noqa: E402
import pygame.display  # noqa: E402
import pygame.draw  # noqa: E402
import pygame.event  # noqa: E402
import pygame.font  # noqa: E402
import pygame.image  # noqa: E402
import pygame.key  # noqa: E402
import pygame.mouse  # noqa: E402
import pygame.sprite  # noqa: E402
import pygame.time  # noqa: E402
import pygame.transform  # noqa: E402

import game_main  # copia transformada de src/main.py  # noqa: E402
import storage  # noqa: E402

IS_WEB = sys.platform == "emscripten"


# --- Record persistente -----------------------------------------------------
# El save_score() original lee y escribe score.json, que en WebAssembly se
# pierde al recargar. Lo sustituimos por localStorage manteniendo la misma
# firma: devuelve el record vigente despues de considerar la partida actual.


def _save_score(self):
    highest = storage.load_highscore()
    if self.score > highest:
        storage.save_highscore(self.score)
        highest = self.score
    return highest


game_main.Game.save_score = _save_score


# --- Estrellas quietas en pausa ---------------------------------------------
# draw_bg_and_ui() se llama fuera del `if not self.paused`, asi que el fondo
# sigue desplazandose con el juego congelado. En vez de reimplementar el
# dibujado (que se quedaria desincronizado del original), basta con anular el
# vector de movimiento mientras esta en pausa.

_direccion_original = game_main.Game._get_star_direction_by_level


def _direccion_estrellas(self):
    if self.paused:
        return 0, 0
    return _direccion_original(self)


game_main.Game._get_star_direction_by_level = _direccion_estrellas


# --- Botones de salir -------------------------------------------------------
# En una pestana del navegador no existe "cerrar el programa": un sys.exit()
# deja al jugador ante un lienzo muerto que solo se arregla recargando. En vez
# de eso convertimos la salida en una vuelta a la pantalla de inicio.


class _BackToMenu(Exception):
    pass


if IS_WEB:

    def _exit(*_args):
        raise _BackToMenu()

    game_main.sys.exit = _exit


async def main():
    while True:
        try:
            juego = game_main.Game()
            await juego.run()
        except _BackToMenu:
            continue  # Quit en web -> volver al inicio en vez de morir
        return


asyncio.run(main())
