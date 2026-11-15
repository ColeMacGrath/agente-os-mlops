"""Despliegue progresivo con análisis de canary y rollback automático.

1. El reconciliador aplica el release del entorno (estable + canary).
2. Se envía tráfico por el proxy y se mide cada revisión: tasa de error,
   latencia p95 (en segundos de modelo), costo por tarea y tasa de bloqueo.
3. Si el canary cumple los criterios, se edita el release (siguiente paso de
   tráfico) como lo haría un pull request y se vuelve a reconciliar. Si falla,
   el release regresa el 100% del tráfico a la estable (rollback).

Cada decisión queda en la bitácora de auditoría y en gitops/historial.md, que
emula el historial de commits del repositorio de despliegue.

Uso: python gitops/analisis_canary.py --entorno produccion
     python gitops/analisis_canary.py --entorno staging --canary-defectuoso   (prueba de rollback)
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "gitops"))
sys.path.insert(0, str(RAIZ / "operacion"))

from carga import generar  # noqa: E402
from reconciliador import ESTADO, PUERTOS, Bitacora, actual, detener, reconciliar  # noqa: E402

FACTOR = 0.05  # 1 s de modelo = 50 ms reales: la latencia se reporta en segundos de modelo


def commit(entorno: str, mensaje: str, release: dict, bitacora: Bitacora) -> None:
    ruta = RAIZ / "deploy" / "entornos" / entorno / "release.yaml"
    cabecera = "# Estado deseado del entorno. Fuente de verdad del despliegue (GitOps):\n# solo se modifica mediante pull request y el reconciliador lo aplica.\n"
    ruta.write_text(cabecera + yaml.safe_dump(release, allow_unicode=True, sort_keys=False))
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(RAIZ / "gitops" / "historial.md", "a", encoding="utf-8") as f:
        f.write(f"- `{ts}` **deploy/{entorno}**: {mensaje}\n")
    bitacora.registrar("commit_gitops", {"entorno": entorno, "mensaje": mensaje,
                                         "trafico": {r["nombre"]: r["trafico"] for r in release["revisiones"]}})
    print(f"[gitops] commit deploy/{entorno}: {mensaje}")


async def trafico(url: str, n: int, offset: int, semilla: int = 31) -> list[dict]:
    solicitudes = generar(n + offset, semilla=semilla)[offset:]
    out, sem = [], asyncio.Semaphore(20)
    async with httpx.AsyncClient(timeout=60) as c:
        async def una(r):
            async with sem:
                cuerpo = {k: v for k, v in r.items() if not k.startswith("_")}
                t0 = time.perf_counter()
                resp = await c.post(f"{url}/v1/analyze", json=cuerpo)
                lat = (time.perf_counter() - t0) / FACTOR
                datos = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                out.append({"revision": resp.headers.get("x-revision"), "codigo": resp.status_code, "latencia_s": lat,
                            "costo": datos.get("costo_usd", 0.0), "bloqueado": datos.get("blocked", False)})
        await asyncio.gather(*(una(r) for r in solicitudes))
    return out


def resumen(filas: list[dict]) -> dict:
    if not filas:
        return {"n": 0}
    ok = [f for f in filas if f["codigo"] == 200]
    lat = sorted(f["latencia_s"] for f in ok) or [0]
    return {"n": len(filas), "tasa_error": round(1 - len(ok) / len(filas), 4), "latencia_p95_s": round(lat[int(0.95 * (len(lat) - 1))], 2),
            "latencia_p50_s": round(statistics.median(lat), 2), "costo_por_tarea": round(sum(f["costo"] for f in ok) / max(len(ok), 1), 6),
            "tasa_bloqueo": round(sum(f["bloqueado"] for f in ok) / max(len(ok), 1), 4)}


def pareado(entorno: str, estable: str, canary: str, n: int, offset: int) -> tuple[dict, dict]:
    """Mismas tareas a las dos revisiones (directo, sin proxy): costo y latencia comparables.

    Con el tráfico repartido cada revisión recibe tareas distintas y, como el costo y la
    latencia dependen de la complejidad (Haiku, Sonnet u Opus), muestras chicas difieren
    por azar aunque el código sea idéntico. La tasa de error sí se mide con el tráfico real.
    """
    urls = actual(entorno)["revisiones"]
    fe = asyncio.run(trafico(urls[estable]["url"], n, offset, semilla=47))
    fc = asyncio.run(trafico(urls[canary]["url"], n, offset, semilla=47))
    est, can = resumen(fe), resumen(fc)
    est["latencias"] = [round(f["latencia_s"], 3) for f in fe if f["codigo"] == 200]
    can["latencias"] = [round(f["latencia_s"], 3) for f in fc if f["codigo"] == 200]
    return est, can


def mas_lento(est: list[float], can: list[float], alfa: float, factor: float) -> tuple[bool, str]:
    """Prueba de Mann-Whitney (una cola): el canary es más lento solo si la diferencia es
    significativa y su mediana supera a la estable en más del factor tolerado."""
    from scipy.stats import mannwhitneyu
    p = mannwhitneyu(can, est, alternative="greater").pvalue
    me, mc = statistics.median(est), statistics.median(can)
    return (p < alfa and mc > me * factor), f"mediana {mc:.2f} vs {me:.2f} s, p={p:.3f}"


def evaluar(est: dict, can: dict, c: dict, par: tuple[dict, dict] | None = None) -> list[tuple[str, bool, str]]:
    lento = None
    if par:   # costo, latencia y bloqueo con las mismas tareas en ambas revisiones
        pe, pc = par
        est = dict(est, costo_por_tarea=pe["costo_por_tarea"], tasa_bloqueo=pe["tasa_bloqueo"])
        can = dict(can, costo_por_tarea=pc["costo_por_tarea"], tasa_bloqueo=pc["tasa_bloqueo"])
        if pe.get("latencias") and pc.get("latencias"):
            lento = mas_lento(pe["latencias"], pc["latencias"], c["latencia_alfa"], c["latencia_mediana_factor_max"])
    relativo = (("latencia frente a estable (Mann-Whitney)", not lento[0], lento[1]) if lento else
                ("latencia p95 frente a estable", can["latencia_p95_s"] <= est["latencia_p95_s"] * c["latencia_p95_factor_max"],
                 f"{can['latencia_p95_s']} vs {est['latencia_p95_s']} s"))
    return [
        ("tasa de error", can["tasa_error"] <= min(c["tasa_error_max"], est["tasa_error"] + c["tasa_error_margen"]), f"{can['tasa_error']:.3f} vs {est['tasa_error']:.3f}"),
        ("latencia p95 dentro del SLA", can["latencia_p95_s"] <= c["latencia_p95_s_max"], f"{can['latencia_p95_s']} s"),
        relativo,
        ("costo por tarea", can["costo_por_tarea"] <= est["costo_por_tarea"] * c["costo_por_tarea_factor_max"], f"${can['costo_por_tarea']:.5f} vs ${est['costo_por_tarea']:.5f}"),
        ("bloqueo de inyección", can["tasa_bloqueo"] >= est["tasa_bloqueo"] - c["bloqueo_inyeccion_margen"], f"{can['tasa_bloqueo']:.3f} vs {est['tasa_bloqueo']:.3f}"),
    ]


def main(entorno: str, defectuoso: bool) -> int:
    cfg = yaml.safe_load((RAIZ / "gitops" / "criterios_canary.yaml").read_text())
    bitacora = Bitacora(ESTADO / "bitacora_despliegues.jsonl")
    ruta = RAIZ / "deploy" / "entornos" / entorno / "release.yaml"
    release = yaml.safe_load(ruta.read_text())
    if defectuoso:
        release["revisiones"] = [dict(release["revisiones"][0], trafico=90), {
            "nombre": "r-3-1-1-defectuosa", "descripcion": "Prueba de rollback: revisión con 15% de errores inyectados",
            "imagen": "ghcr.io/colemacgrath/agente-os-cloud:3.1.1", "modelos": release["revisiones"][0]["modelos"],
            "entorno": {"SIM_FAIL_RATE": "0.15"}, "trafico": 10, "canary": True}]
        commit(entorno, "desplegar canary r-3-1-1-defectuosa al 10% (prueba de rollback)", release, bitacora)
    estable = next(r for r in release["revisiones"] if not r.get("canary"))
    canary = next((r for r in release["revisiones"] if r.get("canary")), None)
    if canary is None:
        return verificar(entorno, estable, cfg, bitacora)
    informe = {"entorno": entorno, "estable": estable["nombre"], "canary": canary["nombre"], "pasos": []}
    url = f"http://127.0.0.1:{PUERTOS[entorno]}"
    offset = 0
    try:
        reconciliar(entorno, FACTOR, bitacora)
        for _paso in cfg["pasos"]:
            filas = asyncio.run(trafico(url, cfg["solicitudes_por_paso"], offset))
            offset += cfg["solicitudes_por_paso"]
            est = resumen([f for f in filas if f["revision"] == estable["nombre"]])
            can = resumen([f for f in filas if f["revision"] == canary["nombre"]])
            par = None
            if est["n"] == 0:  # al 100% ya no queda tráfico en la estable: se compara contra el paso anterior
                est = informe["pasos"][-1]["estable"]
                par = informe["pasos"][-1].get("pareado")
                par = (par["estable"], par["canary"]) if par else None
            elif can["n"]:
                par = pareado(entorno, estable["nombre"], canary["nombre"], cfg.get("solicitudes_pareadas", 150), offset)
            checks = evaluar(est, can, cfg["criterios"], par) if can["n"] else []
            checks.append(("muestra mínima", can["n"] >= cfg["min_solicitudes_canary"], f"n={can['n']}"))
            ok = all(c[1] for c in checks)
            informe["pasos"].append({"trafico_canary": canary["trafico"], "estable": est, "canary": can,
                                     "pareado": {"estable": par[0], "canary": par[1]} if par else None,
                                     "criterios": [{"criterio": c[0], "ok": c[1], "detalle": c[2]} for c in checks], "aprobado": ok})
            print(f"[canary:{entorno}] paso {canary['trafico']}% · estable {est} · canary {can}")
            if par:
                print(f"    pareado ({par[0]['n']} tareas iguales): estable p95 {par[0]['latencia_p95_s']} s, ${par[0]['costo_por_tarea']:.5f} · canary p95 {par[1]['latencia_p95_s']} s, ${par[1]['costo_por_tarea']:.5f}")
            for c in checks:
                print(f"    {'OK   ' if c[1] else 'FALLA'} {c[0]}: {c[2]}")
            if not ok:
                release["revisiones"] = [dict(estable, trafico=100)]
                commit(entorno, f"rollback: {canary['nombre']} no cumplió el análisis al {canary['trafico']}% ({', '.join(c[0] for c in checks if not c[1])})",
                       release, bitacora)
                reconciliar(entorno, FACTOR, bitacora)
                informe["decision"] = "rollback"
                break
            siguiente = next((p for p in cfg["pasos"] if p > canary["trafico"]), None)
            if siguiente is None:
                canary = {k: v for k, v in canary.items() if k != "canary"}
                release["revisiones"] = [dict(canary, trafico=100)]
                commit(entorno, f"promover {canary['nombre']} al 100% y retirar {estable['nombre']} (canary aprobado en todos los pasos)", release, bitacora)
                reconciliar(entorno, FACTOR, bitacora)
                informe["decision"] = "promovido"
                break
            canary["trafico"], estable["trafico"] = siguiente, 100 - siguiente
            release["revisiones"] = [estable, canary]
            commit(entorno, f"avanzar canary {canary['nombre']} al {siguiente}%", release, bitacora)
            reconciliar(entorno, FACTOR, bitacora)
    finally:
        detener(entorno)
    salida = RAIZ / "reports" / f"canary_{entorno}{'_rollback' if defectuoso else ''}.json"
    salida.write_text(json.dumps(informe, indent=2, ensure_ascii=False))
    print(f"[canary:{entorno}] decisión: {informe.get('decision')}")
    # un rollback real deja el despliegue en rojo; en la prueba de rollback es el resultado esperado
    return 1 if informe.get("decision") == "rollback" and not defectuoso else 0


def verificar(entorno: str, revision: dict, cfg: dict, bitacora: Bitacora) -> int:
    """Release con una sola revisión (sin canary): se reconcilia y se verifica contra el SLA."""
    url = f"http://127.0.0.1:{PUERTOS[entorno]}"
    c = cfg["criterios"]
    try:
        reconciliar(entorno, FACTOR, bitacora)
        r = resumen(asyncio.run(trafico(url, cfg["solicitudes_por_paso"], 0)))
    finally:
        detener(entorno)
    checks = [("tasa de error", r["tasa_error"] <= c["tasa_error_max"], f"{r['tasa_error']:.3f}"),
              ("latencia p95 dentro del SLA", r["latencia_p95_s"] <= c["latencia_p95_s_max"], f"{r['latencia_p95_s']} s"),
              ("muestra mínima", r["n"] >= cfg["min_solicitudes_canary"], f"n={r['n']}")]
    ok = all(x[1] for x in checks)
    print(f"[verificacion:{entorno}] {revision['nombre']} al 100% · {r}")
    for x in checks:
        print(f"    {'OK   ' if x[1] else 'FALLA'} {x[0]}: {x[2]}")
    informe = {"entorno": entorno, "revision": revision["nombre"], "metricas": r, "decision": "verificado" if ok else "fallido",
               "criterios": [{"criterio": x[0], "ok": x[1], "detalle": x[2]} for x in checks]}
    bitacora.registrar("verificacion_release", {"entorno": entorno, "revision": revision["nombre"], "aprobado": ok})
    (RAIZ / "reports" / f"verificacion_{entorno}.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False))
    print(f"[verificacion:{entorno}] decisión: {informe['decision']}")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--entorno", default="produccion", choices=list(PUERTOS))
    ap.add_argument("--canary-defectuoso", action="store_true")
    a = ap.parse_args()
    sys.exit(main(a.entorno, a.canary_defectuoso))
