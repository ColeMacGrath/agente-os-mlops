"""Configuración común de pytest.

Las pruebas usan el planificador simulado sin espera (SIM_TIME_FACTOR=0), sin
llave de API y sin token, para ser reproducibles y gratuitas. Las pruebas que
necesitan modelos entrenados se omiten si no existe models/ (correr `dvc repro`).
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
os.environ.setdefault("PLANNER_MODE", "simulado")
os.environ.setdefault("SIM_TIME_FACTOR", "0")
os.environ["AGENT_TOKEN"] = ""

import pytest  # noqa: E402

MODELOS = RAIZ / "models"
HAY_MODELOS = (MODELOS / "riesgo" / "model.pkl").exists() and (MODELOS / "inyeccion" / "model.pkl").exists()
requiere_modelos = pytest.mark.skipif(not HAY_MODELOS, reason="sin modelos entrenados: ejecutar `dvc repro`")


@pytest.fixture
def cliente(tmp_path):
    from fastapi.testclient import TestClient

    from agente_os.api.app import crear_app
    from agente_os.config import Config

    cfg = Config(dir_modelos=MODELOS, ruta_bitacora=tmp_path / "bitacora.jsonl", modo_planificador="simulado", factor_tiempo=0.0)
    with TestClient(crear_app(cfg)) as c:
        c.cfg = cfg
        yield c
