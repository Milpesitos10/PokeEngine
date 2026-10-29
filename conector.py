"""Punto de entrada y coordinación: fachada para la API, reglas de validación de combate y CLI.

Uso CLI:  python conector.py serve | diagnose | sync-catalogs | sync-pokemon 445 [--moves]
          python conector.py sync-range 1 151 | sync-move thunderbolt
"""
from __future__ import annotations

import argparse
import json
import logging
from typing import Protocol

import database as db
from config import get_settings
from pokeapi_client import (PokeAPIClient, PokeAPIError, extract_sprites, learnset_gen4, normalize_name,
                            pattern_sprites)

log = logging.getLogger("pokemon.conector")
STAT_KEYS = ["hp", "attack", "defense", "special-attack", "special-defense", "speed"]
GEN = 4


class NotFoundError(Exception): ...
class EngineNotConnected(Exception): ...


class ValidationFailed(Exception):
    def __init__(self, details: list[str]):
        super().__init__("; ".join(details))
        self.details = details


class BattleEngine(Protocol):
    """PUNTO DE INTEGRACIÓN: el motor de 4.ª gen debe implementar simulate() y devolver la lista de eventos
    que consume el frontend ({type:'log'|'move', actor, text, hit, status, hp:{user,rival}, extra, fainted})."""
    def simulate(self, preview: dict) -> list[dict]: ...


_engine: BattleEngine | None = None


def register_engine(engine: BattleEngine) -> None:
    global _engine
    _engine = engine


def calc_stats(base: list[int], iv: list[int], ev: list[int], level: int, plus: int, minus: int) -> list[int]:
    """Estadísticas de 4.ª gen: PS = ⌊(2B+IV+⌊EV/4⌋)·L/100⌋+L+10; resto = ⌊(⌊…·L/100⌋+5)·naturaleza⌋."""
    out = []
    for i in range(6):
        core = (2 * base[i] + iv[i] + ev[i] // 4) * level // 100
        if i == 0:
            out.append(core + level + 10)
        else:
            mult = 11 if plus == i and plus != minus else 9 if minus == i and plus != minus else 10
            out.append((core + 5) * mult // 10)
    return out


def normalize_search(term: str):
    t = term.strip().lower()
    if not t or len(t) > 40:
        raise ValidationFailed(["El término de búsqueda debe tener entre 1 y 40 caracteres."])
    if t.isdigit():
        return int(t)
    try:
        return normalize_name(t)
    except ValueError:
        raise ValidationFailed(["El término de búsqueda contiene caracteres no válidos."]) from None


class Conector:
    def __init__(self, client: PokeAPIClient | None = None, sync=None):
        self.settings = get_settings()
        self._client, self._sync = client, sync

    @property
    def client(self) -> PokeAPIClient:
        self._client = self._client or PokeAPIClient()
        return self._client

    @property
    def sync(self):
        if self._sync is None:
            from sync_service import SyncService
            self._sync = SyncService(self.client)
        return self._sync

    # ---- consultas
    def search_pokemon(self, term: str, limit: int = 20) -> list[dict]:
        return db.search_pokemon(normalize_search(term), limit)

    def get_pokemon(self, api_id: int) -> dict:
        p = db.get_pokemon(api_id)
        if p is None:
            raise NotFoundError("Pokémon no encontrado en la base de datos. Sincronízalo con POST /api/sync/pokemon/{id}.")
        missing = [k for k in STAT_KEYS if k not in p["base_stats"]]
        if missing:
            raise ValidationFailed([f"Datos incompletos para el Pokémon {api_id}: faltan estadísticas {', '.join(missing)}."])
        p["base"] = [p["base_stats"][k] for k in STAT_KEYS]
        try:
            p["sprites"] = extract_sprites(self.client.get_pokemon(api_id))
        except PokeAPIError:
            p["sprites"] = pattern_sprites(api_id)
        return p

    def search_moves(self, term: str | None, limit: int) -> list[dict]:
        t = None
        if term:
            try:
                t = normalize_name(term)
            except ValueError:
                raise ValidationFailed(["El término de búsqueda contiene caracteres no válidos."]) from None
        return db.search_moves(self.settings.combat_version, t, limit)

    def get_pokemon_moves(self, api_id: int) -> dict:
        if db.get_pokemon(api_id) is None:
            raise NotFoundError("Pokémon no encontrado en la base de datos.")
        names = learnset_gen4(self.client.get_pokemon(api_id))  # PokeAPIError -> 502 en main.py
        found = db.get_moves_by_names(self.settings.combat_version, names) if len(names) <= 2000 else []
        have = {m["name"] for m in found}
        return {"pokemon_id": api_id, "version": self.settings.combat_version, "moves": found,
                "not_synced": [n for n in names if n not in have]}

    def pokedex(self, search, type_name, generation, sort, order, page, page_size) -> dict:
        term = normalize_search(search) if search else None
        tn = None
        if type_name:
            try:
                tn = normalize_name(type_name)
            except ValueError:
                raise ValidationFailed(["El tipo no es válido."]) from None
        total, items = db.pokedex(term, tn, generation, sort, order, page_size, (page - 1) * page_size)
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    def catalogs(self) -> dict:
        return db.catalogs(self.settings.combat_version)

    def get_natures(self) -> list[dict]:
        return self.client.get_all_natures()

    # ---- combate
    def preview_battle(self, req) -> dict:
        v = self.settings.combat_version
        details, built = [], {}
        nmap = {}
        for n in self.get_natures():
            nmap[n["name"].lower()] = n
            nmap[n["name_en"].lower()] = n
        for side in ("user", "rival"):
            c = getattr(req, side)
            label = "Tu Pokémon" if side == "user" else "Pokémon rival"
            try:
                p = self.get_pokemon(c.pokemon_id)
            except NotFoundError:
                details.append(f"{label}: el Pokémon {c.pokemon_id} no está sincronizado.")
                continue
            except ValidationFailed as exc:
                details += [f"{label}: {d}" for d in exc.details]
                continue
            nat = nmap.get(c.nature.strip().lower())
            if nat is None:
                details.append(f"{label}: naturaleza '{c.nature}' no reconocida.")
                continue
            found = {m["name"]: m for m in db.get_moves_by_names(v, c.moves)}
            absent = [m for m in c.moves if m not in found]
            if absent:
                details.append(f"{label}: movimientos no disponibles en {v}: {', '.join(absent)}.")
                continue
            if req.strict_learnset:
                try:
                    learn = set(learnset_gen4(self.client.get_pokemon(c.pokemon_id)))
                except PokeAPIError:
                    details.append(f"{label}: no se pudo comprobar el learnset (PokeAPI no disponible).")
                    continue
                illegal = [m for m in c.moves if m not in learn]
                if illegal:
                    details.append(f"{label}: {p['name']} no aprende en 4.ª gen: {', '.join(illegal)}.")
                    continue
            stats = calc_stats(p["base"], c.iv, c.ev, c.level, nat["plus"], nat["minus"])
            built[side] = {"pokemon": p, "c": c, "nature": nat, "stats": stats, "moves": [found[m] for m in c.moves]}
        if details:
            raise ValidationFailed(details)

        warnings, out = [], {}
        for side, other in (("user", "rival"), ("rival", "user")):
            b, o = built[side], built[other]
            mults = db.get_multipliers(GEN, sorted({m["type"] for m in b["moves"] if m["type"]}), o["pokemon"]["types"])
            moves = []
            for m in b["moves"]:
                eff = None
                if m["category"] != "status" and m["type"]:
                    eff = 1.0
                    for dt in o["pokemon"]["types"]:
                        if (m["type"], dt) not in mults:
                            eff = None
                            break
                        eff *= mults[(m["type"], dt)]
                moves.append({**m, "stab": m["type"] in b["pokemon"]["types"], "effectiveness": eff})
            if any(mv["effectiveness"] is None and mv["category"] != "status" for mv in moves):
                warnings.append("EFECTIVIDAD_TIPOS no tiene todos los datos necesarios; ejecuta POST /api/sync/catalogs.")
            c = b["c"]
            if c.stats and c.stats != b["stats"]:
                warnings.append(f"Las estadísticas enviadas por el frontend para '{side}' difieren de las calculadas por el backend; se usan las del backend.")
            out[side] = {"pokemon": {k: b["pokemon"][k] for k in ("id", "name", "types", "base", "sprites")},
                         "level": c.level, "nature": {k: b["nature"][k] for k in ("name", "plus", "minus")},
                         "iv": c.iv, "ev": c.ev, "stats": b["stats"], "max_hp": b["stats"][0], "moves": moves}
        result = {"valid": True, "ruleset": "gen4", "version": v, "combatants": out, "warnings": sorted(set(warnings)),
                  "engine": {"connected": _engine is not None, "integration_point": "conector.register_engine()"}}
        if _engine is not None and hasattr(_engine, "analizar"):
            errores, avisos = _engine.analizar(result)
            if errores:
                raise ValidationFailed(errores)
            result["warnings"] = sorted(set(result["warnings"] + avisos))
        return result

    def simulate_battle(self, req) -> dict:
        preview = self.preview_battle(req)
        if _engine is None:
            raise EngineNotConnected("El motor de combate de 4.ª generación aún no está conectado.")
        preview["seed"] = req.seed
        return {"events": _engine.simulate(preview)}


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="Conector Calculadora de Daño Pokémon")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve").add_argument("--port", type=int, default=8001)
    sub.add_parser("diagnose")
    sub.add_parser("sync-catalogs")
    p = sub.add_parser("sync-pokemon"); p.add_argument("id"); p.add_argument("--moves", action="store_true")
    m = sub.add_parser("sync-move"); m.add_argument("id")
    r = sub.add_parser("sync-range"); r.add_argument("start", type=int); r.add_argument("end", type=int); r.add_argument("--delay", type=float, default=0.3)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if a.cmd == "serve":
        import uvicorn
        uvicorn.run("main:app", host="127.0.0.1", port=a.port)
    elif a.cmd == "diagnose":
        d = db.schema_diagnostics()
        for t, cols in d["tables"].items():
            print(f"\n{t}\n  " + "\n  ".join(cols))
        print("\nTablas esperadas ausentes:", d["missing"] or "ninguna")
    else:
        svc = Conector().sync
        res = (svc.sync_catalogs() if a.cmd == "sync-catalogs" else svc.sync_pokemon(a.id, a.moves) if a.cmd == "sync-pokemon"
               else svc.sync_move(a.id) if a.cmd == "sync-move" else svc.sync_range(a.start, a.end, a.delay))
        print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
