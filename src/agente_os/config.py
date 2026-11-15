"""Configuración del servicio leída de variables de entorno."""

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _int(nombre: str, defecto: int) -> int:
    try:
        return int(os.getenv(nombre, defecto))
    except ValueError:
        return defecto


@dataclass(frozen=True)
class Config:
    dir_modelos: Path = field(default_factory=lambda: Path(os.getenv("MODEL_DIR", RAIZ / "models")))
    ruta_bitacora: Path | None = field(default_factory=lambda: Path(os.environ["LEDGER_PATH"]) if os.getenv("LEDGER_PATH") else None)
    modo_planificador: str = field(default_factory=lambda: os.getenv("PLANNER_MODE", "simulado"))  # simulado | claude | determinista
    factor_tiempo: float = field(default_factory=lambda: float(os.getenv("SIM_TIME_FACTOR", "1.0")))
    api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "").strip())
    token_agente: str = field(default_factory=lambda: os.getenv("AGENT_TOKEN", "").strip())
    revision: str = field(default_factory=lambda: os.getenv("REVISION", "local"))
    max_tarea: int = field(default_factory=lambda: _int("MAX_TASK_CHARS", 2000))
    max_pantalla: int = field(default_factory=lambda: _int("MAX_SCREEN_CHARS", 20000))
    max_imagen: int = field(default_factory=lambda: _int("MAX_IMAGE_BYTES", 5 * 1024 * 1024))
    ttl_cache_s: int = field(default_factory=lambda: _int("PLAN_CACHE_TTL_S", 3600))
    largo_tarea_media: int = field(default_factory=lambda: _int("ROUTER_TASK_LEN_MEDIUM", 70))
    excluir_participios: bool = field(default_factory=lambda: os.getenv("ROUTER_IGNORE_PARTICIPLES", "0") == "1")
    # Emulación de revisiones anteriores y pruebas de rollback (solo GitOps local y simulación):
    modelo_fijo: str = field(default_factory=lambda: os.getenv("ROUTER_FIXED_MODEL", ""))      # p. ej. claude-opus-5-5 (Fase II)
    cache_planes: bool = field(default_factory=lambda: os.getenv("PLAN_CACHE", "1") == "1")
    tasa_falla_simulada: float = field(default_factory=lambda: float(os.getenv("SIM_FAIL_RATE", "0")))


def cargar() -> Config:
    return Config()
