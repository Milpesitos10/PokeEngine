# Calculadora de Daño Pokémon — Frontend

Interfaz estática (HTML + CSS + JS sin dependencias). Estética Diamante/Perla/Platino con sprites animados de 5.ª generación (Negro/Blanco) del repositorio público PokeAPI/sprites.

## Ejecutar
```
cd pokedmg
python -m http.server 8000
```
Abrir http://localhost:8000 (requiere internet para los GIF). Sin backend en `/api` la página entra en **modo demostración** (insignia amarilla): 5 Pokémon y 8 movimientos de ejemplo con datos reales de 4.ª generación.

## Qué funciona ya
Búsqueda (nombre/nº), nivel, 25 naturalezas, tabla Base/IV/EV/Total con fórmulas de 4.ª gen y validaciones (IV 0–31, EV 0–252, suma ≤ 510), 4 movimientos validados contra los datos, arena con HUD y barras de PS, animaciones (embestida, impacto, daño, debilitamiento), registro, pausa/reanudar/reiniciar, bloqueo de paneles en combate, contraer paneles y `prefers-reduced-motion`.

## Contrato con el backend (pendiente)
| Endpoint | Respuesta |
|---|---|
| `GET /api/pokemon?q=` | `[{id,name}]` |
| `GET /api/pokemon/{id}` | `{id,name,types:['fire'],base:[ps,atq,def,atesp,defesp,vel],sprites:{front,back}}` |
| `GET /api/moves` | `[{name,type,category,power,accuracy,pp}]` |
| `GET /api/natures` | `[{name,plus,minus}]` (índices 1–5; 0 = neutra) |
| `POST /api/battle/simulate` | `{events:[…]}` |

Eventos: `{type:'log',text}` o `{type:'move',actor:'user'|'rival',text,hit,status,hp:{user,rival},extra:[],fainted}`. La interfaz **solo reproduce** estos eventos; el daño, orden, precisión y críticos los decide el motor de 4.ª gen. Todo el acceso a datos está en el objeto `data` de `script.js`. Sin credenciales de SQL Server en el frontend.

## Pendiente / simulado
- Motor de combate: no incluido. El botón «Vista previa de animaciones (demo)» usa porcentajes ilustrativos y lo indica en el registro.
- Animaciones específicas por movimiento: solo hay efectos genéricos (ataque/estado).
