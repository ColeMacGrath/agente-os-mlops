"""Bitácora de auditoría append-only con hashes SHA-256 encadenados.

Cada entrada guarda solo metadatos (nunca el contenido de la tarea ni de la
pantalla): evento, identificador, versiones de código y modelos, ruta del
router, decisión y motivos. Cada hash incluye el hash anterior, de modo que
alterar o borrar una entrada rompe la cadena y la verificación lo detecta.
Extiende el Libro Mayor de la Fase II con lo que pidió la auditoría técnica de
la Actividad 9 (hallazgo A6): modelo de lenguaje, ruta y versión de reglas.
"""

import fcntl
import hashlib
import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path

GENESIS = "0" * 64


def _hash(registro: dict) -> str:
    return hashlib.sha256(json.dumps(registro, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _ultima_entrada(f) -> dict | None:
    """Lee la última línea del archivo sin cargarlo completo."""
    f.seek(0, os.SEEK_END)
    fin = f.tell()
    if fin == 0:
        return None
    pos, bloque = fin, b""
    while pos > 0:
        paso = min(4096, pos)
        pos -= paso
        f.seek(pos)
        bloque = f.read(paso) + bloque
        lineas = [x for x in bloque.split(b"\n") if x.strip()]
        if len(lineas) >= 2 or pos == 0:
            return json.loads(lineas[-1]) if lineas else None
    return None


class Bitacora:
    """Varias instancias o procesos pueden escribir en el mismo archivo: cada escritura
    toma un bloqueo exclusivo y encadena con la última entrada del archivo, no con un
    valor en memoria (la auditoría encontró que dos escritores rompían la cadena)."""

    def __init__(self, ruta: Path | None):
        self.ruta = Path(ruta) if ruta else None
        self._lock = threading.Lock()
        self._ultimo, self._n = GENESIS, 0  # solo para el modo sin archivo

    def registrar(self, evento: str, datos: dict, ts: str | None = None) -> dict:
        with self._lock:
            entrada = {"ts": ts or datetime.now(UTC).isoformat(timespec="milliseconds"), "evento": evento, "datos": datos}
            if not self.ruta:
                entrada = {"n": self._n + 1, **entrada, "hash_anterior": self._ultimo}
                entrada["hash"] = _hash(entrada)
                self._ultimo, self._n = entrada["hash"], entrada["n"]
                return entrada
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            with open(self.ruta, "a+b") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    previa = _ultima_entrada(f)
                    entrada = {"n": (previa["n"] if previa else 0) + 1, **entrada, "hash_anterior": previa["hash"] if previa else GENESIS}
                    entrada["hash"] = _hash(entrada)
                    f.seek(0, os.SEEK_END)
                    f.write((json.dumps(entrada, ensure_ascii=False) + "\n").encode())
                    f.flush()
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
            return entrada


def verificar(ruta: Path) -> dict:
    """Recalcula la cadena completa. Devuelve el resultado y la primera entrada rota, si existe."""
    anterior, n = GENESIS, 0
    for i, linea in enumerate(Path(ruta).read_text().splitlines(), start=1):
        if not linea.strip():
            continue
        e = json.loads(linea)
        esperado = _hash({k: v for k, v in e.items() if k != "hash"})
        if e["hash_anterior"] != anterior or e["hash"] != esperado or e["n"] != n + 1:
            return {"integra": False, "entradas": n, "rota_en_linea": i}
        anterior, n = e["hash"], e["n"]
    return {"integra": True, "entradas": n, "rota_en_linea": None, "hash_final": anterior}
