"""Fórmulas puras de 4.ª generación (sin azar ni estado: el azar llega como parámetro)."""


def dano_base(nivel: int, potencia: int, ataque: int, defensa: int) -> int:
    """⌊⌊⌊(⌊2·N/5⌋+2)·Pot·Atq⌋ / Def⌋ / 50⌋ + 2  (cada división entera redondea hacia abajo)."""
    d = (2 * nivel) // 5 + 2
    return d * potencia * ataque // defensa // 50 + 2


def calcular_dano(nivel, potencia, ataque, defensa, *, critico: bool, aleatorio: int, stab: bool, efectividad: float) -> int:
    """Daño final. aleatorio: entero 85..100. Orden: base → crítico ×2 → aleatorio → STAB ×1,5 → tipos."""
    if efectividad == 0:
        return 0
    d = dano_base(nivel, potencia, ataque, defensa)
    if critico:
        d *= 2
    d = d * aleatorio // 100
    if stab:
        d = d * 3 // 2
    return max(1, int(d * efectividad))
