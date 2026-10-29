# Backend — Calculadora de Daño Pokémon (FastAPI + SQL Server + PokeAPI)

## Estado de verificación (léelo primero)
Escrito contra el script de creación que adjuntaste. **No se ha probado contra un SQL Server real ni contra PokeAPI real** (el entorno donde se generó no tenía ni red, ni FastAPI, ni pyodbc). Lo que sí se ejecutó: compilación de todos los módulos y 12 pruebas unitarias de lógica pura (cliente HTTP simulado, reglas de 4.ª gen, `upsert` con cursor falso, fórmula de estadísticas). Pendiente de ejecutar por ti: `tests/test_api.py` (necesita fastapi+httpx), `tests/test_integration_sqlserver.py` y el primer `sync` real. Hasta entonces, la integración completa **no está confirmada**.

## ⚠️ Seguridad: actúa antes de conectar nada
El script que compartiste contiene contraseñas en texto plano (`SuperPokemon`, `Datawriter`, `Reader`, `Owner`), con `CHECK_POLICY = OFF`. Considéralas expuestas: **rótalas**. Además: `SuperPokemon` es sysadmin, `Datawriter` puede borrar en todas las tablas, y `Reader` tiene `dbcreator` a nivel de servidor. Ninguna se usa en este backend. `sql/01_usuarios_app.sql` crea dos cuentas nuevas con mínimo privilegio (rellena las contraseñas antes de ejecutar):
- `app_pokemon_read`: `SELECT` (la usa la API).
- `app_pokemon_sync`: `SELECT/INSERT/UPDATE` + `DELETE` solo en `POKEMON_TIPOS` y `POKEMON_HABILIDADES` (necesario para reemplazar enlaces por la restricción `UNIQUE(ID_POKEMON, SLOT)`). Solo la usa `sync_service`.

## Estructura
`conector.py` (fachada, reglas de validación, motor pluggable, CLI) · `database.py` · `pokeapi_client.py` · `sync_service.py` · `schemas.py` · `main.py` · `config.py` · `sql/` · `data/gen4_stat_overrides.json` · `tests/`

## Instalación y ejecución
**Requisitos:** Python 3.10 o superior (3.12 recomendado; en 3.9 falla al importar los modelos).
1. Instala el [controlador ODBC 18 para SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server) (o ajusta `DB_DRIVER` al instalado: `pyodbc.drivers()`).
2. `python -m venv .venv && .venv\Scripts\activate` (Windows) / `source .venv/bin/activate`, luego `pip install -r requirements.txt`.
3. Ejecuta `sql/01_usuarios_app.sql` (como administrador) con contraseñas nuevas.
4. `cp .env.example .env` y rellénalo (contraseñas, `SYNC_API_KEY` aleatoria, `CORS_ORIGINS`).
5. Verifica el esquema real: `python conector.py diagnose` (o `sql/00_diagnostico_esquema.sql`).
6. Carga datos: `python conector.py sync-catalogs` → `python conector.py sync-pokemon 445 --moves` (o `sync-range 1 151`).
7. Arranca: `python conector.py serve --port 8001` (docs interactivas en `/docs`).
8. Frontend: pon `FRONTEND_DIR=../pokedmg` y abre `http://127.0.0.1:8001/` (mismo origen, sin CORS), o sirve el frontend aparte y añade su origen a `CORS_ORIGINS`.

## Correspondencia PokeAPI → SQL Server (según el script)
| PokeAPI | Tabla.columna | Notas |
|---|---|---|
| `generation` | `GENERACIONES` (API_ID, NOMBRE) | solo I–IV |
| version groups | `VERSIONES_JUEGO.API_NOMBRE` | `diamond-pearl`, `platinum`, `heartgold-soulsilver` |
| `type` | `TIPOS` | solo los 17 de 4.ª gen (sin `fairy`) |
| `pokemon` id/name/height/weight | `POKEMON` API_ID/NOMBRE/ALTURA/PESO | `ID_GENERACION` desde la especie |
| `stats[].base_stat` | `POKEMON_ESTADISTICAS.VALOR_BASE` + catálogo `ESTADISTICAS` | |
| `types` (+`past_types`) | `POKEMON_TIPOS` (SLOT) | resuelve tipos de 4.ª gen |
| `abilities` (+`past_abilities`) | `HABILIDADES` + `POKEMON_HABILIDADES` | **sin ocultas** (son de 5.ª gen) |
| `move` | `MOVIMIENTOS` + `MOVIMIENTO_VERSION` | valores por versión con `past_values`; categoría = `damage_class` (la división físico/especial por movimiento existe desde 4.ª gen) |
| `damage_relations` (+`past_`) | `EFECTIVIDAD_TIPOS` | 17×17 para generation-iv |
| cada sync | `SINCRONIZACIONES_API` | ID_ESTADO 1 = ok, 3 = error; se registra en transacción aparte |

Lo que **no** existe en el esquema y por tanto no se inventó: sprites (se leen de PokeAPI en cada petición, con caché), naturalezas (PokeAPI, con caché), learnset por Pokémon (se consulta a PokeAPI y se cruza con los movimientos de la BD; `not_synced` lista los que faltan). Si prefieres guardar el learnset en SQL, haría falta una tabla `POKEMON_MOVIMIENTOS`; no se creó sin tu autorización.

## Limitaciones importantes
- **Estadísticas base históricas:** PokeAPI solo da las actuales. Algunos Pokémon tenían otras en 4.ª gen (p. ej. Pikachu, y el propio script de prueba usa los valores actuales). Cada sync lo avisa en `warnings`. Para corregirlas, añade overrides verificados en `data/gen4_stat_overrides.json`.
- La resolución de `past_values`/`past_types` asume que cada entrada vale *hasta* el grupo de versiones indicado (comprobado con el caso de Rayo en la prueba unitaria, pero confírmalo con datos reales tras el primer sync). Verifica también `EFECTIVIDAD_TIPOS` con una tabla de 4.ª gen (p. ej. Acero resiste Fantasma/Siniestro).
- El motor de combate es una **v1 limitada** (ver sección «Motor de combate»). Para desactivarlo, comenta `register_engine(MotorGen4())` en `main.py`: `/api/battles/simulate` volverá a responder 501.

## API (JSON; errores: `{"error":{"code","message","details"}}`)
| Método y ruta | Descripción |
|---|---|
| `GET /api/health[?deep=true]` | 200 `{"status":"ok","database":"ok","pokeapi":"not_checked"}` · 503 si falla la BD |
| `GET /api/pokedex?search=&type=fire&generation=4&sort=total&order=desc&page=1&page_size=24` | índice paginado de los Pokémon de la BD: `{"total":…,"page":…,"items":[{"id","name","types","generation","total"}]}` |
| `GET /api/catalogs` | tipos, generaciones y categorías de movimiento presentes en la BD + recuentos (alimenta los filtros) |
| `GET /api/pokemon?search=pika` (alias `q`) | `[{"id":25,"name":"pikachu"}]` |
| `GET /api/pokemon/25` | detalle (abajo); 404 si no está sincronizado |
| `GET /api/pokemon/25/moves` | movimientos de 4.ª gen que aprende y están en BD + `not_synced` |
| `GET /api/moves?search=thunder&limit=25` | movimientos de la versión `COMBAT_VERSION` |
| `GET /api/natures` | `[{"name":"Modesta","name_en":"modest","plus":3,"minus":1}]` (índices 1–5; 0 = neutra) |
| `POST /api/battles/preview` | valida y devuelve datos para el motor |
| `POST /api/battles/simulate` | llama al motor; 501 si no está conectado |
| `POST /api/sync/pokemon/{id}?include_moves=false` | requiere cabecera `X-API-Key`; 401/403 si falta o está deshabilitado |
| `POST /api/sync/catalogs` | tipos, versiones y efectividades; requiere `X-API-Key` |

```http
GET /api/pokemon/25
{"id":25,"name":"pikachu","height":4,"weight":60,"generation":1,"types":["electric"],
 "base":[35,55,40,50,50,90],"base_stats":{"hp":35,"attack":55,...},"abilities":[{"name":"static","slot":1,"hidden":false}],
 "sprites":{"front":"https://…/animated/25.gif","back":"https://…/back/25.gif","animated":true,"verified":true,"fallback":"https://…"}}

POST /api/battles/preview
{"ruleset":"gen4","strict_learnset":false,
 "user":{"pokemon_id":25,"level":50,"nature":"Modesta","iv":[31,31,31,31,31,31],"ev":[0,0,0,252,0,252],"moves":["thunderbolt"]},
 "rival":{"pokemon_id":7,"level":50,"nature":"Serena","iv":[31,31,31,31,31,31],"ev":[252,0,0,0,252,0],"moves":["surf"]}}
→ 200 {"valid":true,"ruleset":"gen4","version":"platinum","combatants":{"user":{"pokemon":{…},"level":50,"stats":[…],
   "max_hp":…,"moves":[{"name":"thunderbolt","type":"electric","category":"special","power":95,"accuracy":100,"pp":15,
   "stab":true,"effectiveness":2.0}]},"rival":{…}},"warnings":[],"engine":{"connected":false,"integration_point":"conector.register_engine()"}}
→ 422 {"error":{"code":"validation_error","message":"La configuración no es válida.","details":["Pokémon rival: el Pokémon 7 no está sincronizado."]}}
```
(Los valores numéricos del ejemplo son ilustrativos del formato, no resultados reales.) El backend recalcula las estadísticas con la fórmula de 4.ª gen y las usa en lugar de las del frontend.

## Frontend
`script.js` ya llama a `/api/pokemon?q=`, `/api/pokemon/{id}`, `/api/moves`, `/api/natures`, `/api/battles/preview` y `/api/battles/simulate` y muestra los errores de validación en el registro. Nota: los nombres de movimientos son los de la BD (slugs en inglés, p. ej. `thunderbolt`).

## Pruebas
- Unitarias y de API (no tocan datos reales): `pytest tests/test_unit.py tests/test_api.py`.
- Integración real: crea una **copia de prueba** de la BD con tu script, apunta `DB_*` a ella y ejecuta `TEST_DB_NAME=CalculadoraPokemonDB_Test pytest tests/test_integration_sqlserver.py`. Se omite si `TEST_DB_NAME` falta o es la BD real. Cubre conexión, credenciales/servidor incorrectos, `CHECK`/FK con rollback e idempotencia del sync (con `tests/fake_pokeapi.py`).

## Solución de problemas
- `No se pudo conectar…` (503): revisa `DB_SERVER`/instancia, que TCP/IP esté habilitado, el nombre del controlador y `DB_TRUST_SERVER_CERT=true` si usas certificado autofirmado en desarrollo. Los detalles (sin contraseñas) están en el log del servidor.
- `Login failed`: contraseña/usuario del `.env` o login sin usuario en la BD (¿ejecutaste `01_usuarios_app.sql`?).
- 404 en `/api/pokemon/{id}`: ese Pokémon aún no está sincronizado.
- 403 en sync: define `SYNC_API_KEY`; 401: cabecera `X-API-Key` incorrecta.
- 502: PokeAPI caída o con respuesta incompleta; se reintenta hasta 3 veces con espera.

## Motor de combate (`motor/`) — v1: ataques directos 1 contra 1
Se registra solo en `main.py`. `POST /api/battles/simulate` valida (igual que `preview`), simula y devuelve `{"events":[...]}`; el frontend los reproduce. Acepta `"seed": 123` (misma semilla = mismo combate).

**Qué implementa:** fórmula de daño de 4.ª gen, STAB, efectividad de tipos (desde `EFECTIVIDAD_TIPOS`), precisión, crítico (1/16, ×2), factor aleatorio 85–100, prioridad, orden por velocidad (empate al azar), PP, Forcejeo, retroceso y victoria/empate (límite de 200 turnos).
**Qué NO implementa (se avisa en el registro, no se simula):** habilidades, objetos, estados alterados, clima, cambios de estadísticas, efectos secundarios de los ataques, movimientos de estado, y los de `NO_SOPORTADOS` (varios golpes, dos turnos, daño fijo…). Un movimiento no soportado nunca se usa; si no queda ninguno, `preview` rechaza la configuración.
**Elección de movimiento:** el motor elige solo el de mayor daño esperado (`estrategia.py`); es una decisión de diseño, no una regla del juego.

| Quiero añadir… | Dónde |
|---|---|
| Un movimiento con lógica propia | `efectos.py` → `@especial("nombre")` (ejemplos: retroceso, Forcejeo) y quítalo de `NO_SOPORTADOS` en `datos.py` |
| Habilidades / objetos / estados / clima | `efectos.HOOKS` (hay un hook `fin_de_turno`; añade más puntos de enganche en `motor.py` donde la regla lo exija) |
| Prioridades de movimientos | `datos.PRIORIDAD` |
| Otra forma de elegir movimiento | `estrategia.py` |
| Cambiar la fórmula | `formulas.py` (+ actualiza `tests/test_motor.py`) |

**Verifícalo:** escribí la fórmula y las tablas de `datos.py` (prioridades, retrocesos, `NO_SOPORTADOS`) de memoria. Las pruebas comprueban que el código hace lo que dice la fórmula (cálculos a mano), **no** que la fórmula coincida con el juego. Compara varios casos con una calculadora de daño de 4.ª gen (p. ej. la de Smogon) antes de fiarte de los números.

## Índice de la base de datos (frontend)
Sección «Índice de la base de datos» bajo la arena, con tres pestañas que usan **solo tablas existentes**:
- **Pokémon** (`POKEMON`, `POKEMON_TIPOS`, `TIPOS`, `GENERACIONES`, `POKEMON_ESTADISTICAS`): búsqueda, filtro por tipo y generación, orden y paginación; botones «Tu Pokémon» / «Rival» cargan el elegido en el panel correspondiente.
- **Movimientos** (`MOVIMIENTO_VERSION`): filtros por tipo y categoría (físico/especial/estado); se filtra en el navegador sobre `/api/moves`.
- **Naturalezas**: **no existe tabla de naturalezas** en la BD; se leen de PokeAPI (`/api/natures`, con caché). Si quieres que vivan en SQL Server haría falta crear una tabla `NATURALEZAS`, lo que requiere tu autorización.
Si la BD está vacía, el índice lo dice y muestra el comando de sincronización. Sin backend (modo demostración) lista 1–493 desde PokeAPI sin tipos/generación/total.

## Errores típicos al arrancar (causa → solución)
| Síntoma | Causa | Solución |
|---|---|---|
| `ModuleNotFoundError: fastapi/uvicorn/pyodbc` | dependencias sin instalar o venv no activado | activa el venv y `pip install -r requirements.txt` |
| `TypeError: unsupported operand type(s) for |` al importar | Python < 3.10 | usa Python 3.10+ |
| `Address already in use` / `WinError 10048` | el puerto 8001 está ocupado | `python conector.py serve --port 8002` |
| `ModuleNotFoundError: main` | no estás en la carpeta `backend/` | `cd backend` antes de `python conector.py serve` |
| La API arranca pero `/api/health` da 503 | SQL Server inaccesible o credenciales mal | el backend arranca igualmente (no conecta al iniciar); mira el log y revisa `.env` |
| `Data source name not found` en el log | `DB_DRIVER` no coincide con el instalado | `python -c "import pyodbc;print(pyodbc.drivers())"` y copia el nombre exacto |
| La página dice «Demo» aunque el backend corre | el frontend no llega a `/api` (otro puerto) | usa `FRONTEND_DIR=../pokedmg`, o pon la URL en `<meta name="api-base">` y añade el origen a `CORS_ORIGINS` |
Comprobación rápida: `python -c "import main"` (importa todo sin abrir puerto) y, con el servidor en marcha, `curl http://127.0.0.1:8001/api/health`.
