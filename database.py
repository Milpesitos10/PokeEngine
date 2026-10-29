"""Acceso a SQL Server (pyodbc). Una conexión por operación, consultas parametrizadas, transacciones."""
from __future__ import annotations

import logging
import re
from contextlib import contextmanager

try:
    import pyodbc
except ImportError:  # permite importar el módulo sin ODBC (p. ej. en pruebas unitarias)
    pyodbc = None

from config import get_settings

log = logging.getLogger("pokemon.db")


class DatabaseError(Exception):
    """Error genérico de base de datos (mensaje apto para el cliente)."""


class DatabaseUnavailable(DatabaseError):
    """No se pudo conectar (servidor inaccesible, credenciales inválidas, falta de configuración)."""


class IntegrityViolation(DatabaseError):
    """Violación de clave foránea, UNIQUE o CHECK."""


def _redact(text: str, *secrets: str) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "***")
    return re.sub(r"(PWD|Password)=[^;]*", r"\1=***", text, flags=re.I)


def _braced(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def build_connection_string(role: str = "read") -> tuple[str, str]:
    """Devuelve (cadena, secreto). role: 'read' (API) o 'sync' (escritura limitada)."""
    s = get_settings()
    parts = [
        f"DRIVER={_braced(s.db_driver)}",
        f"SERVER={s.db_server}",
        f"DATABASE={s.db_name}",
        f"Encrypt={'yes' if s.db_encrypt else 'no'}",
        f"TrustServerCertificate={'yes' if s.db_trust_cert else 'no'}",
        "APP=CalculadoraPokemon",
    ]
    secret = ""
    if s.db_auth == "windows":
        parts.append("Trusted_Connection=yes")
    else:
        user, secret = (s.db_user, s.db_password) if role == "read" else (s.db_sync_user, s.db_sync_password)
        if not user or not secret:
            raise DatabaseUnavailable(f"Credenciales de SQL Server no configuradas para el rol '{role}'.")
        parts += [f"UID={_braced(user)}", f"PWD={_braced(secret)}"]
    return ";".join(parts), secret


@contextmanager
def transaction(role: str = "read"):
    """Cursor dentro de una transacción: commit si todo va bien, rollback si falla, cierre siempre."""
    if pyodbc is None:
        raise DatabaseUnavailable("pyodbc no está instalado.")
    s = get_settings()
    conn_str, secret = build_connection_string(role)
    try:
        conn = pyodbc.connect(conn_str, timeout=s.db_login_timeout, autocommit=False)
    except pyodbc.Error as exc:
        log.error("Fallo de conexión a SQL Server (rol=%s): %s", role, _redact(str(exc), secret))
        raise DatabaseUnavailable("No se pudo conectar con la base de datos.") from None
    conn.timeout = s.db_query_timeout
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except pyodbc.IntegrityError as exc:
        conn.rollback()
        log.warning("Violación de integridad: %s", _redact(str(exc), secret))
        raise IntegrityViolation("La operación viola una restricción de la base de datos.") from None
    except pyodbc.Error as exc:
        conn.rollback()
        log.error("Error SQL: %s", _redact(str(exc), secret))
        raise DatabaseError("Error al ejecutar la consulta.") from None
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def _rows(cur) -> list[dict]:
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def ping() -> bool:
    with transaction("read") as cur:
        cur.execute("SELECT 1")
        return cur.fetchone()[0] == 1


def like_escape(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").replace("[", "\\[")


# ---------------------------------------------------------------- escritura (solo sync_service)
_IDENT = re.compile(r"^[A-Z][A-Z0-9_]*$")
ALLOWED_TABLES = {
    "ESTADOS", "GENERACIONES", "VERSIONES_JUEGO", "TIPOS", "POKEMON", "ESTADISTICAS", "POKEMON_ESTADISTICAS",
    "POKEMON_TIPOS", "MOVIMIENTOS", "MOVIMIENTO_VERSION", "EFECTIVIDAD_TIPOS", "HABILIDADES",
    "POKEMON_HABILIDADES", "SINCRONIZACIONES_API",
}


def upsert(cur, table: str, keys: dict, values: dict | None = None, update: bool = True) -> str:
    """UPDATE-then-INSERT atómico (UPDLOCK+SERIALIZABLE). Idempotente: devuelve inserted|updated|unchanged.

    Los identificadores se validan contra una lista blanca; los valores siempre van como parámetros.
    """
    if table not in ALLOWED_TABLES:
        raise ValueError("Tabla no permitida.")
    for col in (*keys, *(values or {})):
        if not _IDENT.match(col):
            raise ValueError("Nombre de columna no válido.")
    where = " AND ".join(f"{k} = ?" for k in keys)
    if values and update:
        sets = ", ".join(f"{c} = ?" for c in values)
        cur.execute(f"UPDATE dbo.{table} WITH (UPDLOCK, SERIALIZABLE) SET {sets} WHERE {where}", (*values.values(), *keys.values()))
        if cur.rowcount > 0:
            return "updated"
    else:
        cur.execute(f"SELECT 1 FROM dbo.{table} WITH (UPDLOCK, SERIALIZABLE) WHERE {where}", tuple(keys.values()))
        if cur.fetchone():
            return "unchanged"
    cols = {**keys, **(values or {})}
    cur.execute(f"INSERT INTO dbo.{table} ({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})", tuple(cols.values()))
    return "inserted"


def lookup(cur, table: str, id_col: str, where_col: str, value):
    if table not in ALLOWED_TABLES or not _IDENT.match(id_col) or not _IDENT.match(where_col):
        raise ValueError("Identificador no permitido.")
    cur.execute(f"SELECT {id_col} FROM dbo.{table} WHERE {where_col} = ?", (value,))
    row = cur.fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------- lectura (cuenta de solo lectura)
def search_pokemon(term: str | int, limit: int = 20) -> list[dict]:
    with transaction("read") as cur:
        if isinstance(term, int):
            cur.execute("SELECT TOP (?) API_ID AS id, NOMBRE AS name FROM dbo.POKEMON WHERE ID_ESTADO = 1 AND API_ID = ?", (limit, term))
        else:
            cur.execute(
                "SELECT TOP (?) API_ID AS id, NOMBRE AS name FROM dbo.POKEMON "
                "WHERE ID_ESTADO = 1 AND NOMBRE LIKE ? ESCAPE '\\' ORDER BY API_ID",
                (limit, f"%{like_escape(term)}%"),
            )
        return _rows(cur)


def get_pokemon(api_id: int) -> dict | None:
    with transaction("read") as cur:
        cur.execute(
            "SELECT P.ID_POKEMON, P.API_ID, P.NOMBRE, P.ALTURA, P.PESO, G.API_ID AS GEN FROM dbo.POKEMON P "
            "LEFT JOIN dbo.GENERACIONES G ON G.ID_GENERACION = P.ID_GENERACION WHERE P.API_ID = ? AND P.ID_ESTADO = 1",
            (api_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        pid = row.ID_POKEMON
        out = {"id": row.API_ID, "name": row.NOMBRE, "height": row.ALTURA, "weight": row.PESO, "generation": row.GEN}
        cur.execute(
            "SELECT E.NOMBRE, PE.VALOR_BASE FROM dbo.POKEMON_ESTADISTICAS PE JOIN dbo.ESTADISTICAS E "
            "ON E.ID_ESTADISTICA = PE.ID_ESTADISTICA WHERE PE.ID_POKEMON = ? AND PE.ID_ESTADO = 1 AND E.ID_ESTADO = 1",
            (pid,),
        )
        out["base_stats"] = {r[0]: r[1] for r in cur.fetchall()}
        cur.execute(
            "SELECT T.NOMBRE FROM dbo.POKEMON_TIPOS PT JOIN dbo.TIPOS T ON T.ID_TIPO = PT.ID_TIPO "
            "WHERE PT.ID_POKEMON = ? AND PT.ID_ESTADO = 1 ORDER BY PT.SLOT",
            (pid,),
        )
        out["types"] = [r[0] for r in cur.fetchall()]
        cur.execute(
            "SELECT H.NOMBRE, PH.SLOT, PH.ES_OCULTA FROM dbo.POKEMON_HABILIDADES PH JOIN dbo.HABILIDADES H "
            "ON H.ID_HABILIDAD = PH.ID_HABILIDAD WHERE PH.ID_POKEMON = ? AND PH.ID_ESTADO = 1 ORDER BY PH.SLOT",
            (pid,),
        )
        out["abilities"] = [{"name": r[0], "slot": r[1], "hidden": bool(r[2])} for r in cur.fetchall()]
        return out


_MOVE_SELECT = (
    "SELECT M.API_ID AS id, M.NOMBRE AS name, T.NOMBRE AS type, MV.CATEGORIA AS category, MV.POTENCIA AS power, "
    "MV.PRECISION_MOVIMIENTO AS accuracy, MV.PP AS pp FROM dbo.MOVIMIENTOS M "
    "JOIN dbo.MOVIMIENTO_VERSION MV ON MV.ID_MOVIMIENTO = M.ID_MOVIMIENTO "
    "JOIN dbo.VERSIONES_JUEGO V ON V.ID_VERSION = MV.ID_VERSION "
    "LEFT JOIN dbo.TIPOS T ON T.ID_TIPO = MV.ID_TIPO "
    "WHERE V.API_NOMBRE = ? AND M.ID_ESTADO = 1 AND MV.ID_ESTADO = 1 AND V.ID_ESTADO = 1"
)


def search_moves(version: str, term: str | None, limit: int) -> list[dict]:
    with transaction("read") as cur:
        if term:
            cur.execute(_MOVE_SELECT.replace("SELECT ", "SELECT TOP (?) ", 1) + " AND M.NOMBRE LIKE ? ESCAPE '\\' ORDER BY M.NOMBRE",
                        (limit, version, f"%{like_escape(term)}%"))
        else:
            cur.execute(_MOVE_SELECT.replace("SELECT ", "SELECT TOP (?) ", 1) + " ORDER BY M.NOMBRE", (limit, version))
        return _rows(cur)


def get_moves_by_names(version: str, names: list[str]) -> list[dict]:
    if not names:
        return []
    marks = ", ".join(["?"] * len(names))
    with transaction("read") as cur:
        cur.execute(_MOVE_SELECT + f" AND M.NOMBRE IN ({marks})", (version, *names))
        return _rows(cur)


def get_multipliers(gen_api_id: int, attack_types: list[str], defend_types: list[str]) -> dict[tuple[str, str], float]:
    if not attack_types or not defend_types:
        return {}
    qa, qd = ", ".join(["?"] * len(attack_types)), ", ".join(["?"] * len(defend_types))
    with transaction("read") as cur:
        cur.execute(
            "SELECT TA.NOMBRE, TD.NOMBRE, E.MULTIPLICADOR FROM dbo.EFECTIVIDAD_TIPOS E "
            "JOIN dbo.TIPOS TA ON TA.ID_TIPO = E.ID_TIPO_ATAQUE JOIN dbo.TIPOS TD ON TD.ID_TIPO = E.ID_TIPO_DEFENSA "
            "JOIN dbo.GENERACIONES G ON G.ID_GENERACION = E.ID_GENERACION "
            f"WHERE G.API_ID = ? AND E.ID_ESTADO = 1 AND TA.NOMBRE IN ({qa}) AND TD.NOMBRE IN ({qd})",
            (gen_api_id, *attack_types, *defend_types),
        )
        return {(r[0], r[1]): float(r[2]) for r in cur.fetchall()}


# ---------------------------------------------------------------- índice (Pokédex de la BD)
SORTS = {"number": "P.API_ID", "name": "P.NOMBRE", "total": "TOTAL"}
_DEX_FROM = "FROM dbo.POKEMON P LEFT JOIN dbo.GENERACIONES G ON G.ID_GENERACION = P.ID_GENERACION"


def _pokedex_order(sort: str, order: str) -> str:
    """ORDER BY sin columnas repetidas (SQL Server lo rechaza): desempata por número solo si no se ordena ya por él."""
    col, direction = SORTS.get(sort, "P.API_ID"), ("DESC" if order == "desc" else "ASC")
    return f"{col} {direction}" if col == "P.API_ID" else f"{col} {direction}, P.API_ID"


def _pokedex_filters(term, type_name, gen) -> tuple[str, list]:
    where, params = ["P.ID_ESTADO = 1"], []
    if term is not None:
        if isinstance(term, int):
            where.append("P.API_ID = ?")
            params.append(term)
        else:
            where.append("P.NOMBRE LIKE ? ESCAPE '\\'")
            params.append(f"%{like_escape(term)}%")
    if type_name:
        where.append("EXISTS (SELECT 1 FROM dbo.POKEMON_TIPOS PT JOIN dbo.TIPOS T ON T.ID_TIPO = PT.ID_TIPO "
                     "WHERE PT.ID_POKEMON = P.ID_POKEMON AND PT.ID_ESTADO = 1 AND T.NOMBRE = ?)")
        params.append(type_name)
    if gen:
        where.append("G.API_ID = ?")
        params.append(gen)
    return " AND ".join(where), params


def pokedex(term, type_name, gen, sort: str, order: str, limit: int, offset: int) -> tuple[int, list[dict]]:
    where, params = _pokedex_filters(term, type_name, gen)
    direction = "DESC" if order == "desc" else "ASC"
    with transaction("read") as cur:
        cur.execute(f"SELECT COUNT(*) {_DEX_FROM} WHERE {where}", params)
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT P.API_ID AS id, P.NOMBRE AS name, G.API_ID AS generation, (SELECT SUM(PE.VALOR_BASE) FROM "
            "dbo.POKEMON_ESTADISTICAS PE WHERE PE.ID_POKEMON = P.ID_POKEMON AND PE.ID_ESTADO = 1) AS total "
            f"{_DEX_FROM} WHERE {where} ORDER BY {_pokedex_order(sort, order)} "
            "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY", (*params, offset, limit))
        items = _rows(cur)
        for it in items:
            it["types"] = []
        if items:
            by_id = {it["id"]: it for it in items}
            cur.execute("SELECT P.API_ID, T.NOMBRE FROM dbo.POKEMON_TIPOS PT JOIN dbo.POKEMON P ON P.ID_POKEMON = PT.ID_POKEMON "
                        "JOIN dbo.TIPOS T ON T.ID_TIPO = PT.ID_TIPO WHERE PT.ID_ESTADO = 1 AND P.API_ID IN "
                        f"({', '.join(['?'] * len(by_id))}) ORDER BY P.API_ID, PT.SLOT", list(by_id))
            for api_id, tname in cur.fetchall():
                by_id[api_id]["types"].append(tname)
    return total, items


def catalogs(version: str) -> dict:
    """Valores para los filtros del índice, leídos de TIPOS, GENERACIONES y MOVIMIENTO_VERSION."""
    with transaction("read") as cur:
        cur.execute("SELECT NOMBRE FROM dbo.TIPOS WHERE ID_ESTADO = 1 ORDER BY API_ID")
        types = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT API_ID, NOMBRE FROM dbo.GENERACIONES WHERE ID_ESTADO = 1 ORDER BY API_ID")
        gens = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT MV.CATEGORIA FROM dbo.MOVIMIENTO_VERSION MV JOIN dbo.VERSIONES_JUEGO V "
                    "ON V.ID_VERSION = MV.ID_VERSION WHERE V.API_NOMBRE = ? AND MV.ID_ESTADO = 1 AND MV.CATEGORIA IS NOT NULL "
                    "ORDER BY MV.CATEGORIA", (version,))
        cats = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM dbo.POKEMON WHERE ID_ESTADO = 1")
        n_pokemon = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT M.ID_MOVIMIENTO) FROM dbo.MOVIMIENTOS M JOIN dbo.MOVIMIENTO_VERSION MV "
                    "ON MV.ID_MOVIMIENTO = M.ID_MOVIMIENTO JOIN dbo.VERSIONES_JUEGO V ON V.ID_VERSION = MV.ID_VERSION "
                    "WHERE V.API_NOMBRE = ? AND M.ID_ESTADO = 1 AND MV.ID_ESTADO = 1", (version,))
        n_moves = cur.fetchone()[0]
    return {"types": types, "generations": gens, "move_categories": cats, "version": version,
            "counts": {"pokemon": n_pokemon, "moves": n_moves}}


def fetch_count(table: str) -> int:
    if table not in ALLOWED_TABLES:
        raise ValueError("Tabla no permitida.")
    with transaction("read") as cur:
        cur.execute(f"SELECT COUNT(*) FROM dbo.{table}")
        return cur.fetchone()[0]


EXPECTED_TABLES = sorted(ALLOWED_TABLES)


def schema_diagnostics() -> dict:
    """Solo lectura: columnas reales y tablas esperadas ausentes (sección 3 del encargo)."""
    with transaction("read") as cur:
        cur.execute(
            "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = 'dbo' ORDER BY TABLE_NAME, ORDINAL_POSITION"
        )
        tables: dict[str, list] = {}
        for t, c, d, n in cur.fetchall():
            tables.setdefault(t, []).append(f"{c} {d}{'' if n == 'YES' else ' NOT NULL'}")
    return {"tables": tables, "missing": [t for t in EXPECTED_TABLES if t not in tables]}
