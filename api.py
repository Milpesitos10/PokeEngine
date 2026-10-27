"""HTTP API used by the static frontend."""
from __future__ import annotations

import logging
from contextlib import closing
from pathlib import Path

import pyodbc
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import database, pokeapi
from .motor import MotorGen4

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent
SPRITES = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/"
    "versions/generation-v/black-white/animated/"
)

NATURES = [
    ("Fuerte", 0, 0), ("Huraña", 1, 2), ("Audaz", 1, 5), ("Firme", 1, 3),
    ("Pícara", 1, 4), ("Osada", 2, 1), ("Dócil", 0, 0), ("Plácida", 2, 5),
    ("Agitada", 2, 3), ("Floja", 2, 4), ("Miedosa", 5, 1), ("Activa", 5, 2),
    ("Seria", 0, 0), ("Alegre", 5, 3), ("Ingenua", 5, 4), ("Modesta", 3, 1),
    ("Afable", 3, 2), ("Mansa", 3, 5), ("Tímida", 0, 0), ("Alocada", 3, 4),
    ("Serena", 4, 1), ("Amable", 4, 2), ("Grosera", 4, 5), ("Cauta", 4, 3),
    ("Rara", 0, 0),
]
NATURE_BY_NAME = {name.casefold(): (plus, minus) for name, plus, minus in NATURES}

app = FastAPI(title="PokeEngine API", version="1.0.0")


class CombatantInput(BaseModel):
    pokemon_id: int = Field(gt=0)
    level: int = Field(ge=1, le=100)
    nature: str
    iv: list[int] = Field(min_length=6, max_length=6)
    ev: list[int] = Field(min_length=6, max_length=6)
    stats: list[int] | None = None
    moves: list[str] = Field(min_length=1, max_length=4)


class BattleInput(BaseModel):
    ruleset: str = "gen4"
    user: CombatantInput
    rival: CombatantInput
    seed: int | None = None


@app.get("/")
def home():
    return FileResponse(ROOT / "index.html")


@app.get("/styles.css")
def styles():
    return FileResponse(ROOT / "styles.css", media_type="text/css")


@app.get("/script.js")
def script():
    return FileResponse(ROOT / "script.js", media_type="application/javascript")


@app.get("/api/health")
def health():
    try:
        with closing(database.connect()) as connection:
            connection.cursor().execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except pyodbc.Error as exc:
        logger.exception("SQL Server health check failed")
        raise HTTPException(status_code=503, detail="No se pudo conectar con SQL Server.") from exc


@app.get("/api/pokemon")
def search_pokemon(q: str = Query(min_length=1, max_length=40)):
    try:
        results = database.search_pokemon(q.strip())
        if results:
            return results
        return pokeapi.search_pokemon(q)
    except LookupError:
        return []
    except RuntimeError as exc:
        logger.exception("Pokemon lookup failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except pyodbc.Error as exc:
        logger.exception("SQL Server pokemon search failed")
        raise HTTPException(status_code=503, detail="No se pudo consultar el catálogo SQL Server.") from exc


@app.get("/api/pokemon/{pokemon_id}")
def pokemon_details(pokemon_id: int):
    try:
        result = database.get_pokemon(pokemon_id)
        if result is None:
            return pokeapi.pokemon(str(pokemon_id))
        return {
            **result,
            "sprites": {
                "front": f"{SPRITES}{pokemon_id}.gif",
                "back": f"{SPRITES}back/{pokemon_id}.gif",
            },
        }
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Pokemon details lookup failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except pyodbc.Error as exc:
        logger.exception("SQL Server pokemon details lookup failed")
        raise HTTPException(status_code=503, detail="No se pudo consultar el catálogo SQL Server.") from exc


@app.get("/api/pokemon/{pokemon_id}/moves")
def pokemon_moves(pokemon_id: int, q: str = Query(default="", max_length=60)):
    try:
        return pokeapi.pokemon_moves(pokemon_id, q)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Pokemon move list lookup failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except pyodbc.Error as exc:
        logger.exception("SQL Server move synchronization failed")
        raise HTTPException(status_code=503, detail="No se pudo guardar el movimiento en SQL Server.") from exc


@app.get("/api/moves")
def list_moves(q: str = Query(default="", max_length=50)):
    try:
        if q.strip():
            return pokeapi.search_moves(q.strip())
        return database.list_moves(limit=500)
    except LookupError:
        return []
    except RuntimeError as exc:
        logger.exception("Move lookup failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except pyodbc.Error as exc:
        logger.exception("SQL Server move lookup failed")
        raise HTTPException(status_code=503, detail="No se pudo consultar el catálogo SQL Server.") from exc


@app.get("/api/natures")
def list_natures():
    return [{"name": name, "plus": plus, "minus": minus} for name, plus, minus in NATURES]


def _stat_total(base: int, iv: int, ev: int, level: int, index: int,
                plus: int, minus: int) -> int:
    core = ((2 * base + iv + ev // 4) * level) // 100
    if index == 0:
        return core + level + 10
    modifier = 1.1 if plus == index else 0.9 if minus == index else 1.0
    return int((core + 5) * modifier)


def _prepare_combatant(
    config: CombatantInput, opponent_types: list[str], pokemon: dict | None = None
) -> dict:
    nature = NATURE_BY_NAME.get(config.nature.casefold())
    if nature is None:
        raise ValueError(f"Naturaleza desconocida: {config.nature}.")
    if any(value < 0 or value > 31 for value in config.iv):
        raise ValueError("Cada IV debe estar entre 0 y 31.")
    if any(value < 0 or value > 252 for value in config.ev):
        raise ValueError("Cada EV debe estar entre 0 y 252.")
    if sum(config.ev) > 510:
        raise ValueError("La suma de EV no puede superar 510.")

    if pokemon is None:
        pokemon = database.get_pokemon(config.pokemon_id)
        if pokemon is None:
            pokemon = pokeapi.pokemon(str(config.pokemon_id))
    if any(type_name not in database.GEN4_TYPES for type_name in pokemon["types"]):
        raise ValueError(
            "El motor de combate solo admite Pokémon con tipos de Gen. I–IV."
        )
    plus, minus = nature
    stats = [
        _stat_total(base, config.iv[index], config.ev[index], config.level, index, plus, minus)
        for index, base in enumerate(pokemon["base"])
    ]
    moves = []
    for api_name in config.moves:
        move_data = database.move_for_battle(api_name)
        if move_data is None:
            pokeapi.move(api_name)
            move_data = database.move_for_battle(api_name)
        if move_data is None:
            raise ValueError(f"No se encontró el movimiento '{api_name}' en el catálogo Gen. IV.")
        effect = (
            database.move_effectiveness(move_data["type"], opponent_types)
            if move_data["type"] else None
        )
        moves.append({
            "name": move_data["name"], "type": move_data["type"],
            "category": move_data["category"], "power": move_data["power"],
            "accuracy": move_data["accuracy"], "pp": move_data["pp"],
            "effectiveness": effect, "stab": move_data["type"] in pokemon["types"],
        })
    return {
        "pokemon": {"id": pokemon["id"], "name": pokemon["name"],
                    "types": pokemon["types"], "base": pokemon["base"]},
        "level": config.level, "stats": stats, "moves": moves,
    }


@app.post("/api/battle/simulate")
def simulate_battle(request: BattleInput):
    if request.ruleset.casefold() != "gen4":
        raise HTTPException(status_code=422, detail="Solo está disponible el ruleset gen4.")
    try:
        if not database.type_chart_ready():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Falta la tabla de efectividad completa de Gen. IV "
                    "(289 combinaciones) en dbo.EFECTIVIDAD_TIPOS. "
                    "Ejecuta .\\.venv\\Scripts\\python.exe sync_catalogs.py."
                ),
            )
        user_data = database.get_pokemon(request.user.pokemon_id)
        if user_data is None:
            user_data = pokeapi.pokemon(str(request.user.pokemon_id))
        rival_data = database.get_pokemon(request.rival.pokemon_id)
        if rival_data is None:
            rival_data = pokeapi.pokemon(str(request.rival.pokemon_id))
        user = _prepare_combatant(request.user, rival_data["types"], user_data)
        rival = _prepare_combatant(request.rival, user_data["types"], rival_data)
        preview = {"combatants": {"user": user, "rival": rival}, "seed": request.seed}
        return {"events": MotorGen4().simulate(preview)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Battle setup failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except pyodbc.Error as exc:
        logger.exception("SQL Server battle lookup failed")
        raise HTTPException(status_code=503, detail="No se pudo consultar SQL Server para el combate.") from exc
