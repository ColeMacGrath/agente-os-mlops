"""Router de modelos, cálculo de costos y bitácora encadenada."""

import json

from agente_os.auditoria.bitacora import Bitacora, verificar
from agente_os.router.costos import Consumo
from agente_os.router.router import Router


def test_router_por_complejidad():
    r = Router()
    assert r.decidir("Copia el total", "Total: $10", False).modelo == "claude-haiku-5-5"
    assert r.decidir("Resume el correo y prepara un borrador", "texto", False).modelo == "claude-sonnet-5-5"
    assert r.decidir("Analiza la orden, compárala con el presupuesto y después envía el resumen", "x", False).modelo == "claude-opus-5-5"


def test_politica_ocr_primero():
    r = Router()
    assert r.decidir("Copia el folio", "Folio A-22 del pedido de compra pendiente de pago", True).enviar_imagen is False
    assert r.decidir("Copia el folio", "", True).enviar_imagen is True


def test_umbral_de_largo_configurable():
    tarea = "Copia el número de pedido que aparece en la parte superior de la ventana del ERP"
    assert Router(largo_tarea_media=70).decidir(tarea, "x", False).complejidad == "media"
    assert Router(largo_tarea_media=120).decidir(tarea, "x", False).complejidad == "simple"


def test_costo_con_cache_y_batch():
    c = Consumo("claude-sonnet-5-5", 1000, 2500, 0, 500, 1.0)
    esperado = (1000 * 2.0 + 2500 * 0.10 + 500 * 10.0) / 1e6
    assert abs(c.costo_usd - esperado) < 1e-12
    c.batch = True
    assert abs(c.costo_usd - esperado / 2) < 1e-12


def test_bitacora_detecta_alteraciones(tmp_path):
    ruta = tmp_path / "b.jsonl"
    b = Bitacora(ruta)
    for i in range(5):
        b.registrar("analyze", {"i": i})
    assert verificar(ruta)["integra"] and verificar(ruta)["entradas"] == 5
    lineas = ruta.read_text().splitlines()
    e = json.loads(lineas[2])
    e["datos"]["i"] = 99
    lineas[2] = json.dumps(e, ensure_ascii=False)
    ruta.write_text("\n".join(lineas) + "\n")
    r = verificar(ruta)
    assert not r["integra"] and r["rota_en_linea"] == 3


def test_bitacora_continua_la_cadena_al_reabrir(tmp_path):
    ruta = tmp_path / "b.jsonl"
    Bitacora(ruta).registrar("a", {})
    Bitacora(ruta).registrar("b", {})
    assert verificar(ruta)["entradas"] == 2


def test_bitacora_con_dos_escritores_intercalados(tmp_path):
    """Regresión: dos instancias escribiendo en el mismo archivo no deben romper la cadena."""
    ruta = tmp_path / "b.jsonl"
    a, b = Bitacora(ruta), Bitacora(ruta)
    for i in range(10):
        (a if i % 3 else b).registrar("evento", {"i": i})
    r = verificar(ruta)
    assert r["integra"] and r["entradas"] == 10
