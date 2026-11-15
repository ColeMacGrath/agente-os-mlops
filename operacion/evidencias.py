"""Genera las evidencias visuales del pipeline a partir de los registros reales.

- iteraciones_modelo.png: métricas de v1 (Fase II), v2 (Actividad 9), v3.0 y v3.1.
- terminal_*.html: registros de consola (pruebas, DVC, compuerta, canary, rollback,
  auditoría) en formato de terminal; docs/evidencias/render.swift los convierte a PNG.
"""

import html
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
REP = RAIZ / "reports"
REG = RAIZ / "docs" / "evidencias" / "registros"
CAP = RAIZ / "docs" / "evidencias" / "capturas"
CAP.mkdir(parents=True, exist_ok=True)


def iteraciones() -> None:
    versiones = [("v1 · Fase II", "historico_v1.json"), ("v2 · Actividad 9", "historico_v2.json"), ("v3.0 · Fase III", "historico_v3_0.json"),
                 ("v3.1 · Fase III", "evaluacion.json")]
    datos = {n: json.loads((REP / f).read_text()) for n, f in versiones}
    metricas = [("Riesgo: recall alto", "riesgo", "recall_alto"), ("Riesgo: impacto dispar", "riesgo", "impacto_dispar"),
                ("Inyección: TPR", "inyeccion", "tpr"), ("Inyección: FPR", "inyeccion", "fpr"), ("PII: recall", "pii", "recall")]
    colores = ["#B0B8C4", "#7F95B0", "#2F6DB5", "#1E8E5A"]
    plt.rcParams.update({"font.family": "Arial", "font.size": 9.5, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.color": "#E3E8EE", "axes.axisbelow": True, "figure.dpi": 200})
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    for ax, conj, titulo in [(axs[0], "a9", "Conjunto de desarrollo (Actividad 9)"), (axs[1], "ciego_f4", "Conjunto ciego F4 (nunca usado para diseñar)")]:
        ancho = 0.2
        for i, (n, _) in enumerate(versiones):
            vals = [datos[n][c].get(conj, {}).get(k, float("nan")) for _, c, k in metricas]
            xs = [j + (i - 1.5) * ancho for j in range(len(metricas))]
            ax.bar(xs, vals, ancho, color=colores[i], label=n)
        ax.set_xticks(range(len(metricas)))
        ax.set_xticklabels([m[0] for m in metricas], rotation=15, ha="right")
        ax.set_title(titulo, fontweight="bold")
        ax.set_ylim(0, 1.08)
        ax.axhline(0.8, color="#B7791F", ls=":", lw=1)
    axs[1].text(0.99, 0.97, "v3.0 no se evaluó en F4 (F4 se escribió después)", transform=axs[1].transAxes, ha="right", va="top", fontsize=8, color="#5B6B7F")
    axs[0].legend(frameon=False, fontsize=8, loc="lower left", ncol=2)
    fig.suptitle("Iteraciones del modelo: calidad y equidad por versión", fontweight="bold", fontsize=12)
    fig.tight_layout()
    fig.savefig(CAP / "iteraciones_modelo.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def terminal(nombre: str, titulo: str, comando: str, texto: str, max_lineas: int = 46) -> None:
    lineas = texto.rstrip("\n").splitlines()
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas - 6] + ["…"] + lineas[-5:]
    cuerpo = []
    for ln in lineas:
        e = html.escape(ln)
        if any(x in ln for x in ("FALLA", "ERROR", "RECHAZ", "rollback", "Traceback")):
            e = f'<span style="color:#ff7b72">{e}</span>'
        elif any(x in ln for x in ("OK ", "PASSED", "passed", "APROBADO", "promovido", "All checks passed", "up to date", "sí")):
            e = f'<span style="color:#7ee787">{e}</span>'
        cuerpo.append(e)
    alto = 90 + 19 * (len(lineas) + 2)
    pagina = f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;background:#fff;font-family:Menlo,monospace}}
.v{{margin:18px;border-radius:10px;overflow:hidden;box-shadow:0 4px 18px rgba(0,0,0,.25);background:#0d1117}}
.b{{background:#21262d;padding:9px 14px;color:#c9d1d9;font:13px -apple-system,Helvetica}}
.b i{{display:inline-block;width:12px;height:12px;border-radius:6px;margin-right:6px}}
pre{{margin:0;padding:14px 18px;color:#c9d1d9;font-size:12.5px;line-height:19px;white-space:pre-wrap}}
.c{{color:#79c0ff}}</style></head><body><div class="v"><div class="b"><i style="background:#ff5f56"></i><i style="background:#ffbd2e"></i>
<i style="background:#27c93f"></i>&nbsp; {html.escape(titulo)}</div><pre><span class="c">$ {html.escape(comando)}</span>
{chr(10).join(cuerpo)}</pre></div></body></html>"""
    (CAP / f"terminal_{nombre}.html").write_text(pagina, encoding="utf-8")
    (CAP / f"terminal_{nombre}.alto").write_text(str(alto))


def main() -> None:
    iteraciones()
    t = lambda f: (REG / f).read_text()  # noqa: E731
    terminal("pruebas", "agente-os-mlops · pruebas", "python -m pytest -v", t("11_pytest.log"), 40)
    terminal("lint", "agente-os-mlops · lint", "ruff check src pipelines tests gitops operacion", t("12_ruff.log"))
    terminal("dvc_repro", "agente-os-mlops · pipeline DVC", "dvc repro", t("05_dvc_repro.log"), 48)
    terminal("dvc_dag", "agente-os-mlops · DAG del pipeline", "dvc dag", t("13_dvc_dag.log"))
    terminal("compuerta", "agente-os-mlops · compuerta", "python pipelines/compuerta.py", t("16_compuerta_vigente.log"), 50)
    terminal("canary", "agente-os-mlops · despliegue progresivo", "python gitops/analisis_canary.py --entorno produccion",
             t("06_canary_produccion.log"), 46)
    terminal("rollback", "agente-os-mlops · prueba de rollback", "python gitops/analisis_canary.py --entorno staging --canary-defectuoso",
             t("07_canary_rollback_staging.log"))
    terminal("auditoria", "agente-os-mlops · auditoría", "python operacion/informe_auditoria.py", (REP / "auditoria.md").read_text(), 46)
    terminal("historial_gitops", "agente-os-mlops · historial GitOps", "cat gitops/historial.md", (RAIZ / "gitops" / "historial.md").read_text())
    terminal("validacion_fallida", "agente-os-mlops · primera validación de datos (rechazada)", "python pipelines/validar_datos.py",
             "\n".join(("OK    " if c["ok"] else "FALLA ") + f"[{c['corpus']}] {c['chequeo']}: {c['detalle']}"
                       for c in json.loads(t("01_validacion_datos_fallida.json"))["chequeos"]))
    print("evidencias generadas en", CAP)


if __name__ == "__main__":
    main()
