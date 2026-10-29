"""Modelos Pydantic v2 de solicitudes y respuestas."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Sprites(BaseModel):
    front: str | None = None
    back: str | None = None
    animated: bool = False
    verified: bool = True
    fallback: str | None = None


class PokemonSummary(BaseModel):
    id: int
    name: str


class Ability(BaseModel):
    name: str
    slot: int
    hidden: bool = False


class PokemonDetail(BaseModel):
    id: int
    name: str
    height: int | None = None
    weight: int | None = None
    generation: int | None = None
    types: list[str]
    base: list[int] = Field(description="[PS, Ataque, Defensa, At. Esp., Def. Esp., Velocidad]")
    base_stats: dict[str, int]
    abilities: list[Ability]
    sprites: Sprites


class MoveOut(BaseModel):
    id: int
    name: str
    type: str | None = None
    category: Literal["physical", "special", "status"] | None = None
    power: int | None = None
    accuracy: int | None = None
    pp: int | None = None


class PokemonMoves(BaseModel):
    pokemon_id: int
    version: str
    moves: list[MoveOut]
    not_synced: list[str] = Field(description="Movimientos de 4.ª gen que aprende y aún no están en la BD")


class NatureOut(BaseModel):
    name: str
    name_en: str
    plus: int = Field(ge=0, le=5, description="Índice de la estadística que sube (1-5; 0 = neutra)")
    minus: int = Field(ge=0, le=5)


class Combatant(BaseModel):
    pokemon_id: int = Field(ge=1, le=493)
    level: int = Field(ge=1, le=100)
    nature: str = Field(min_length=1, max_length=40)
    iv: list[int] = Field(min_length=6, max_length=6)
    ev: list[int] = Field(min_length=6, max_length=6)
    moves: list[str] = Field(min_length=1, max_length=4)
    stats: list[int] | None = Field(default=None, max_length=6, description="Calculadas por el frontend; el backend las recalcula")

    @field_validator("iv")
    @classmethod
    def _iv(cls, v):
        if any(not 0 <= x <= 31 for x in v):
            raise ValueError("Cada IV debe estar entre 0 y 31.")
        return v

    @field_validator("ev")
    @classmethod
    def _ev(cls, v):
        if any(not 0 <= x <= 252 for x in v):
            raise ValueError("Cada EV debe estar entre 0 y 252.")
        if sum(v) > 510:
            raise ValueError("La suma de EV no puede superar 510.")
        return v

    @field_validator("moves")
    @classmethod
    def _moves(cls, v):
        norm = [m.strip().lower().replace(" ", "-") for m in v]
        if len(set(norm)) != len(norm):
            raise ValueError("Movimientos repetidos.")
        if any(not m or len(m) > 60 for m in norm):
            raise ValueError("Nombre de movimiento no válido.")
        return norm


class BattleRequest(BaseModel):
    ruleset: Literal["gen4"] = "gen4"
    user: Combatant
    rival: Combatant
    seed: int | None = Field(None, ge=0, le=2**32 - 1, description="Semilla del azar: misma semilla = mismo combate")
    strict_learnset: bool = Field(False, description="Si es true, exige que cada movimiento esté en el learnset de 4.ª gen (consulta PokeAPI)")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[str] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "error"]
    pokeapi: Literal["ok", "error", "not_checked"]


class PokedexItem(BaseModel):
    id: int
    name: str
    types: list[str]
    generation: int | None = None
    total: int | None = Field(None, description="Suma de estadísticas base")


class PokedexPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PokedexItem]


class CatalogsOut(BaseModel):
    types: list[str]
    generations: list[dict]
    move_categories: list[str]
    version: str
    counts: dict[str, int]
