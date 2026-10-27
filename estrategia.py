"""Cómo elige movimiento cada Pokémon en la simulación automática. Cámbiala aquí (p. ej. aleatoria, por tipo...)."""
from .formulas import calcular_dano
from .modelos import Combatiente, Movimiento


def elegir_movimiento(atq: Combatiente, dfn: Combatiente) -> Movimiento | None:
    """Mayor daño esperado (daño medio × precisión) entre los movimientos con PP. None → Forcejeo."""
    mejor, mejor_valor = None, -1.0
    for m in atq.movimientos:
        if m.pp <= 0:
            continue
        i_a, i_d = (1, 2) if m.categoria == "physical" else (3, 4)
        d = calcular_dano(atq.nivel, m.potencia, atq.stats[i_a], dfn.stats[i_d], critico=False, aleatorio=92,
                          stab=m.stab, efectividad=m.efectividad)
        valor = d * (100 if m.precision is None else m.precision) / 100
        if valor > mejor_valor:
            mejor, mejor_valor = m, valor
    return mejor
