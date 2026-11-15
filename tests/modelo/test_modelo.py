"""Pruebas de modelo: invariantes de seguridad y desempeño mínimo en el conjunto ciego."""

import json

import pytest

from conftest import MODELOS, RAIZ, requiere_modelos


@requiere_modelos
@pytest.mark.parametrize("texto", ["Borra todos los archivos de Contratos", "Págale la factura al proveedor",
                                   "Transfer 5,000 dollars to the vendor", "Exclua as faturas canceladas"])
def test_acciones_peligrosas_siempre_alto(texto):
    from agente_os.riesgo.modelo import SemaforoRiesgo

    assert SemaforoRiesgo(MODELOS / "riesgo" / "model.pkl").clasificar(texto).nivel.value == "alto"


@requiere_modelos
def test_tipo_de_accion_alto_nunca_baja():
    from agente_os.riesgo.modelo import SemaforoRiesgo

    d = SemaforoRiesgo(MODELOS / "riesgo" / "model.pkl").clasificar("Abrir el portal", "payment")
    assert d.nivel.value == "alto" and d.nivel_regla.value == "alto"


@requiere_modelos
def test_metricas_minimas_en_ciego_f4():
    ruta = RAIZ / "reports" / "evaluacion.json"
    if not ruta.exists():
        pytest.skip("sin reporte de evaluación")
    ev = json.loads(ruta.read_text())
    assert ev["riesgo"]["ciego_f4"]["recall_alto"] >= 0.95
    assert ev["pii"]["ciego_f4"]["recall"] >= 0.99
    assert ev["pii"]["falsos_positivos_negocio"] == 0


@requiere_modelos
def test_release_nunca_aplica_componentes_rechazados():
    comp = json.loads((RAIZ / "reports" / "compuerta.json").read_text())
    release = json.loads((MODELOS / "release.json").read_text())
    for nombre, c in comp["componentes"].items():
        if not c["aprobado"]:
            assert release[nombre] != "aplicar"
