"""Tablas de reglas de 4.ª generación que NO están en la base de datos. REVÍSALAS antes de fiarte de ellas."""

MAX_TURNOS = 200

# Prioridad de movimientos ofensivos (4.ª gen). La BD actual no tiene columna de prioridad.
PRIORIDAD = {"quick-attack": 1, "mach-punch": 1, "extreme-speed": 1, "aqua-jet": 1,
             "bullet-punch": 1, "ice-shard": 1, "vacuum-wave": 1, "shadow-sneak": 1}

# Retroceso (numerador, denominador) sobre el daño causado
RETROCESO = {"double-edge": (1, 3), "brave-bird": (1, 3), "flare-blitz": (1, 3), "wood-hammer": (1, 3),
             "volt-tackle": (1, 3), "take-down": (1, 4), "submission": (1, 4), "head-smash": (1, 2)}

# Movimientos con potencia pero mecánica propia aún NO implementada: el motor no los usa (y lo avisa).
NO_SOPORTADOS = {
    # dos turnos / recarga
    "razor-wind", "solar-beam", "skull-bash", "sky-attack", "fly", "dig", "dive", "bounce", "shadow-force",
    "hyper-beam", "giga-impact", "blast-burn", "hydro-cannon", "frenzy-plant", "roar-of-time", "rock-wrecker",
    # varios golpes
    "double-slap", "comet-punch", "fury-attack", "pin-missile", "spike-cannon", "barrage", "fury-swipes",
    "bone-rush", "bullet-seed", "icicle-spear", "rock-blast", "arm-thrust", "double-kick", "bonemerang",
    "double-hit", "twineedle", "triple-kick",
    # daño fijo / variable / dependiente de estado
    "seismic-toss", "night-shade", "dragon-rage", "sonic-boom", "super-fang", "psywave", "endeavor",
    "guillotine", "horn-drill", "fissure", "sheer-cold", "low-kick", "grass-knot", "gyro-ball", "electro-ball",
    "flail", "reversal", "return", "frustration", "hidden-power", "magnitude", "present", "spit-up",
    "trump-card", "wring-out", "crush-grip", "punishment", "natural-gift", "fling", "judgment", "weather-ball",
    "brine", "eruption", "water-spout", "assurance", "payback", "revenge", "avalanche", "counter",
    "mirror-coat", "metal-burst", "bide", "focus-punch", "explosion", "self-destruct", "last-resort",
    "fake-out", "sucker-punch", "feint", "me-first", "mimic",
}
