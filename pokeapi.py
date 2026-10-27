"""PokeAPI client and on-demand synchronization into SQL Server."""
from __future__ import annotations

import re
from urllib.parse import quote

import httpx

from . import database

BASE_URL = "https://pokeapi.co/api/v2"
TIMEOUT = 15.0
_move_refs: list[dict] | None = None
_pokemon_refs: list[dict] | None = None
_pokemon_move_refs: dict[int, list[str]] = {}


def _get(path: str) -> dict:
    try:
        response = httpx.get(f"{BASE_URL}/{path.lstrip('/')}", timeout=TIMEOUT)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise LookupError("No existe ese recurso en PokeAPI.") from exc
        raise RuntimeError(f"PokeAPI respondió HTTP {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("No se pudo conectar con PokeAPI.") from exc
    return response.json()


def _api_id(url: str) -> int:
    match = re.search(r"/(\d+)/?$", url)
    if not match:
        raise RuntimeError(f"URL de PokeAPI no contiene un ID válido: {url}")
    return int(match.group(1))


def search_pokemon(query: str, limit: int = 20) -> list[dict]:
    global _pokemon_refs
    if query.isdigit():
        if not 1 <= int(query) <= 493:
            return []
        return [{"id": int(query), "name": _get(f"pokemon/{query}")["name"]}]
    if _pokemon_refs is None:
        _pokemon_refs = _get("pokemon?limit=1000")["results"]
    query = query.strip().lower().replace(" ", "-")
    return [
        {"id": _api_id(item["url"]), "name": item["name"]}
        for item in _pokemon_refs if query in item["name"].lower()
        and 1 <= _api_id(item["url"]) <= 493
    ][:limit]


def pokemon(query: str) -> dict:
    value = quote(query.strip().lower(), safe="-")
    raw = _get(f"pokemon/{value}")
    species = _get(f"pokemon-species/{raw['id']}")
    if database.GENERATION_IDS.get(species["generation"]["name"], 99) > 4:
        raise LookupError("El motor y el catálogo de tipos están configurados para Gen. I–IV.")
    payload = {
        "id": int(raw["id"]),
        "name": raw["name"],
        "height": raw.get("height"),
        "weight": raw.get("weight"),
        "url": raw["species"]["url"],
        "generation": species["generation"]["name"],
        "types": [
            {"id": _api_id(item["type"]["url"]), "name": item["type"]["name"],
             "url": item["type"]["url"]}
            for item in sorted(raw["types"], key=lambda entry: entry["slot"])
        ],
        "stats": {
            item["stat"]["name"]: {
                "id": _api_id(item["stat"]["url"]),
                "value": int(item["base_stat"]),
            }
            for item in raw["stats"]
        },
        "sprites": {
            "front": raw["sprites"].get("front_default") or "",
            "back": raw["sprites"].get("back_default") or "",
        },
    }
    database.save_pokemon(payload)
    return {
        "id": payload["id"], "name": payload["name"],
        "types": [item["name"] for item in payload["types"]],
        "base": [payload["stats"][name]["value"] for name in database.STAT_NAMES],
        "sprites": payload["sprites"],
    }


def _move_refs_list() -> list[dict]:
    global _move_refs
    if _move_refs is None:
        _move_refs = _get("move?limit=1000")["results"]
    return _move_refs


def move(query: str) -> dict:
    value = quote(query.strip().lower().replace(" ", "-"), safe="-")
    raw = _get(f"move/{value}")
    if raw["generation"]["name"] not in {"generation-i", "generation-ii", "generation-iii", "generation-iv"}:
        raise LookupError("Ese movimiento no existe en la cuarta generación.")

    version_values = next(
        (entry for entry in raw.get("past_values", [])
         if entry.get("version_group", {}).get("name") in {"diamond-pearl", "platinum"}),
        None,
    )
    power, accuracy, pp, move_type = raw.get("power"), raw.get("accuracy"), raw.get("pp"), raw.get("type")
    if version_values:
        for key in ("power", "accuracy", "pp", "type"):
            if version_values.get(key) is not None:
                if key == "type":
                    move_type = version_values[key]
                elif key == "power":
                    power = version_values[key]
                elif key == "accuracy":
                    accuracy = version_values[key]
                else:
                    pp = version_values[key]
    type_data = None
    if move_type:
        type_data = {
            "id": _api_id(move_type["url"]),
            "name": move_type["name"],
            "url": move_type["url"],
        }
    payload = {
        "id": int(raw["id"]), "name": raw["name"],
        "url": raw.get("url") or f"{BASE_URL}/move/{raw['id']}/",
        "type": type_data, "category": raw["damage_class"]["name"],
        "power": power, "accuracy": accuracy, "pp": pp,
    }
    database.save_move(payload)
    return {
        "api_id": payload["id"], "api_name": payload["name"], "name": payload["name"],
        "type": type_data["name"] if type_data else None,
        "category": payload["category"], "power": payload["power"],
        "accuracy": payload["accuracy"], "pp": payload["pp"],
    }


def pokemon_moves(pokemon_id: int, query: str = "") -> list[dict]:
    if not 1 <= pokemon_id <= 493:
        raise LookupError("El Pokémon debe pertenecer a la Pokédex de Gen. IV (1–493).")
    if pokemon_id not in _pokemon_move_refs:
        raw = _get(f"pokemon/{pokemon_id}")
        allowed_groups = {"diamond-pearl", "platinum"}
        names = {
            entry["move"]["name"]
            for entry in raw["moves"]
            if any(
                detail["version_group"]["name"] in allowed_groups
                for detail in entry["version_group_details"]
            )
        }
        _pokemon_move_refs[pokemon_id] = sorted(names)

    normalized = query.strip().lower().replace(" ", "-")
    matches = [
        name for name in _pokemon_move_refs[pokemon_id]
        if not normalized or normalized in name
    ]
    if normalized and normalized in _pokemon_move_refs[pokemon_id]:
        return [move(normalized)]
    return [{"api_name": name, "name": name} for name in matches]


def search_moves(query: str, limit: int = 12) -> list[dict]:
    cached = database.list_moves(query, limit)
    if cached:
        return cached
    normalized = query.strip().lower().replace(" ", "-")
    refs = [
        item for item in _move_refs_list()
        if normalized in item["name"].lower()
    ][:limit]
    result = []
    for ref in refs:
        try:
            result.append(move(ref["name"]))
        except LookupError:
            continue
    return result


def synchronize_gen4_type_chart() -> int:
    type_refs = _get("type?limit=100")["results"]
    type_refs = [item for item in type_refs if item["name"] in database.GEN4_TYPES]
    if len(type_refs) != len(database.GEN4_TYPES):
        raise RuntimeError("PokeAPI no devolvió los 17 tipos de Gen. IV.")

    type_details = {item["name"]: _get(f"type/{item['name']}") for item in type_refs}
    chart = gen4_type_chart(type_details)
    database.save_gen4_type_chart(
        chart,
        [
            {"id": _api_id(item["url"]), "name": item["name"], "url": item["url"]}
            for item in type_refs
        ],
    )
    return len(chart)


def gen4_type_chart(type_details: dict[str, dict]) -> dict[tuple[str, str], float]:
    chart: dict[tuple[str, str], float] = {}
    relations = {}
    historical = {}
    for attack in database.GEN4_TYPES:
        detail = type_details[attack]
        # Gen. V historical relations retain the pre-Fairy chart used by Gen. IV.
        past = next(
            (entry["damage_relations"] for entry in detail.get("past_damage_relations", [])
             if entry.get("generation", {}).get("name") == "generation-v"),
            None,
        )
        relations[attack] = past or detail["damage_relations"]
        historical[attack] = past is not None

    def multiplier(relation: dict, direction: str, target: str) -> float:
        if target in {item["name"] for item in relation[f"no_damage_{direction}"]}:
            return 0.0
        if target in {item["name"] for item in relation[f"double_damage_{direction}"]}:
            return 2.0
        if target in {item["name"] for item in relation[f"half_damage_{direction}"]}:
            return 0.5
        return 1.0

    for attack in database.GEN4_TYPES:
        for defense in database.GEN4_TYPES:
            outgoing = multiplier(relations[attack], "to", defense)
            incoming = multiplier(relations[defense], "from", attack)
            chart[(attack, defense)] = (
                outgoing if historical[attack] or not historical[defense] else incoming
            )
    return chart
