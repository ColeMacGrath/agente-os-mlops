"""API de la Capa Nube del Agente OS (versión 3, lista para producción).

Mismo contrato que la Fase II, con el rediseño de la Actividad 9 implementado:
endpoint asíncrono, router de modelos, caché de planes, clasificación de riesgo
por lote y modo degradado. Agrega lo que pide la operación en producción:
métricas Prometheus, bitácora de auditoría encadenada y /v1/version con el
linaje de modelos y datos.

Orden de las barreras (sin cambios desde la Fase II): Filtro Ciego, validador
de inyección antes de llamar al modelo y semáforo de riesgo que nunca baja.
"""

import base64
import binascii
import hashlib
import json
import random
import time
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from agente_os import __version__
from agente_os.auditoria.bitacora import Bitacora
from agente_os.config import Config, cargar
from agente_os.guardrails.inyeccion import DetectorInyeccion
from agente_os.guardrails.pii import enmascarar
from agente_os.monitoreo import metricas as m
from agente_os.riesgo.modelo import SemaforoRiesgo
from agente_os.router.planificador import (
    ErrorPlanificador,
    PlanificadorClaude,
    PlanificadorDeterminista,
    PlanificadorSimulado,
)
from agente_os.router.router import Router
from agente_os.schemas import (
    EXECUTABLE_ACTIONS,
    AnalyzeRequest,
    GuardRequest,
    GuardResponse,
    PIIFinding,
    PlannedAction,
    RiskLevel,
    RiskRequest,
    RiskResponse,
)

CHARS_POR_TOKEN = 3.5


class CachePlanes:
    """LRU con TTL. En producción se respalda en Memorystore (Redis) con la misma interfaz."""

    def __init__(self, capacidad: int = 5000, ttl_s: int = 3600):
        self._d: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self.capacidad, self.ttl_s = capacidad, ttl_s

    @staticmethod
    def llave(task: str, screen: str, app_ctx: str | None) -> str:
        return hashlib.sha256(f"{task.strip().lower()}\x1f{screen}\x1f{app_ctx or ''}".encode()).hexdigest()

    def obtener(self, k: str) -> dict | None:
        item = self._d.get(k)
        if not item or time.monotonic() - item[0] > self.ttl_s:
            return None
        self._d.move_to_end(k)
        return item[1]

    def guardar(self, k: str, valor: dict) -> None:
        self._d[k] = (time.monotonic(), valor)
        self._d.move_to_end(k)
        while len(self._d) > self.capacidad:
            self._d.popitem(last=False)


class Estado:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        manifiesto = cfg.dir_modelos / "manifest.json"
        self.manifiesto = json.loads(manifiesto.read_text()) if manifiesto.exists() else {}
        release = cfg.dir_modelos / "release.json"
        self.release = json.loads(release.read_text()) if release.exists() else {"riesgo": "aplicar", "inyeccion": "aplicar", "pii": "aplicar"}
        self.semaforo = SemaforoRiesgo(cfg.dir_modelos / "riesgo" / "model.pkl")
        self.detector = DetectorInyeccion(cfg.dir_modelos / "inyeccion" / "model.pkl", modo=self.release.get("inyeccion", "aplicar"))
        self.router = Router(largo_tarea_media=cfg.largo_tarea_media, modelo_fijo=cfg.modelo_fijo or None,
                             excluir_participios=cfg.excluir_participios)
        self.cache = CachePlanes(ttl_s=cfg.ttl_cache_s)
        self.bitacora = Bitacora(cfg.ruta_bitacora)
        self.determinista = PlanificadorDeterminista()
        if cfg.modo_planificador == "claude" and cfg.api_key:
            self.planificador = PlanificadorClaude(cfg.api_key)
        elif cfg.modo_planificador == "determinista":
            self.planificador = None
        else:
            self.planificador = PlanificadorSimulado(factor_tiempo=cfg.factor_tiempo)
        m.INFO.labels(__version__, self.semaforo.version, self.detector.version, cfg.revision).set(1)

    @property
    def versiones(self) -> dict:
        return {"servicio": __version__, "revision": self.cfg.revision, "riesgo": self.semaforo.version,
                "inyeccion": self.detector.version, "modo_inyeccion": self.detector.modo, "planificador": self.cfg.modo_planificador}


def crear_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or cargar()

    @asynccontextmanager
    async def ciclo(app: FastAPI):
        app.state.e = Estado(cfg)
        yield

    app = FastAPI(title="Agente OS · Capa Nube", version=__version__, lifespan=ciclo,
                  description="Gateway de planificación con barreras de seguridad, router de modelos y auditoría.")

    def estado(request: Request) -> Estado:
        return request.app.state.e

    def token(x_agent_token: str | None = Header(default=None)) -> None:
        if cfg.token_agente and x_agent_token != cfg.token_agente:
            raise HTTPException(status_code=401, detail="Token de agente inválido o ausente")

    @app.middleware("http")
    async def medir(request: Request, call_next):
        inicio = time.perf_counter()
        resp = await call_next(request)
        ruta = request.url.path
        if ruta != "/metrics":
            m.SOLICITUDES.labels(ruta, str(resp.status_code)).inc()
            m.LATENCIA.labels(ruta).observe(time.perf_counter() - inicio)
        return resp

    @app.get("/health", tags=["sistema"])
    def health(e: Estado = Depends(estado)) -> dict:
        return {"status": "ok", "service": "agente-os-cloud", "version": __version__, "claude_mode": cfg.modo_planificador,
                "risk_model_version": e.semaforo.version, "injection_model_version": e.detector.version,
                "risk_model_metrics": {k: v for k, v in e.semaforo.metricas.items() if isinstance(v, (int, float))},
                "auth_required": bool(cfg.token_agente)}

    @app.get("/v1/version", tags=["sistema"])
    def version(e: Estado = Depends(estado)) -> dict:
        return {**e.versiones, "linaje": e.manifiesto}

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(m.REGISTRO), media_type=CONTENT_TYPE_LATEST)

    @app.post("/v1/guard", response_model=GuardResponse, tags=["guardrails"], dependencies=[Depends(token)])
    def guard(req: GuardRequest, e: Estado = Depends(estado)) -> GuardResponse:
        if len(req.text) > cfg.max_pantalla:
            raise HTTPException(status_code=413, detail=f"El texto excede {cfg.max_pantalla} caracteres")
        pii = enmascarar(req.text)
        iny = e.detector.detectar(req.text)
        return GuardResponse(injection_detected=iny.detectado, injection_score=iny.puntaje, injection_matches=iny.coincidencias,
                             pii_found=[PIIFinding(kind=k, count=v) for k, v in sorted(pii.conteos.items())], masked_text=pii.enmascarado)

    @app.post("/v1/risk", response_model=RiskResponse, tags=["modelo"], dependencies=[Depends(token)])
    def risk(req: RiskRequest, e: Estado = Depends(estado)) -> RiskResponse:
        if not req.description.strip():
            raise HTTPException(status_code=422, detail="La descripción no puede estar vacía")
        d = e.semaforo.clasificar(req.description, req.type)
        return RiskResponse(risk=d.nivel, model_prediction=d.nivel_modelo, model_confidence=d.confianza, probabilities=d.probabilidades,
                            rule_level=d.nivel_regla, rule_reason=d.motivo_regla)

    def decodificar_imagen(b64: str) -> tuple[str, str]:
        if b64.startswith("data:"):
            b64 = b64.split(",", 1)[-1]
        try:
            raw = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=422, detail="image_base64 no es base64 válido") from None
        if len(raw) > cfg.max_imagen:
            raise HTTPException(status_code=413, detail="La imagen excede el tamaño máximo")
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return base64.b64encode(raw).decode(), "image/png"
        if raw.startswith(b"\xff\xd8\xff"):
            return base64.b64encode(raw).decode(), "image/jpeg"
        raise HTTPException(status_code=415, detail="Formato de imagen no soportado, usa PNG o JPEG")

    @app.post("/v1/analyze", tags=["agente"], dependencies=[Depends(token)])
    async def analyze(req: AnalyzeRequest, e: Estado = Depends(estado)) -> dict:
        inicio = time.perf_counter()
        rid = uuid.uuid4().hex[:12]
        task = req.task.strip()
        if not task:
            raise HTTPException(status_code=422, detail="La tarea no puede estar vacía")
        if len(task) > cfg.max_tarea:
            raise HTTPException(status_code=413, detail=f"La tarea excede {cfg.max_tarea} caracteres")
        if len(req.screen_text) > cfg.max_pantalla:
            raise HTTPException(status_code=413, detail=f"El texto de pantalla excede {cfg.max_pantalla} caracteres")
        img, media = (None, None)
        if req.image_base64:
            img, media = decodificar_imagen(req.image_base64)

        p_task, p_screen = enmascarar(task), enmascarar(req.screen_text)
        for tipo, n in {**p_task.conteos, **p_screen.conteos}.items():
            m.PII_SERVIDOR.labels(tipo).inc(n)
        pii_total = p_task.total + p_screen.total
        m.IDIOMA.labels(m.estimar_idioma(task)).inc()

        def responder(summary, acciones, bloqueado, motivos, puntaje, modelo, extra):
            nivel = RiskLevel.highest(RiskLevel.bajo, *(a.risk for a in acciones))
            lat = int((time.perf_counter() - inicio) * 1000)
            e.bitacora.registrar("analyze", {
                "request_id": rid, "versiones": e.versiones, "modelo_lenguaje": modelo, "ruta": extra.get("complejidad"),
                "bloqueado": bloqueado, "motivos": motivos[:3], "riesgo": nivel.value, "acciones": [a.type for a in acciones],
                "biometria": [a.requires_biometric for a in acciones], "pii_servidor": pii_total, "cache_plan": extra.get("cache_plan", False),
                "degradado": extra.get("modo_degradado", False), "costo_usd": extra.get("costo_usd", 0.0), "latencia_ms": lat,
            })
            return {"request_id": rid, "summary": summary, "actions": [a.model_dump() for a in acciones], "overall_risk": nivel.value,
                    "blocked": bloqueado, "block_reasons": motivos, "pii_masked_server": pii_total, "injection_score": puntaje,
                    "claude_mode": cfg.modo_planificador, "model": modelo, "latency_ms": lat, **extra}

        iny = e.detector.detectar(req.screen_text)
        sombra = iny.decision_sombra
        if iny.decision_sombra is not None:
            m.SOMBRA.labels("coincide" if iny.decision_sombra == iny.detectado else
                            ("sombra_bloquearia" if iny.decision_sombra else "sombra_permitiria")).inc()
        if iny.detectado:
            m.BLOQUEOS.labels("inyeccion").inc()
            motivos = [f"Posible inyección de prompt en pantalla: {c}" for c in iny.coincidencias]
            return responder("Ejecución cancelada: la pantalla contiene instrucciones dirigidas al agente.", [], True, motivos,
                             iny.puntaje, "ninguno", {"costo_usd": 0.0, "cache_plan": False, "sombra_inyeccion": sombra})

        if cfg.tasa_falla_simulada and random.random() < cfg.tasa_falla_simulada:
            raise HTTPException(status_code=500, detail="Falla simulada (prueba de rollback)")
        llave = e.cache.llave(p_task.enmascarado, p_screen.enmascarado, req.app_context)
        guardado = e.cache.obtener(llave) if cfg.cache_planes else None
        if guardado is not None:
            m.CACHE_PLANES.labels("acierto").inc()
            acciones = [PlannedAction(**a) for a in guardado["actions"]]
            return responder(guardado["summary"], acciones, False, [], iny.puntaje, guardado["model"],
                             {"costo_usd": 0.0, "cache_plan": True, "complejidad": guardado["complejidad"]})
        m.CACHE_PLANES.labels("fallo").inc()

        ruta = e.router.decidir(p_task.enmascarado, p_screen.enmascarado, bool(img))
        tokens_var = int((len(p_task.enmascarado) + len(p_screen.enmascarado) + len(req.app_context or "")) / CHARS_POR_TOKEN) + 1
        tokens_var += 900 if ruta.enviar_imagen else 0
        degradado, consumo = False, None
        try:
            if e.planificador is None:
                raise ErrorPlanificador("Planificador determinista configurado", 503)
            plan, consumo = await e.planificador.plan(ruta.modelo, p_task.enmascarado, p_screen.enmascarado,
                                                      img if ruta.enviar_imagen else None, media, req.app_context, tokens_var)
        except ErrorPlanificador as exc:
            if exc.status_code < 500 and cfg.modo_planificador != "determinista":
                return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})
            degradado = True
            m.DEGRADADO.inc()
            plan = e.determinista.plan(p_task.enmascarado, p_screen.enmascarado, None, None, req.app_context)

        if getattr(plan, "screen_injection_suspected", False):
            m.BLOQUEOS.labels("modelo_inyeccion").inc()
            return responder("Ejecución cancelada: el modelo detectó instrucciones sospechosas en la pantalla.", [], True,
                             ["El modelo marcó el contenido de pantalla como posible inyección"], max(iny.puntaje, 0.5), plan.model, {})

        decisiones = e.semaforo.clasificar_lote([f"{a['description']} {a['target']}".strip() for a in plan.actions],
                                                [a["type"] for a in plan.actions])
        acciones = []
        for a, d in zip(plan.actions, decisiones):
            ejecutable = a["type"] in EXECUTABLE_ACTIONS and d.nivel is not RiskLevel.alto
            m.RIESGO.labels(d.nivel.value).inc()
            acciones.append(PlannedAction(type=a["type"], description=a["description"], target=a["target"],
                                          content=enmascarar(a["content"]).enmascarado, risk=d.nivel, risk_sources=d.fuentes,
                                          model_confidence=d.confianza, executable=ejecutable, requires_biometric=d.nivel is RiskLevel.alto,
                                          simulated=not ejecutable))
        modelo = "planificador-determinista" if degradado else consumo.modelo
        extra = {"cache_plan": False, "complejidad": ruta.complejidad, "modo_degradado": degradado, "imagen_enviada": ruta.enviar_imagen,
                 "costo_usd": 0.0, "sombra_inyeccion": sombra}
        if consumo is not None:
            m.RUTA.labels(ruta.complejidad, consumo.modelo).inc()
            for tipo, n in [("entrada", consumo.tokens_entrada), ("cache_lectura", consumo.tokens_cache_lectura),
                            ("cache_escritura", consumo.tokens_cache_escritura), ("salida", consumo.tokens_salida)]:
                m.TOKENS.labels(consumo.modelo, tipo).inc(n)
            m.COSTO.labels(consumo.modelo).inc(consumo.costo_usd)
            extra["costo_usd"] = round(consumo.costo_usd, 6)
            extra["latencia_modelo_s"] = round(consumo.latencia_modelo_s, 3)
        if not degradado:
            e.cache.guardar(llave, {"summary": plan.summary, "actions": [a.model_dump() for a in acciones], "model": modelo,
                                    "complejidad": ruta.complejidad})
        return responder(plan.summary, acciones, False, [], iny.puntaje, modelo, extra)

    return app


app = crear_app()
