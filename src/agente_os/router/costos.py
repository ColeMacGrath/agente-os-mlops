"""Precios, latencia de referencia y cálculo del costo por llamada.

Precios de lista de la API de Claude (USD por millón de tokens). Lectura de
caché: 0.05x en Opus 5.5 y Sonnet 5.5; 0.1x en Haiku 5.5 (supuesto conservador).
Escritura de caché con TTL de 5 minutos: 1.25x. Batch API: 50% de descuento.
"""

from dataclasses import dataclass

PRECIOS = {
    "claude-opus-5-5": {"in": 4.00, "out": 20.00, "cache_read": 0.20},
    "claude-sonnet-5-5": {"in": 2.00, "out": 10.00, "cache_read": 0.10},
    "claude-haiku-5-5": {"in": 0.10, "out": 0.50, "cache_read": 0.01},
}
FACTOR_ESCRITURA_CACHE = 1.25
DESCUENTO_BATCH = 0.50

# Supuestos de la simulación (Actividad 9): TTFT y velocidad de salida por modelo.
LATENCIA = {
    "claude-opus-5-5": {"ttft_s": 1.5, "tok_s": 70.0},
    "claude-sonnet-5-5": {"ttft_s": 0.8, "tok_s": 110.0},
    "claude-haiku-5-5": {"ttft_s": 0.4, "tok_s": 200.0},
}
TOKENS_SALIDA = {"claude-opus-5-5": 600, "claude-sonnet-5-5": 520, "claude-haiku-5-5": 420}


@dataclass
class Consumo:
    modelo: str
    tokens_entrada: int
    tokens_cache_lectura: int
    tokens_cache_escritura: int
    tokens_salida: int
    latencia_modelo_s: float
    batch: bool = False

    @property
    def costo_usd(self) -> float:
        p = PRECIOS[self.modelo]
        c = (self.tokens_entrada * p["in"] + self.tokens_cache_lectura * p["cache_read"]
             + self.tokens_cache_escritura * p["in"] * FACTOR_ESCRITURA_CACHE + self.tokens_salida * p["out"]) / 1_000_000
        return c * (1 - DESCUENTO_BATCH) if self.batch else c
