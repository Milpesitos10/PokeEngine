"""Aplicación FastAPI. Ejecutar: uvicorn main:app --port 8001"""
from __future__ import annotations

import hmac
import logging

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import database as db
from config import get_settings
from conector import Conector, EngineNotConnected, NotFoundError, ValidationFailed, register_engine
from motor import MotorGen4
from pokeapi_client import PokeAPIError, PokeAPIInvalidResponse, PokeAPINotFound, PokeAPIUnavailable
from typing import Literal

from schemas import (BattleRequest, CatalogsOut, PokedexPage, ErrorResponse, HealthOut, MoveOut, NatureOut, PokemonDetail, PokemonMoves,
                     PokemonSummary)
from sync_service import OutOfScope, SyncError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pokemon.api")
settings = get_settings()
facade = Conector()
register_engine(MotorGen4())  # para desactivar el motor, comenta esta línea (simulate devolverá 501)
ERR = {404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}

app = FastAPI(title="Calculadora de Daño Pokémon - API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type", "X-API-Key"])


def _err(status: int, code: str, message: str, details: list[str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details}})


@app.exception_handler(RequestValidationError)
async def _validation(_: Request, exc: RequestValidationError):
    details = [f"{'.'.join(str(p) for p in e['loc'] if p != 'body')}: {e['msg']}" for e in exc.errors()]
    return _err(422, "validation_error", "Parámetros no válidos.", details)


@app.exception_handler(ValidationFailed)
async def _vf(_: Request, exc: ValidationFailed):
    return _err(422, "validation_error", "La configuración no es válida.", exc.details)


for _cls, _status, _code, _msg in [
    (NotFoundError, 404, "not_found", None), (PokeAPINotFound, 404, "not_found", "Recurso no encontrado en PokeAPI."),
    (OutOfScope, 422, "out_of_scope", None), (PokeAPIUnavailable, 502, "upstream_unavailable", "PokeAPI no está disponible."),
    (PokeAPIInvalidResponse, 502, "upstream_invalid", "PokeAPI devolvió datos incompletos."),
    (db.DatabaseUnavailable, 503, "database_unavailable", "Base de datos no disponible."),
    (db.IntegrityViolation, 409, "conflict", "La operación viola una restricción de datos."),
    (db.DatabaseError, 500, "database_error", "Error interno de base de datos."),
    (EngineNotConnected, 501, "engine_not_connected", None), (SyncError, 422, "sync_error", None),
]:
    def _make(status=_status, code=_code, msg=_msg):
        async def handler(_: Request, exc: Exception):
            return _err(status, code, msg or str(exc))
        return handler
    app.add_exception_handler(_cls, _make())


@app.exception_handler(Exception)
async def _unexpected(_: Request, exc: Exception):
    log.exception("Error no controlado")  # el detalle queda solo en el log del servidor
    return _err(500, "internal_error", "Error interno del servidor.")


def require_sync_key(x_api_key: str | None = Header(default=None)):
    if not settings.sync_api_key:
        raise HTTPException(403, detail="La sincronización está deshabilitada (SYNC_API_KEY no configurada).")
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.sync_api_key):
        raise HTTPException(401, detail="Clave de API no válida.")


@app.exception_handler(HTTPException)
async def _http(_: Request, exc: HTTPException):
    return _err(exc.status_code, "http_error", str(exc.detail))


# ---------------------------------------------------------------- endpoints
@app.get("/api/health", response_model=HealthOut, responses={503: {"model": HealthOut}})
def health(deep: bool = False):
    try:
        database = "ok" if db.ping() else "error"
    except Exception:
        database = "error"
    pokeapi = "not_checked"
    if deep:
        try:
            facade.client.get_species("pikachu")
            pokeapi = "ok"
        except PokeAPIError:
            pokeapi = "error"
    healthy = database == "ok" and pokeapi != "error"
    body = {"status": "ok" if healthy else "degraded", "database": database, "pokeapi": pokeapi}
    return JSONResponse(status_code=200 if healthy else 503, content=body)


@app.get("/api/pokedex", response_model=PokedexPage, responses=ERR)
def pokedex(search: str | None = Query(None, max_length=40), type: str | None = Query(None, max_length=20),
            generation: int | None = Query(None, ge=1, le=4), sort: Literal["number", "name", "total"] = "number",
            order: Literal["asc", "desc"] = "asc", page: int = Query(1, ge=1, le=10000), page_size: int = Query(24, ge=1, le=60)):
    """Índice paginado de los Pokémon que hay en la base de datos, con filtros por tipo y generación."""
    return facade.pokedex(search, type, generation, sort, order, page, page_size)


@app.get("/api/catalogs", response_model=CatalogsOut, responses=ERR)
def catalogs():
    """Tipos, generaciones y categorías de movimiento disponibles en la BD (para los filtros) y recuentos."""
    return facade.catalogs()


@app.get("/api/pokemon", response_model=list[PokemonSummary], responses=ERR)
def search_pokemon(search: str | None = Query(None, max_length=40), q: str | None = Query(None, max_length=40, description="Alias de search"),
                   limit: int = Query(20, ge=1, le=50)):
    term = search or q
    if not term:
        raise ValidationFailed(["Indica 'search' con un nombre o número de Pokédex."])
    return facade.search_pokemon(term, limit)


@app.get("/api/pokemon/{pokemon_id}", response_model=PokemonDetail, responses=ERR)
def get_pokemon(pokemon_id: int = Path(ge=1, le=settings.max_dex)):
    return facade.get_pokemon(pokemon_id)


@app.get("/api/pokemon/{pokemon_id}/moves", response_model=PokemonMoves, responses=ERR)
def pokemon_moves(pokemon_id: int = Path(ge=1, le=settings.max_dex)):
    return facade.get_pokemon_moves(pokemon_id)


@app.get("/api/moves", response_model=list[MoveOut], responses=ERR)
def search_moves(search: str | None = Query(None, max_length=60), limit: int = Query(500, ge=1, le=1000)):
    return facade.search_moves(search, limit)


@app.get("/api/natures", response_model=list[NatureOut], responses=ERR)
def natures():
    return facade.get_natures()


@app.post("/api/battles/preview", responses={**ERR, 501: {"model": ErrorResponse}})
def battle_preview(req: BattleRequest):
    return facade.preview_battle(req)


@app.post("/api/battles/simulate", responses={**ERR, 501: {"model": ErrorResponse}})
def battle_simulate(req: BattleRequest):
    return facade.simulate_battle(req)


@app.post("/api/sync/pokemon/{pokemon_id}", dependencies=[Depends(require_sync_key)], responses=ERR)
def sync_pokemon(pokemon_id: int = Path(ge=1, le=settings.max_dex), include_moves: bool = False):
    return facade.sync.sync_pokemon(pokemon_id, include_moves)


@app.post("/api/sync/catalogs", dependencies=[Depends(require_sync_key)], responses=ERR)
def sync_catalogs():
    return facade.sync.sync_catalogs()


if settings.frontend_dir:  # sirve el frontend desde el mismo origen (sin CORS); debe ir al final
    app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
