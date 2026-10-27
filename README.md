# Calculadora de Daño Pokémon

Interfaz web estática con una API Python. La API lee y escribe el catálogo normalizado en SQL Server y obtiene de PokeAPI, bajo demanda, los Pokémon y movimientos que aún no estén guardados.

## Requisitos

- Python 3.10 o posterior.
- SQL Server con el esquema de `CalculadoraPokemonDB`.
- Microsoft ODBC Driver 18 for SQL Server instalado.
- Acceso a internet para consultar PokeAPI y descargar sprites.

## Configuración en Windows

Desde la carpeta del proyecto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edita `.env` localmente con el servidor y las credenciales de SQL Server. No compartas ni subas ese archivo. Configura `DB_SERVER`, `DB_NAME`, `DB_USER` y `DB_PASSWORD`. Si la tabla `ESTADOS` no tiene un estado llamado `Activo` o `Active`, define también `DB_ACTIVE_STATUS_ID` con el ID correspondiente.

La tabla `ESTADISTICAS` debe tener las seis filas de estadísticas de PokeAPI (`API_ID` 1 a 6, o los nombres `hp`, `attack`, `defense`, `special-attack`, `special-defense`, `speed`). Las demás tablas y columnas usadas por la API deben corresponder al esquema existente.

Arranca la aplicación:

```powershell
.\.venv\Scripts\python.exe run_api.py
```

Abre <http://localhost:8000>. La interfaz y la API se sirven desde el mismo origen, así que `script.js` conserva `const API='/api'`. Verifica la conexión en <http://localhost:8000/api/health>.

## Preparar el catálogo de combate

Antes del primer combate, sincroniza la matriz Gen. IV una vez desde la carpeta del proyecto:

```powershell
.\.venv\Scripts\python.exe sync_catalogs.py
```

El comando usa PokeAPI para reconstruir las 289 combinaciones de los 17 tipos y las inserta o actualiza en `dbo.EFECTIVIDAD_TIPOS`. Es idempotente y se puede repetir si hace falta. Los movimientos se cargan bajo demanda y el selector muestra solo los que el Pokémon puede aprender en Diamante/Perla/Platino.

## API

| Endpoint | Descripción |
|---|---|
| `GET /api/pokemon?q=charizard` | Busca en SQL Server; si no existe, consulta PokeAPI y lo normaliza/guarda. |
| `GET /api/pokemon/{id}` | Devuelve nombre, tipos, estadísticas base y sprites. |
| `GET /api/pokemon/{id}/moves` | Lista movimientos aprendibles en Diamante/Perla/Platino; `?q=...` obtiene los datos completos de uno. |
| `GET /api/moves` | Devuelve movimientos ya guardados. |
| `GET /api/moves?q=earth` | Busca movimientos, los consulta en PokeAPI y los guarda en SQL Server. |
| `GET /api/natures` | Devuelve las naturalezas admitidas por el frontend. |
| `POST /api/battle/simulate` | Recalcula las estadísticas en el servidor y ejecuta el motor Gen. IV. |
| `GET /api/health` | Comprueba la conexión a SQL Server. |

Pokémon y movimientos se sincronizan conforme se buscan; no se descargan todos los catálogos al arrancar. Para simular combates, `EFECTIVIDAD_TIPOS` debe contener las 289 combinaciones de los 17 tipos de Gen. IV para la generación 4. La API no reemplaza esa tabla con la tabla actual de PokeAPI, porque las reglas de efectividad han cambiado desde Gen. IV.

## Pruebas del motor

Desde la carpeta del proyecto:

```powershell
pytest -q
```

La API devuelve un error explícito si faltan credenciales, tablas, estadísticas o el estado activo; no envía las credenciales al navegador.
