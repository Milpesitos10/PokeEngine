"""Motor de combate 4.ª gen — v1: ataques directos 1 contra 1. Sin habilidades, objetos ni estados alterados."""
from __future__ import annotations

import random

from . import efectos
from .datos import MAX_TURNOS, NO_SOPORTADOS, PRIORIDAD
from .estrategia import elegir_movimiento
from .modelos import Batalla, Combatiente, Movimiento

OTRO = {"user": "rival", "rival": "user"}


def motivo_no_ejecutable(m: dict) -> str | None:
    if m["category"] == "status":
        return "movimiento de estado"
    if not m["power"]:
        return "sin potencia fija"
    if m["name"] in NO_SOPORTADOS:
        return "mecánica aún no implementada"
    return None


class MotorGen4:
    nombre = "gen4-ataques-directos"

    def analizar(self, preview: dict) -> tuple[list[str], list[str]]:
        """(errores bloqueantes, avisos). Lo usa /api/battles/preview."""
        errores, avisos = [], []
        for lado, c in preview["combatants"].items():
            quien = "Tu Pokémon" if lado == "user" else "Pokémon rival"
            usables, omitidos = 0, []
            for m in c["moves"]:
                motivo = motivo_no_ejecutable(m)
                if motivo:
                    omitidos.append(f"{m['name']} ({motivo})")
                elif m["effectiveness"] is None:
                    errores.append(f"{quien}: falta la efectividad de tipos para {m['name']} (ejecuta POST /api/sync/catalogs).")
                elif not m.get("pp"):
                    errores.append(f"{quien}: {m['name']} no tiene PP en la base de datos.")
                else:
                    usables += 1
            if omitidos:
                avisos.append(f"{quien}: el motor no usará {', '.join(omitidos)}.")
            if usables == 0 and not any(e.startswith(quien) for e in errores):
                errores.append(f"{quien}: no tiene ningún movimiento ofensivo soportado por el motor.")
        return errores, avisos

    @staticmethod
    def _combatiente(lado: str, c: dict) -> Combatiente:
        movs = [Movimiento(m["name"], m["type"], m["category"], m["power"], m["accuracy"], m["pp"], m["effectiveness"],
                           m["stab"], PRIORIDAD.get(m["name"], 0))
                for m in c["moves"] if motivo_no_ejecutable(m) is None]
        return Combatiente(lado, c["pokemon"]["name"], c["level"], c["pokemon"]["types"], c["stats"], movs, ps=c["stats"][0])

    @staticmethod
    def _orden(cs, acciones, rng) -> list[str]:
        claves = [(acciones[l].prioridad, c.stats[5], rng.random(), l) for l, c in cs.items()]  # empate de velocidad: azar
        return [k[3] for k in sorted(claves, reverse=True)]

    def simulate(self, preview: dict) -> list[dict]:
        errores, avisos = self.analizar(preview)
        if errores:
            raise ValueError("; ".join(errores))
        cs = {l: self._combatiente(l, c) for l, c in preview["combatants"].items()}
        b = Batalla(cs, random.Random(preview.get("seed")))
        log = lambda t, **k: {"type": "log", "text": t, **k}
        ev = [log(f"¡{cs['user'].etiqueta} ha entrado en combate!", max_hp={l: c.ps_max for l, c in cs.items()}),
              log(f"¡{cs['rival'].etiqueta} está preparado!"),
              log("Motor v1: solo ataques directos (sin habilidades, objetos, estados ni efectos secundarios).")]
        ev += [log(a) for a in avisos]
        for turno in range(1, MAX_TURNOS + 1):
            b.turno = turno
            ev.append(log(f"— Turno {turno} —"))
            acciones = {l: elegir_movimiento(c, cs[OTRO[l]]) or efectos.movimiento_forcejeo() for l, c in cs.items()}
            for lado in self._orden(cs, acciones, b.rng):
                atq, dfn, mov = cs[lado], cs[OTRO[lado]], acciones[lado]
                if not (atq.vivo and dfn.vivo):
                    continue
                if mov.nombre == "struggle":
                    ev.append(log(f"¡{atq.etiqueta} no tiene movimientos disponibles!", actor=lado))
                else:
                    mov.pp -= 1
                res = efectos.resolver(b, atq, dfn, mov)
                res["hp"] = {l: c.ps for l, c in cs.items()}
                ev.append(res)
                for l in (dfn.lado, atq.lado):
                    if not cs[l].vivo:
                        ev.append({"type": "faint", "actor": l, "fainted": l, "text": f"¡{cs[l].etiqueta} se ha debilitado!"})
            for hook in efectos.HOOKS["fin_de_turno"]:
                ev += hook(b)
            if not all(c.vivo for c in cs.values()):
                break
        caidos = [l for l, c in cs.items() if not c.vivo]
        ganador = OTRO[caidos[0]] if len(caidos) == 1 else "draw"
        fin = ("¡El combate ha terminado! " + (f"¡Ha ganado {cs[ganador].etiqueta}!" if ganador != "draw"
               else "Empate (ambos debilitados o límite de turnos)."))
        ev.append({"type": "end", "text": fin, "winner": ganador, "turns": b.turno})
        return ev
