"""PUNTO DE EXTENSIÓN: comportamiento de cada movimiento. Por defecto todo es un ataque directo.

Para añadir un movimiento con lógica propia:
    @especial("nombre-del-movimiento")
    def mi_efecto(b, atq, dfn, mov):
        ev = ataque_directo(b, atq, dfn, mov)   # o escribe tu propia lógica
        ...modifica ev["extra"], PS, etc...
        return ev
Habilidades, objetos y estados: añade funciones a HOOKS (se invocan desde motor.py).
"""
from __future__ import annotations

from .datos import RETROCESO
from .formulas import calcular_dano
from .modelos import Batalla, Combatiente, Movimiento

ESPECIALES: dict = {}
HOOKS: dict[str, list] = {"fin_de_turno": []}  # cada hook: fn(batalla) -> list[dict] de eventos


def especial(*nombres):
    def deco(fn):
        for n in nombres:
            ESPECIALES[n] = fn
        return fn
    return deco


def resolver(b: Batalla, atq: Combatiente, dfn: Combatiente, mov: Movimiento) -> dict:
    return ESPECIALES.get(mov.nombre, ataque_directo)(b, atq, dfn, mov)


def ataque_directo(b: Batalla, atq: Combatiente, dfn: Combatiente, mov: Movimiento) -> dict:
    """Orden de tiradas (reproducible con semilla): precisión → crítico → factor aleatorio."""
    ev = {"type": "move", "actor": atq.lado, "text": f"¡{atq.etiqueta} usó {mov.bonito}!", "hit": False,
          "status": False, "damage": 0, "extra": []}
    if mov.precision is not None and b.rng.randint(1, 100) > mov.precision:
        ev["extra"].append(f"¡El ataque de {atq.etiqueta} falló!")
        return ev
    if mov.efectividad == 0:
        ev["extra"].append(f"No afecta a {dfn.etiqueta}...")
        return ev
    critico = b.rng.randint(1, 16) == 1  # 1/16 en 4.ª gen (sin modificadores aún)
    aleatorio = b.rng.randint(85, 100)
    i_a, i_d = (1, 2) if mov.categoria == "physical" else (3, 4)
    dano = calcular_dano(atq.nivel, mov.potencia, atq.stats[i_a], dfn.stats[i_d], critico=critico,
                         aleatorio=aleatorio, stab=mov.stab, efectividad=mov.efectividad)
    dano = min(dano, dfn.ps)
    dfn.ps -= dano
    ev.update(hit=True, damage=dano)
    if critico:
        ev["extra"].append("¡Un golpe crítico!")
    if mov.efectividad > 1:
        ev["extra"].append("¡Es súper efectivo!")
    elif mov.efectividad < 1:
        ev["extra"].append("No es muy efectivo...")
    ev["extra"].append(f"¡El ataque ha causado {dano} puntos de daño!")
    return ev


@especial(*RETROCESO)
def con_retroceso(b, atq, dfn, mov):
    ev = ataque_directo(b, atq, dfn, mov)
    if ev["hit"]:
        num, den = RETROCESO[mov.nombre]
        atq.ps = max(0, atq.ps - max(1, ev["damage"] * num // den))
        ev["extra"].append(f"¡{atq.etiqueta} se ha herido por el retroceso!")
    return ev


@especial("struggle")
def forcejeo(b, atq, dfn, mov):
    ev = ataque_directo(b, atq, dfn, mov)
    atq.ps = max(0, atq.ps - max(1, atq.ps_max // 4))
    ev["extra"].append(f"¡{atq.etiqueta} se ha herido por el retroceso!")
    return ev


def movimiento_forcejeo() -> Movimiento:
    return Movimiento("struggle", None, "physical", 50, None, 1, 1.0, False)
