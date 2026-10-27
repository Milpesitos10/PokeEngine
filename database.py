"""SQL Server persistence for the normalized PokeAPI catalog."""
from __future__ import annotations

import os
from contextlib import closing

import pyodbc

STAT_NAMES = ("hp", "attack", "defense", "special-attack", "special-defense", "speed")
STAT_API_IDS = {1: "hp", 2: "attack", 3: "defense", 4: "special-attack", 5: "special-defense", 6: "speed"}
TYPE_API_IDS = {
    1: "normal", 2: "fighting", 3: "flying", 4: "poison", 5: "ground",
    6: "rock", 7: "bug", 8: "ghost", 9: "steel", 10: "fire",
    11: "water", 12: "grass", 13: "electric", 14: "psychic",
    15: "ice", 16: "dragon", 17: "dark",
}
TYPE_IDS = {name: api_id for api_id, name in TYPE_API_IDS.items()}
GENERATION_IDS = {
    "generation-i": 1, "generation-ii": 2, "generation-iii": 3,
    "generation-iv": 4, "generation-v": 5, "generation-vi": 6,
    "generation-vii": 7, "generation-viii": 8, "generation-ix": 9,
}
GEN4_TYPES = (
    "normal", "fire", "water", "electric", "grass", "ice", "fighting",
    "poison", "ground", "flying", "psychic", "bug", "rock", "ghost",
    "dragon", "dark", "steel",
)


def _odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def connect() -> pyodbc.Connection:
    """Open a fresh connection; credentials are read only from environment variables."""
    server = os.getenv("DB_SERVER", "").strip()
    database = os.getenv("DB_NAME", "CalculadoraPokemonDB").strip()
    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")
    if not server or not user or not password:
        raise RuntimeError("Configura DB_SERVER, DB_USER y DB_PASSWORD en el archivo .env.")

    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    trust_certificate = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "yes").lower()
    connection_string = (
        f"DRIVER={_odbc_value(driver)};"
        f"SERVER={_odbc_value(server)};"
        f"DATABASE={_odbc_value(database)};"
        f"UID={_odbc_value(user)};"
        f"PWD={_odbc_value(password)};"
        "Encrypt=yes;"
        f"TrustServerCertificate={'yes' if trust_certificate in {'1', 'true', 'yes'} else 'no'};"
        "Connection Timeout=5;"
    )
    return pyodbc.connect(connection_string, autocommit=False)


def active_status_id(cursor) -> int:
    configured = os.getenv("DB_ACTIVE_STATUS_ID", "").strip()
    if configured:
        try:
            return int(configured)
        except ValueError as exc:
            raise RuntimeError("DB_ACTIVE_STATUS_ID debe ser un entero.") from exc

    row = cursor.execute(
        "SELECT TOP (1) ID_ESTADO FROM dbo.ESTADOS "
        "WHERE LOWER(NOMBRE_ESTADO) IN (N'activo', N'active')"
    ).fetchone()
    if row is None:
        raise RuntimeError(
            "No se encontró el estado Activo/Active en dbo.ESTADOS. "
            "Configura DB_ACTIVE_STATUS_ID en .env."
        )
    return int(row[0])


def ensure_generation(cursor, api_id: int, name: str, status_id: int) -> int:
    row = cursor.execute(
        "SELECT ID_GENERACION FROM dbo.GENERACIONES WHERE API_ID = ?", api_id
    ).fetchone()
    if row:
        return int(row[0])
    return int(cursor.execute(
        "INSERT INTO dbo.GENERACIONES (API_ID, NOMBRE, FECHA_REGISTRO, ID_ESTADO) "
        "OUTPUT INSERTED.ID_GENERACION VALUES (?, ?, SYSUTCDATETIME(), ?)",
        api_id, name, status_id,
    ).fetchone()[0])


def ensure_version(cursor, generation_id: int, status_id: int) -> int:
    api_name = "diamond-pearl"
    row = cursor.execute(
        "SELECT TOP (1) ID_VERSION FROM dbo.VERSIONES_JUEGO "
        "WHERE ID_GENERACION = ? AND API_NOMBRE IN "
        "(N'diamond-pearl', N'diamond', N'pearl', N'platinum') "
        "ORDER BY CASE API_NOMBRE WHEN N'diamond-pearl' THEN 0 "
        "WHEN N'diamond' THEN 1 WHEN N'pearl' THEN 2 ELSE 3 END",
        generation_id,
    ).fetchone()
    if row:
        return int(row[0])
    return int(cursor.execute(
        "INSERT INTO dbo.VERSIONES_JUEGO "
        "(API_NOMBRE, NOMBRE_MOSTRADO, ID_GENERACION, FECHA_REGISTRO, ID_ESTADO) "
        "OUTPUT INSERTED.ID_VERSION VALUES (?, ?, ?, SYSUTCDATETIME(), ?)",
        api_name, "Diamante/Perla (Gen. IV)", generation_id, status_id,
    ).fetchone()[0])


def _upsert_type(cursor, item: dict, status_id: int) -> int:
    row = cursor.execute(
        "SELECT ID_TIPO FROM dbo.TIPOS WHERE API_ID = ?", item["id"]
    ).fetchone()
    if row:
        cursor.execute(
            "UPDATE dbo.TIPOS SET NOMBRE = ?, API_URL = ?, ID_ESTADO = ? WHERE ID_TIPO = ?",
            item["name"], item["url"], status_id, int(row[0]),
        )
        return int(row[0])
    return int(cursor.execute(
        "INSERT INTO dbo.TIPOS (API_ID, NOMBRE, API_URL, FECHA_REGISTRO, ID_ESTADO) "
        "OUTPUT INSERTED.ID_TIPO VALUES (?, ?, ?, SYSUTCDATETIME(), ?)",
        item["id"], item["name"], item["url"], status_id,
    ).fetchone()[0])


def save_pokemon(payload: dict) -> None:
    with closing(connect()) as connection:
        try:
            cursor = connection.cursor()
            status_id = active_status_id(cursor)
            generation_api_id = GENERATION_IDS[payload["generation"]]
            generation_id = ensure_generation(
                cursor, generation_api_id, payload["generation"], status_id
            )
            row = cursor.execute(
                "SELECT ID_POKEMON FROM dbo.POKEMON WHERE API_ID = ?", payload["id"]
            ).fetchone()
            if row:
                pokemon_id = int(row[0])
                cursor.execute(
                    "UPDATE dbo.POKEMON SET NOMBRE = ?, ALTURA = ?, PESO = ?, "
                    "API_URL = ?, ID_GENERACION = ?, ID_ESTADO = ? WHERE ID_POKEMON = ?",
                    payload["name"], payload["height"], payload["weight"],
                    payload["url"], generation_id, status_id, pokemon_id,
                )
            else:
                pokemon_id = int(cursor.execute(
                    "INSERT INTO dbo.POKEMON "
                    "(API_ID, NOMBRE, ALTURA, PESO, API_URL, ID_GENERACION, FECHA_REGISTRO, ID_ESTADO) "
                    "OUTPUT INSERTED.ID_POKEMON VALUES (?, ?, ?, ?, ?, ?, SYSUTCDATETIME(), ?)",
                    payload["id"], payload["name"], payload["height"], payload["weight"],
                    payload["url"], generation_id, status_id,
                ).fetchone()[0])

            cursor.execute("DELETE FROM dbo.POKEMON_TIPOS WHERE ID_POKEMON = ?", pokemon_id)
            for slot, item in enumerate(payload["types"], 1):
                type_id = _upsert_type(cursor, item, status_id)
                cursor.execute(
                    "INSERT INTO dbo.POKEMON_TIPOS "
                    "(ID_POKEMON, ID_TIPO, SLOT, FECHA_REGISTRO, ID_ESTADO) "
                    "VALUES (?, ?, ?, SYSUTCDATETIME(), ?)",
                    pokemon_id, type_id, slot, status_id,
                )

            cursor.execute(
                "DELETE FROM dbo.POKEMON_ESTADISTICAS WHERE ID_POKEMON = ?", pokemon_id
            )
            for name, stat_data in payload["stats"].items():
                stat = cursor.execute(
                    "SELECT ID_ESTADISTICA FROM dbo.ESTADISTICAS "
                    "WHERE API_ID = ? OR NOMBRE = ?",
                    stat_data["id"], name,
                ).fetchone()
                if stat is None:
                    raise RuntimeError(
                        f"Falta la estadística '{name}' en dbo.ESTADISTICAS; "
                        "carga primero el catálogo de estadísticas."
                    )
                cursor.execute(
                    "INSERT INTO dbo.POKEMON_ESTADISTICAS "
                    "(ID_POKEMON, ID_ESTADISTICA, VALOR_BASE, FECHA_REGISTRO, ID_ESTADO) "
                    "VALUES (?, ?, ?, SYSUTCDATETIME(), ?)",
                    pokemon_id, int(stat[0]), stat_data["value"], status_id,
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def get_pokemon(api_id: int) -> dict | None:
    with closing(connect()) as connection:
        cursor = connection.cursor()
        pokemon = cursor.execute(
            "SELECT ID_POKEMON, API_ID, NOMBRE, API_URL FROM dbo.POKEMON WHERE API_ID = ?",
            api_id,
        ).fetchone()
        if pokemon is None:
            return None
        pokemon_id = int(pokemon[0])
        types = cursor.execute(
            "SELECT t.API_ID, t.NOMBRE FROM dbo.POKEMON_TIPOS pt "
            "JOIN dbo.TIPOS t ON t.ID_TIPO = pt.ID_TIPO "
            "WHERE pt.ID_POKEMON = ? ORDER BY pt.SLOT",
            pokemon_id,
        ).fetchall()
        stats = cursor.execute(
            "SELECT e.API_ID, e.NOMBRE, pe.VALOR_BASE FROM dbo.POKEMON_ESTADISTICAS pe "
            "JOIN dbo.ESTADISTICAS e ON e.ID_ESTADISTICA = pe.ID_ESTADISTICA "
            "WHERE pe.ID_POKEMON = ?",
            pokemon_id,
        ).fetchall()
    values = {}
    for row in stats:
        stat_name = STAT_API_IDS.get(int(row[0])) if row[0] is not None else None
        if stat_name is None:
            stat_name = str(row[1]).replace("_", "-").lower()
        values[stat_name] = int(row[2])
    if any(name not in values for name in STAT_NAMES):
        raise RuntimeError(
            f"El Pokémon {api_id} no tiene las seis estadísticas normalizadas en SQL Server."
        )
    return {
        "id": int(pokemon[1]),
        "name": str(pokemon[2]),
        "types": [
            TYPE_API_IDS.get(int(row[0]), str(row[1]).lower())
            for row in types
        ],
        "base": [values[name] for name in STAT_NAMES],
        "url": str(pokemon[3] or ""),
    }


def search_pokemon(query: str, limit: int = 20) -> list[dict]:
    with closing(connect()) as connection:
        cursor = connection.cursor()
        if query.isdigit():
            rows = cursor.execute(
                "SELECT TOP (?) API_ID, NOMBRE FROM dbo.POKEMON "
                "WHERE API_ID = ? AND API_ID BETWEEN 1 AND 493 ORDER BY API_ID",
                    limit, int(query),
            ).fetchall()
        else:
            rows = cursor.execute(
                "SELECT TOP (?) API_ID, NOMBRE FROM dbo.POKEMON "
                "WHERE NOMBRE LIKE ? AND API_ID BETWEEN 1 AND 493 ORDER BY NOMBRE",
                limit, f"%{query}%",
            ).fetchall()
    return [{"id": int(row[0]), "name": str(row[1])} for row in rows]


def save_move(payload: dict) -> None:
    with closing(connect()) as connection:
        try:
            cursor = connection.cursor()
            status_id = active_status_id(cursor)
            generation_id = ensure_generation(cursor, 4, "generation-iv", status_id)
            version_id = ensure_version(cursor, generation_id, status_id)
            type_id = None
            if payload["type"]:
                type_id = _upsert_type(cursor, payload["type"], status_id)
            row = cursor.execute(
                "SELECT ID_MOVIMIENTO FROM dbo.MOVIMIENTOS WHERE API_ID = ?", payload["id"]
            ).fetchone()
            if row:
                move_id = int(row[0])
                cursor.execute(
                    "UPDATE dbo.MOVIMIENTOS SET NOMBRE = ?, API_URL = ?, ID_ESTADO = ? "
                    "WHERE ID_MOVIMIENTO = ?",
                    payload["name"], payload["url"], status_id, move_id,
                )
            else:
                move_id = int(cursor.execute(
                    "INSERT INTO dbo.MOVIMIENTOS (API_ID, NOMBRE, API_URL, FECHA_REGISTRO, ID_ESTADO) "
                    "OUTPUT INSERTED.ID_MOVIMIENTO VALUES (?, ?, ?, SYSUTCDATETIME(), ?)",
                    payload["id"], payload["name"], payload["url"], status_id,
                ).fetchone()[0])
            exists = cursor.execute(
                "SELECT 1 FROM dbo.MOVIMIENTO_VERSION WHERE ID_MOVIMIENTO = ? AND ID_VERSION = ?",
                move_id, version_id,
            ).fetchone()
            if exists:
                cursor.execute(
                    "UPDATE dbo.MOVIMIENTO_VERSION SET ID_TIPO = ?, POTENCIA = ?, "
                    "PRECISION_MOVIMIENTO = ?, PP = ?, CATEGORIA = ?, ID_ESTADO = ? "
                    "WHERE ID_MOVIMIENTO = ? AND ID_VERSION = ?",
                    type_id, payload["power"], payload["accuracy"], payload["pp"],
                    payload["category"], status_id, move_id, version_id,
                )
            else:
                cursor.execute(
                    "INSERT INTO dbo.MOVIMIENTO_VERSION "
                    "(ID_MOVIMIENTO, ID_VERSION, ID_TIPO, POTENCIA, PRECISION_MOVIMIENTO, "
                    "PP, CATEGORIA, FECHA_REGISTRO, ID_ESTADO) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME(), ?)",
                    move_id, version_id, type_id, payload["power"], payload["accuracy"],
                    payload["pp"], payload["category"], status_id,
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def list_moves(query: str = "", limit: int = 100) -> list[dict]:
    with closing(connect()) as connection:
        cursor = connection.cursor()
        pattern = f"%{query}%"
        rows = cursor.execute(
            "WITH ranked AS ("
            " SELECT m.API_ID, m.NOMBRE, t.API_ID AS TYPE_API_ID, t.NOMBRE AS TYPE_NAME, "
            " mv.CATEGORIA, mv.POTENCIA, mv.PRECISION_MOVIMIENTO, mv.PP, "
            " ROW_NUMBER() OVER (PARTITION BY m.ID_MOVIMIENTO ORDER BY "
            " CASE v.API_NOMBRE WHEN N'diamond-pearl' THEN 0 WHEN N'diamond' THEN 1 "
            " WHEN N'pearl' THEN 2 ELSE 3 END) AS rn "
            " FROM dbo.MOVIMIENTOS m "
            " JOIN dbo.MOVIMIENTO_VERSION mv ON mv.ID_MOVIMIENTO = m.ID_MOVIMIENTO "
            " JOIN dbo.VERSIONES_JUEGO v ON v.ID_VERSION = mv.ID_VERSION "
            " LEFT JOIN dbo.TIPOS t ON t.ID_TIPO = mv.ID_TIPO "
            " WHERE v.ID_GENERACION = (SELECT ID_GENERACION FROM dbo.GENERACIONES WHERE API_ID = 4)"
            ") SELECT TOP (?) API_ID, NOMBRE, TYPE_API_ID, TYPE_NAME, CATEGORIA, "
            "POTENCIA, PRECISION_MOVIMIENTO, PP FROM ranked "
            "WHERE rn = 1 AND NOMBRE LIKE ? ORDER BY NOMBRE",
            limit, pattern,
        ).fetchall()
    return [
        {"api_id": int(row[0]), "api_name": str(row[1]), "name": str(row[1]),
         "type": TYPE_API_IDS.get(int(row[2]), str(row[3]).lower()) if row[2] is not None else None,
         "category": row[4], "power": row[5], "accuracy": row[6], "pp": row[7]}
        for row in rows
    ]


def type_chart_ready() -> bool:
    with closing(connect()) as connection:
        row = connection.cursor().execute(
            "SELECT COUNT(DISTINCT CONCAT(e.ID_TIPO_ATAQUE, ':', e.ID_TIPO_DEFENSA)) "
            "FROM dbo.EFECTIVIDAD_TIPOS e "
            "JOIN dbo.GENERACIONES g ON g.ID_GENERACION = e.ID_GENERACION "
            "JOIN dbo.TIPOS a ON a.ID_TIPO = e.ID_TIPO_ATAQUE "
            "JOIN dbo.TIPOS d ON d.ID_TIPO = e.ID_TIPO_DEFENSA "
            "WHERE g.API_ID = 4 AND a.API_ID BETWEEN 1 AND 17 "
            "AND d.API_ID BETWEEN 1 AND 17"
        ).fetchone()
    return bool(row and int(row[0]) == len(GEN4_TYPES) ** 2)


def save_gen4_type_chart(chart: dict[tuple[str, str], float], types: list[dict]) -> None:
    if len(chart) != len(GEN4_TYPES) ** 2:
        raise ValueError("La matriz de efectividad debe incluir exactamente 289 combinaciones.")
    with closing(connect()) as connection:
        try:
            cursor = connection.cursor()
            status_id = active_status_id(cursor)
            generation_id = ensure_generation(cursor, 4, "generation-iv", status_id)
            type_db_ids = {
                item["name"]: _upsert_type(cursor, item, status_id)
                for item in types
            }
            if set(type_db_ids) != set(GEN4_TYPES):
                raise ValueError("El catálogo debe incluir los 17 tipos de Gen. IV.")
            for attack in GEN4_TYPES:
                for defense in GEN4_TYPES:
                    attack_id = type_db_ids[attack]
                    defense_id = type_db_ids[defense]
                    multiplier = chart[(attack, defense)]
                    exists = cursor.execute(
                        "SELECT 1 FROM dbo.EFECTIVIDAD_TIPOS "
                        "WHERE ID_TIPO_ATAQUE = ? AND ID_TIPO_DEFENSA = ? AND ID_GENERACION = ?",
                        attack_id, defense_id, generation_id,
                    ).fetchone()
                    if exists:
                        cursor.execute(
                            "UPDATE dbo.EFECTIVIDAD_TIPOS SET MULTIPLICADOR = ?, ID_ESTADO = ? "
                            "WHERE ID_TIPO_ATAQUE = ? AND ID_TIPO_DEFENSA = ? AND ID_GENERACION = ?",
                            multiplier, status_id, attack_id, defense_id, generation_id,
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO dbo.EFECTIVIDAD_TIPOS "
                            "(ID_TIPO_ATAQUE, ID_TIPO_DEFENSA, ID_GENERACION, MULTIPLICADOR, "
                            "FECHA_REGISTRO, ID_ESTADO) VALUES (?, ?, ?, ?, SYSUTCDATETIME(), ?)",
                            attack_id, defense_id, generation_id, multiplier, status_id,
                        )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def move_for_battle(api_name: str, generation: int = 4) -> dict | None:
    with closing(connect()) as connection:
        row = connection.cursor().execute(
            "SELECT TOP (1) m.API_ID, m.NOMBRE, t.API_ID, t.NOMBRE, "
            "mv.CATEGORIA, mv.POTENCIA, mv.PRECISION_MOVIMIENTO, mv.PP "
            "FROM dbo.MOVIMIENTOS m "
            "JOIN dbo.MOVIMIENTO_VERSION mv ON mv.ID_MOVIMIENTO = m.ID_MOVIMIENTO "
            "JOIN dbo.VERSIONES_JUEGO v ON v.ID_VERSION = mv.ID_VERSION "
            "LEFT JOIN dbo.TIPOS t ON t.ID_TIPO = mv.ID_TIPO "
            "WHERE m.NOMBRE = ? AND v.ID_GENERACION = "
            "(SELECT ID_GENERACION FROM dbo.GENERACIONES WHERE API_ID = 4) "
            "ORDER BY CASE v.API_NOMBRE WHEN N'diamond-pearl' THEN 0 "
            "WHEN N'diamond' THEN 1 WHEN N'pearl' THEN 2 ELSE 3 END",
            api_name,
        ).fetchone()
    if row is None:
        return None
    type_name = (
        TYPE_API_IDS.get(int(row[2]), str(row[3]).lower()) if row[2] is not None else None
    )
    return {"id": int(row[0]), "name": str(row[1]), "type": type_name,
            "category": row[4], "power": row[5], "accuracy": row[6], "pp": row[7]}


def move_effectiveness(move_type: str, defender_types: list[str]) -> float | None:
    with closing(connect()) as connection:
        cursor = connection.cursor()
        attack_api_id = TYPE_IDS.get(move_type)
        if attack_api_id is None:
            return None
        attack = cursor.execute(
            "SELECT ID_TIPO FROM dbo.TIPOS WHERE API_ID = ?", attack_api_id
        ).fetchone()
        if attack is None:
            return None
        multiplier = 1.0
        for name in defender_types:
            defense_api_id = TYPE_IDS.get(name)
            if defense_api_id is None:
                return None
            defense = cursor.execute(
                "SELECT ID_TIPO FROM dbo.TIPOS WHERE API_ID = ?", defense_api_id
            ).fetchone()
            if defense is None:
                return None
            value = cursor.execute(
                "SELECT e.MULTIPLICADOR FROM dbo.EFECTIVIDAD_TIPOS e "
                "JOIN dbo.GENERACIONES g ON g.ID_GENERACION = e.ID_GENERACION "
                "WHERE e.ID_TIPO_ATAQUE = ? AND e.ID_TIPO_DEFENSA = ? AND g.API_ID = 4",
                int(attack[0]), int(defense[0]),
            ).fetchone()
            if value is None:
                return None
            multiplier *= float(value[0])
    return multiplier
