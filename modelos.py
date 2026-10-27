"""Estructuras de datos del combate (sin lógica de reglas)."""
from __future__ import annotations

import random
from dataclasses import dataclass, field


def bonito(slug: str) -> str:
    return slug.replace("-", " ").title()


@dataclass
class Movimiento:
    nombre: str  # slug de la BD, p. ej. "thunderbolt"
    tipo: str | None
    categoria: str  # physical | special
    potencia: int
    precision: int | None  # None = no falla
    pp: int
    efectividad: float  # multiplicador ya calculado contra el defensor (EFECTIVIDAD_TIPOS)
    stab: bool
    prioridad: int = 0

    @property
    def bonito(self) -> str:
        return bonito(self.nombre)


@dataclass
class Combatiente:
    lado: str  # "user" | "rival"
    nombre: str
    nivel: int
    tipos: list[str]
    stats: list[int]  # [PS, Ataque, Defensa, At. Esp., Def. Esp., Velocidad]
    movimientos: list[Movimiento]
    ps: int = 0

    @property
    def ps_max(self) -> int:
        return self.stats[0]

    @property
    def vivo(self) -> bool:
        return self.ps > 0

    @property
    def etiqueta(self) -> str:
        base = bonito(self.nombre)
        return base if self.lado == "user" else f"{base} rival"


@dataclass
class Batalla:
    combatientes: dict[str, Combatiente]
    rng: random.Random
    turno: int = 0
