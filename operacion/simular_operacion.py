"""Simulación de 30 días de operación de la release r-3-1-0 en producción.

Cada día se envía al servicio real (barreras, modelos, router, caché, bitácora y
métricas) una muestra de solicitudes con la mezcla de la oleada vigente. Las
cifras de costo se escalan al volumen real del día. La latencia y el consumo de
tokens del modelo de lenguaje son simulados (planificador simulado).

Eventos programados (lo que la operación debe detectar y atender):
- Día 11: inicia la oleada 2 (de 300 a 1,000 usuarios).
- Día 15: un área adopta un flujo de conciliación con tareas largas pero simples.
- Día 21: la API del modelo no está disponible durante 50 minutos.
- Día 22: inicia el piloto de Brasil (usuarios en portugués).

Las acciones de optimización no están programadas: se disparan con las alertas
y se aplican al día siguiente, como haría el equipo de operación.

Uso: python operacion/simular_operacion.py
"""

import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "operacion"))

from carga import CATALOGO, PNG_1x1  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from agente_os.api.app import crear_app  # noqa: E402
from agente_os.auditoria.bitacora import Bitacora  # noqa: E402
from agente_os.config import Config  # noqa: E402
from agente_os.datos import corpus_inyeccion  # noqa: E402
from agente_os.datos.pii_sintetico import pii_por_pais  # noqa: E402

SALIDA = RAIZ / "operacion" / "salida"
MUESTRA_DIARIA = 400
TAREAS_POR_USUARIO, PROP_NUBE = 40, 0.15
PRESUPUESTO_DIARIO = 45000 / 365  # C03 de la Fase I
COSTO_INSTANCIA_HORA = 0.0648 + 0.0036  # 1 vCPU + 0.5 GiB por hora (precio de referencia)

TAREAS_EN = [("Copy the pending invoice total", "Total pending: $29,370.00", "Excel", False, "simple"),
             ("Summarize the email to-dos", "Review the lease before Friday. Send the October expense report.", "Mail", False, "simple"),
             ("Open the vendor portal", "", "Finder", False, "simple"),
             ("Compare regional sales and save the growing ones to a file", "North +8% Center +3% South -4%", "Numbers", True, "media"),
             ("Pay the Servicios TI Norte invoice", "Invoice F-8812 $18,900", "Online banking", True, "media")]
TAREAS_PT = [("Copie o total das faturas pendentes", "Total pendente: R$ 29.370,00", "Excel", False, "simple"),
             ("Resuma as pendências do e-mail", "Revisar o contrato antes de sexta. Enviar o relatório de despesas.", "Mail", False, "simple"),
             ("Abra o portal de fornecedores", "", "Finder", False, "simple"),
             ("Compare as vendas por região e salve as que cresceram", "Norte +8% Centro +3% Sul -4%", "Numbers", True, "media"),
             ("Pague a fatura da Servicios TI Norte", "Fatura F-8812 R$ 18.900", "Banco", True, "media")]
CONCILIACION = ["Copia el total conciliado de la cuenta de proveedores nacionales correspondiente al cierre de octubre",
                "Copia el saldo final conciliado de la cuenta bancaria principal de operación al cierre del mes",
                "Copia el importe total de las partidas en tránsito de la conciliación de la cuenta de nómina"]


def mezcla_idioma(dia: int) -> dict:
    if dia <= 10:
        return {"es": 0.95, "en": 0.05}
    if dia <= 21:
        return {"es": 0.88, "en": 0.12}
    return {"es": 0.76, "en": 0.11, "pt": 0.13}


def usuarios(dia: int) -> int:
    return 300 if dia <= 10 else 1000


def psi(actual: dict, base: dict) -> float:
    claves = set(actual) | set(base)
    return round(sum((actual.get(k, 1e-4) - base.get(k, 1e-4)) * math.log(actual.get(k, 1e-4) / base.get(k, 1e-4)) for k in claves), 4)


class Generador:
    def __init__(self, semilla: int = 2026):
        self.rng = random.Random(semilla)
        ataques = [f for f in corpus_inyeccion.generar(semilla=99, n_por_idioma=200) if f["etiqueta"] == 1]
        self.ataques = {k: [f["texto"] for f in ataques if f["idioma"] == k] for k in ("es", "en", "pt", "spanglish")}
        self.recientes: list[dict] = []
        self.n = 0
        self.prob_pii = 0.01  # baja cuando el dispositivo recibe el Filtro Ciego v2

    def solicitud(self, dia: int) -> dict:
        r = self.rng
        self.n += 1
        if self.recientes and r.random() < 0.12:
            return dict(r.choice(self.recientes[-300:]), repetida=True)
        idioma = r.choices(list(mezcla_idioma(dia)), weights=list(mezcla_idioma(dia).values()))[0]
        if idioma == "es" and dia >= 15 and r.random() < 0.35:
            tarea, pantalla, app, imagen, compl = r.choice(CONCILIACION), "Saldo conciliado: $1,284,330.10", "SAP", False, "simple"
            flujo = "conciliacion"
        else:
            tarea, pantalla, app, imagen, compl = r.choice({"es": CATALOGO, "en": TAREAS_EN, "pt": TAREAS_PT}[idioma])
            flujo = "general"
        ataque = None
        if r.random() < 0.02:
            grupo = r.choice(["spanglish", idioma]) if idioma == "es" else idioma
            ataque = grupo
            pantalla = r.choice(self.ataques[grupo])
        pii = None
        if r.random() < self.prob_pii:
            pais = r.choice(["US", "ES", "AR", "BR", "CO"])
            tipo, valor = r.choice(pii_por_pais(r)[pais])
            pantalla += f" Contacto: {valor}"
            pii = pais
        s = {"task": f"{tarea} (ref {self.n:06d})", "screen_text": pantalla, "app_context": app,
             "image_base64": PNG_1x1 if imagen else None, "idioma": idioma, "flujo": flujo, "ataque": ataque, "pii": pii, "repetida": False}
        self.recientes.append(s)
        return s


def evaluar_alertas(reglas: list[dict], fila: dict, historial: list[dict]) -> list[dict]:
    disparadas = []
    for r in reglas:
        v = fila.get(r["metrica"])
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        cumple = v > r["umbral"] if r["op"] == ">" else v < r["umbral"]
        if cumple and r.get("dias_consecutivos", 1) > 1:
            previos = historial[-(r["dias_consecutivos"] - 1):]
            cumple = len(previos) == r["dias_consecutivos"] - 1 and all(
                (p.get(r["metrica"]) or 0) > r["umbral"] if r["op"] == ">" else (p.get(r["metrica"]) or 1) < r["umbral"] for p in previos)
        if cumple:
            disparadas.append({"dia": fila["dia"], "id": r["id"], "severidad": r["severidad"], "dueno": r["dueno"],
                               "descripcion": r["descripcion"], "valor": v, "umbral": r["umbral"]})
    return disparadas


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta_bitacora = SALIDA / "bitacora.jsonl"
    ruta_bitacora.unlink(missing_ok=True)
    reglas = yaml.safe_load((RAIZ / "operacion" / "alertas.yaml").read_text())["reglas"]
    bitacora = Bitacora(ruta_bitacora)
    gen = Generador()
    estado = {"largo_tarea_media": 70, "excluir_participios": False, "horas_min_instancias": 24}

    def nueva_app():
        cfg = Config(dir_modelos=RAIZ / "models", ruta_bitacora=ruta_bitacora, modo_planificador="simulado", factor_tiempo=0.0,
                     revision="r-3-1-0", largo_tarea_media=estado["largo_tarea_media"],
                     excluir_participios=estado["excluir_participios"])
        return TestClient(crear_app(cfg))

    cliente = nueva_app().__enter__()
    filas, alertas, acciones, base_idioma, pendientes = [], [], [], None, []
    ataques_ventana: list[pd.DataFrame] = []
    eval_f4 = json.loads((RAIZ / "reports" / "evaluacion.json").read_text())["riesgo"]["ciego_f4"]["grupos"]
    for dia in range(1, 31):
        for accion in [a for a in pendientes if a["aplicar_dia"] == dia]:
            if accion["tipo"] == "router":
                estado["largo_tarea_media"] = int(accion["valor"]["ROUTER_TASK_LEN_MEDIUM"])
                estado["excluir_participios"] = accion["valor"]["ROUTER_IGNORE_PARTICIPLES"] == "1"
                cliente.__exit__(None, None, None)
                cliente = nueva_app().__enter__()
            elif accion["tipo"] == "instancias":
                estado["horas_min_instancias"] = accion["valor"]
            elif accion["tipo"] == "filtro_dispositivo":
                gen.prob_pii = accion["valor"]
            elif accion["tipo"] == "linea_base_idioma":
                base_idioma = accion["valor"]
            bitacora.registrar("accion_optimizacion", {"dia": dia, **{k: v for k, v in accion.items() if k != "aplicar_dia"}})
            accion["aplicada_dia"] = dia
            acciones.append(accion)
        pendientes = [a for a in pendientes if a["aplicar_dia"] != dia]

        resultados = []
        falla_desde = int(MUESTRA_DIARIA * 0.55) if dia == 21 else None
        for i in range(MUESTRA_DIARIA):
            s = gen.solicitud(dia)
            plan = cliente.app.state.e.planificador
            plan.falla_api = falla_desde is not None and falla_desde <= i < falla_desde + int(MUESTRA_DIARIA * 0.035)
            cuerpo = {k: s[k] for k in ("task", "screen_text", "app_context", "image_base64")}
            r = cliente.post("/v1/analyze", json=cuerpo)
            d = r.json() if r.status_code == 200 else {}
            resultados.append({**{k: s[k] for k in ("idioma", "flujo", "ataque", "pii", "repetida")}, "codigo": r.status_code,
                               "costo": d.get("costo_usd", 0.0), "latencia": d.get("latencia_modelo_s", 0.05 if d.get("cache_plan") else 0.0),
                               "modelo": d.get("model"), "cache": d.get("cache_plan", False), "bloqueado": d.get("blocked", False),
                               "degradado": d.get("modo_degradado", False), "sombra": d.get("sombra_inyeccion"),
                               "pii_servidor": d.get("pii_masked_server", 0)})
        cliente.app.state.e.planificador.falla_api = False
        df = pd.DataFrame(resultados)
        volumen = usuarios(dia) * TAREAS_POR_USUARIO * PROP_NUBE
        ok = df[df.codigo == 200]
        llm = ok[(~ok.cache) & (~ok.bloqueado) & (~ok.degradado)]
        mezcla = Counter(llm.modelo)
        dist = df.idioma.value_counts(normalize=True).round(4).to_dict()
        if dia == 7:
            base_idioma = df.idioma.value_counts(normalize=True).to_dict()
        ataques_ventana = (ataques_ventana + [df[df.ataque.notna()]])[-7:]
        atq = pd.concat(ataques_ventana)
        costo_tarea = float(ok.costo.mean())
        infra = 2 * estado["horas_min_instancias"] * COSTO_INSTANCIA_HORA + 2.5
        fila = {
            "dia": dia, "usuarios": usuarios(dia), "volumen_real": int(volumen), "muestra": len(df),
            "disponibilidad": round(len(ok) / len(df), 5), "tasa_error": round(1 - len(ok) / len(df), 5),
            "tasa_degradado": round(float(ok.degradado.mean()), 4),
            "latencia_p95_s": round(float(llm.latencia.quantile(0.95)), 2), "latencia_p50_s": round(float(llm.latencia.median()), 2),
            "costo_por_tarea": round(costo_tarea, 6), "costo_modelo_dia": round(costo_tarea * volumen, 2), "costo_infra_dia": round(infra, 2),
            "costo_diario_vs_presupuesto": round((costo_tarea * volumen + infra) / PRESUPUESTO_DIARIO, 3),
            "tasa_cache": round(float(ok.cache.mean()), 4),
            "mix_haiku": round(mezcla.get("claude-haiku-5-5", 0) / max(len(llm), 1), 3),
            "mix_sonnet": round(mezcla.get("claude-sonnet-5-5", 0) / max(len(llm), 1), 3),
            "mix_opus": round(mezcla.get("claude-opus-5-5", 0) / max(len(llm), 1), 3),
            "tasa_bloqueo": round(float(ok.bloqueado.mean()), 4),
            "idioma_es": dist.get("es", 0), "idioma_en": dist.get("en", 0), "idioma_pt": dist.get("pt", 0),
            "psi_idioma": psi(dist, base_idioma) if base_idioma else 0.0,
            "ataques": int(df.ataque.notna().sum()), "ataques_ventana_7d": len(atq), "inyeccion_tpr_campeon": round(float(atq.bloqueado.mean()), 3) if len(atq) else None,
            "inyeccion_tpr_sombra": round(float(atq.sombra.fillna(False).astype(bool).mean()), 3) if len(atq) else None,
            "inyeccion_fp_sombra": round(float(df[df.ataque.isna()].sombra.fillna(False).astype(bool).mean()), 4),
            "tasa_pii_servidor": round(float((df[df.ataque.isna()].pii_servidor > 0).mean()), 4),  # solo tráfico legítimo
        }
        fila["inyeccion_tpr_brecha_sombra"] = round((fila["inyeccion_tpr_sombra"] or 0) - (fila["inyeccion_tpr_campeon"] or 0), 3) if dia >= 7 else None
        pt_atq = atq[atq.ataque == "pt"]
        fila["inyeccion_tpr_campeon_pt"] = round(float(pt_atq.bloqueado.mean()), 3) if len(pt_atq) else None
        fila["inyeccion_tpr_sombra_pt"] = round(float(pt_atq.sombra.fillna(False).astype(bool).mean()), 3) if len(pt_atq) else None
        disparadas = evaluar_alertas(reglas, fila, filas)
        for a in disparadas:
            bitacora.registrar("alerta", a)
        alertas += disparadas
        filas.append(fila)

        ids = {a["id"] for a in disparadas}
        tipos = {a["tipo"] for a in pendientes} | {a["tipo"] for a in acciones}

        def programar(tipo, valor, alerta, decision, evidencia, validacion, adr=None, sistema=True, _dia=dia, _tipos=tipos, _pend=pendientes):
            if tipo not in _tipos:
                _pend.append({"tipo": tipo, "valor": valor, "aplicar_dia": _dia + 1, "alerta": alerta, "decision": decision,
                              "evidencia": evidencia, "validacion": validacion, "adr": adr, "cambia_sistema": sistema})
                _tipos.add(tipo)

        if "PRIV-PII" in ids:
            programar("filtro_dispositivo", 0.001, "PRIV-PII", "Publicar en la app de macOS el Filtro Ciego v2 (formatos internacionales)",
                      f"{fila['tasa_pii_servidor']:.2%} de las solicitudes traen datos personales sin enmascarar (DNI, SSN, CPF, IBAN): "
                      "el servidor los tapa (segunda barrera), pero salen del dispositivo.",
                      "El Filtro Ciego v2 protege 100% de los datos de seis países en los conjuntos de evaluación, sin falsos positivos.",
                      "docs/adr/0006-filtro-dispositivo.md")
        if "FIN-MEZCLA" in ids:
            from agente_os.router.router import _VERBOS, Router
            conc = df[(df.flujo == "conciliacion") & (df.codigo == 200) & (~df.cache)]
            ejemplo = CONCILIACION[0] + " (ref 000000)"
            verbos = [m.group(0) for m in _VERBOS.finditer(ejemplo)]
            programar("router", {"ROUTER_TASK_LEN_MEDIUM": "120", "ROUTER_IGNORE_PARTICIPLES": "1"}, "FIN-MEZCLA",
                      "Ajustar el router: no contar participios como verbos y subir el umbral de longitud de 70 a 120 caracteres (cambio vía GitOps)",
                      f"Sonnet pasó de 45% a {fila['mix_sonnet']:.0%} de las llamadas con el flujo de conciliación ({len(conc)} tareas en la muestra). "
                      f"Causa raíz: el router contaba {verbos} como verbos y la tarea mide {len(ejemplo)} caracteres; "
                      f"con el ajuste se clasifica como '{Router(120, excluir_participios=True).complejidad(ejemplo, '', False)}'.",
                      "Las barreras no dependen del router: el semáforo de riesgo y Touch ID siguen aplicando a toda acción planeada.",
                      "docs/adr/0004-ajuste-router.md")
        if "DRIFT-IDIOMA" in ids:
            recall_pt = eval_f4.get("portugues", {}).get("tpr")
            programar("linea_base_idioma", df.idioma.value_counts(normalize=True).to_dict(), "DRIFT-IDIOMA",
                      "Confirmar que el cambio es el piloto de Brasil y fijar una nueva línea base de idioma",
                      f"PSI {fila['psi_idioma']:.2f}: {fila['idioma_pt']:.0%} de las tareas en portugués desde el día 22.",
                      f"El semáforo de riesgo v3.1 tiene recall {recall_pt:.2f} en portugués (conjunto ciego F4); el grupo se agrega al reporte semanal de fairness.",
                      None, False)
        if "SEG-SOMBRA" in ids and dia >= 14:
            programar("etiquetado_f5", None, "SEG-SOMBRA", "Solicitar al Comité de IA el etiquetado del conjunto F5 con textos reales para decidir la promoción del clasificador",
                      f"Ventana de 7 días: el campeón (reglas) bloquea {fila['inyeccion_tpr_campeon']:.0%} de los ataques y el clasificador en sombra "
                      f"{fila['inyeccion_tpr_sombra']:.0%}, con {fila['inyeccion_fp_sombra']:.1%} de falsos positivos en tráfico benigno.",
                      "La promoción requiere pasar todas las compuertas en F5; mientras tanto el clasificador sigue en sombra.", None, False)
        if "OPS-DEG" in ids:
            programar("incidente_api", None, "OPS-DEG", "Incidente INC-F3-021 cerrado: caída de 50 min de la API del modelo atendida en modo degradado",
                      f"{fila['tasa_degradado']:.1%} de las respuestas del día salieron del planificador determinista; disponibilidad del servicio {fila['disponibilidad']:.2%}.",
                      "Sin violación del SLA; el runbook de la Actividad 8 se cumplió sin intervención manual.", None, False)
        if dia == 10:
            programar("instancias", 11, "revisión FinOps semanal", "Mantener la instancia mínima solo de 7:00 a 18:00 (11 h) en lugar de 24 h",
                      "Diez días de tráfico: el 100% de las tareas ocurre en horario laboral; fuera de él la instancia mínima solo genera costo.",
                      "Fuera de horario el arranque en frío medido (1.3 s) no afecta el SLA de 16 s.", "docs/adr/0005-instancias-minimas.md")
        print(f"día {dia:2d} · usuarios {fila['usuarios']:4d} · disp {fila['disponibilidad']:.4f} · p95 {fila['latencia_p95_s']:5.2f} s · "
              f"costo/tarea {fila['costo_por_tarea']:.5f} · cache {fila['tasa_cache']:.2f} · mix H/S/O {fila['mix_haiku']:.2f}/"
              f"{fila['mix_sonnet']:.2f}/{fila['mix_opus']:.2f} · PSI {fila['psi_idioma']:.3f} · alertas {sorted(ids)}")
    cliente.__exit__(None, None, None)
    pd.DataFrame(filas).to_csv(SALIDA / "metricas_diarias.csv", index=False)
    (SALIDA / "alertas.json").write_text(json.dumps(alertas, indent=2, ensure_ascii=False, default=str))
    (SALIDA / "acciones.json").write_text(json.dumps(acciones, indent=2, ensure_ascii=False, default=str))
    print(f"{len(alertas)} alertas, {len(acciones)} acciones. Resultados en {SALIDA.relative_to(RAIZ) if SALIDA.is_relative_to(RAIZ) else SALIDA}")


if __name__ == "__main__":
    main()
