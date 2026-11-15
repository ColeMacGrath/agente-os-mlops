"""Lógica GitOps: propuesta de canary, promoción y prueba estadística de latencia."""
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "gitops"))

from actualizar_release import aprobada_de, con_canary  # noqa: E402
from analisis_canary import mas_lento  # noqa: E402

ESTABLE = {"nombre": "r-1", "imagen": "img:1", "trafico": 100}
NUEVA = {"nombre": "r-2", "imagen": "img:2"}


def test_nueva_revision_entra_como_canary_frente_a_la_estable():
    revs = con_canary({"revisiones": [ESTABLE]}, NUEVA, 10)
    assert [(r["nombre"], r["trafico"], r.get("canary", False)) for r in revs] == [("r-1", 90, False), ("r-2", 10, True)]


def test_sin_estable_o_misma_revision_queda_al_100():
    assert con_canary({"revisiones": []}, NUEVA, 10) == [dict(NUEVA, trafico=100)]
    assert con_canary({"revisiones": [ESTABLE]}, dict(NUEVA, nombre="r-1"), 10)[0]["trafico"] == 100


def test_se_promueve_la_canary_sin_la_marca():
    release = {"revisiones": [dict(ESTABLE, trafico=90), dict(NUEVA, trafico=10, canary=True)]}
    assert aprobada_de(release) == dict(NUEVA, trafico=10)
    assert aprobada_de({"revisiones": [ESTABLE]})["nombre"] == "r-1"


def test_mann_whitney_no_ve_diferencia_entre_revisiones_identicas():
    rng = random.Random(1)
    a = [rng.lognormvariate(1.4, 0.5) for _ in range(150)]
    b = [rng.lognormvariate(1.4, 0.5) for _ in range(150)]
    assert not mas_lento(a, b, 0.01, 1.05)[0]


def test_mann_whitney_detecta_un_canary_30_por_ciento_mas_lento():
    rng = random.Random(2)
    a = [rng.lognormvariate(1.4, 0.5) for _ in range(150)]
    b = [1.3 * rng.lognormvariate(1.4, 0.5) for _ in range(150)]
    assert mas_lento(a, b, 0.01, 1.05)[0]
