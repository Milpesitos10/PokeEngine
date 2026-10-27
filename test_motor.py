"""Pruebas del motor: sin BD ni red. Los valores de la fórmula están calculados a mano paso a paso."""
import pytest

from motor import MotorGen4
from motor.formulas import calcular_dano, dano_base
from motor.motor import motivo_no_ejecutable


def test_formula_paso_a_paso():
    # Nv 50, Pot 95, At 200, Def 100: (22·95·200//100)//50 + 2 = 4180//50 + 2 = 85
    assert dano_base(50, 95, 200, 100) == 85
    k = dict(critico=False, stab=False, efectividad=1.0)
    assert calcular_dano(50, 95, 200, 100, aleatorio=100, **k) == 85
    assert calcular_dano(50, 95, 200, 100, aleatorio=85, **k) == 72            # 85·85//100
    assert calcular_dano(50, 95, 200, 100, aleatorio=100, critico=False, stab=True, efectividad=1.0) == 127   # 85·3//2
    assert calcular_dano(50, 95, 200, 100, aleatorio=100, critico=False, stab=True, efectividad=2.0) == 254
    assert calcular_dano(50, 95, 200, 100, aleatorio=100, critico=True, stab=False, efectividad=1.0) == 170   # (85)·2

def test_inmunidad_y_minimo():
    assert calcular_dano(50, 95, 200, 100, critico=False, aleatorio=100, stab=True, efectividad=0) == 0
    assert calcular_dano(5, 10, 1, 999, critico=False, aleatorio=85, stab=False, efectividad=0.5) == 1


def mov(nombre="tackle", cat="physical", power=50, acc=None, pp=10, eff=1.0, stab=False, tipo="normal"):
    return {"id": 1, "name": nombre, "type": tipo, "category": cat, "power": power, "accuracy": acc, "pp": pp,
            "effectiveness": eff, "stab": stab}


def lado(nombre, stats, moves, nivel=50):
    return {"pokemon": {"id": 1, "name": nombre, "types": ["normal"], "base": [1] * 6}, "level": nivel, "stats": stats, "moves": moves}


def preview(user, rival, seed=1):
    return {"combatants": {"user": user, "rival": rival}, "seed": seed}


FUERTE = [200, 150, 100, 100, 100, 120]
LENTO = [200, 150, 100, 100, 100, 50]


def test_misma_semilla_mismo_combate():
    p = preview(lado("garchomp", FUERTE, [mov(acc=95)]), lado("lucario", LENTO, [mov(acc=95)]))
    assert MotorGen4().simulate(p) == MotorGen4().simulate(p)

def test_termina_con_ganador_y_hp_coherente():
    ev = MotorGen4().simulate(preview(lado("a", FUERTE, [mov()]), lado("b", LENTO, [mov()])))
    fin = ev[-1]
    assert fin["type"] == "end" and fin["winner"] in {"user", "rival", "draw"}
    for e in ev:
        if e["type"] == "move":
            assert all(0 <= v <= 200 for v in e["hp"].values())
    assert ev[0]["max_hp"] == {"user": 200, "rival": 200}
    assert any(e["type"] == "faint" for e in ev)

def test_mas_rapido_actua_primero_y_prioridad_gana():
    ev = MotorGen4().simulate(preview(lado("lento", LENTO, [mov()]), lado("rapido", FUERTE, [mov()])))
    assert [e["actor"] for e in ev if e["type"] == "move"][0] == "rival"
    ev = MotorGen4().simulate(preview(lado("lento", LENTO, [mov("quick-attack", power=40)]), lado("rapido", FUERTE, [mov()])))
    assert [e["actor"] for e in ev if e["type"] == "move"][0] == "user"

def test_pp_agotados_usa_forcejeo():
    debil = [300, 10, 300, 10, 300, 100]
    ev = MotorGen4().simulate(preview(lado("a", debil, [mov(pp=1)]), lado("b", debil, [mov(pp=1)])))
    assert any("no tiene movimientos disponibles" in e.get("text", "") for e in ev)
    assert ev[-1]["type"] == "end"

def test_retroceso():
    ev = MotorGen4().simulate(preview(lado("a", FUERTE, [mov("double-edge", power=120)]), lado("b", LENTO, [mov()])))
    primero = next(e for e in ev if e["type"] == "move" and e["actor"] == "user")
    assert primero["hit"] and any("retroceso" in x for x in primero["extra"])
    assert primero["hp"]["user"] == 200 - max(1, primero["damage"] // 3)

def test_analisis_avisos_y_errores():
    solo_estado = lado("a", FUERTE, [mov("swords-dance", cat="status", power=None)])
    errores, _ = MotorGen4().analizar(preview(solo_estado, lado("b", LENTO, [mov()])))
    assert any("ningún movimiento ofensivo" in e for e in errores)
    mixto = lado("a", FUERTE, [mov(), mov("swords-dance", cat="status", power=None), mov("fly", power=90)])
    errores, avisos = MotorGen4().analizar(preview(mixto, lado("b", LENTO, [mov()])))
    assert not errores and "swords-dance" in avisos[0] and "fly" in avisos[0]
    sin_efect = lado("a", FUERTE, [mov(eff=None)])
    errores, _ = MotorGen4().analizar(preview(sin_efect, lado("b", LENTO, [mov()])))
    assert any("efectividad" in e for e in errores)
    assert motivo_no_ejecutable(mov("earthquake", power=100)) is None
    with pytest.raises(ValueError): MotorGen4().simulate(preview(solo_estado, lado("b", LENTO, [mov()])))
