"""Proxy local con reparto de tráfico por pesos (emula el traffic split de Cloud Run).

Lee las rutas de gitops/estado/<entorno>_rutas.json en cada solicitud (recarga en
caliente al cambiar el archivo) y agrega la cabecera x-revision a la respuesta.
Uso: uvicorn proxy:app --port 8200  (con la variable GITOPS_RUTAS=ruta al JSON)
"""

import json
import os
import random
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response

RUTAS = Path(os.environ.get("GITOPS_RUTAS", "estado/rutas.json"))
app = FastAPI(title="Proxy GitOps local")
_cache = {"mtime": 0.0, "rutas": {}}
_cliente = httpx.AsyncClient(timeout=120)


def rutas() -> dict:
    m = RUTAS.stat().st_mtime
    if m != _cache["mtime"]:
        _cache.update(mtime=m, rutas=json.loads(RUTAS.read_text()))
    return _cache["rutas"]


@app.api_route("/{ruta:path}", methods=["GET", "POST"])
async def reenviar(ruta: str, request: Request) -> Response:
    r = {k: v for k, v in rutas().items() if v["peso"] > 0}
    revision = random.choices(list(r), weights=[v["peso"] for v in r.values()])[0]
    up = await _cliente.request(request.method, f"{r[revision]['url']}/{ruta}", content=await request.body(),
                                headers={"content-type": request.headers.get("content-type", "application/json")})
    return Response(up.content, status_code=up.status_code, media_type=up.headers.get("content-type"),
                    headers={"x-revision": revision})
