"""Tablero de operación: gráficas de los 30 días a partir de operacion/salida.

Genera docs/evidencias/capturas/tablero_*.png con los mismos indicadores que el
tablero de Cloud Monitoring: servicio, costo, router, idioma y seguridad.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SAL = RAIZ / "docs" / "evidencias" / "capturas"
SAL.mkdir(parents=True, exist_ok=True)
AZUL, VERDE, ROJO, AMBAR, GRIS, MORADO = "#2F6DB5", "#1E8E5A", "#C0392B", "#B7791F", "#8A99AD", "#6B4FA8"
plt.rcParams.update({"font.family": "Arial", "font.size": 9.5, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "#E3E8EE", "axes.axisbelow": True, "axes.titleweight": "bold", "axes.titlesize": 10.5, "figure.dpi": 200})


def eventos(ax, acciones):
    for d, txt in [(11, "oleada 2"), (15, "flujo conciliación"), (21, "caída API"), (22, "piloto Brasil")]:
        ax.axvline(d, color=GRIS, ls=":", lw=1)
        ax.text(d + 0.15, ax.get_ylim()[1], txt, fontsize=7, color=GRIS, va="top", rotation=90)
    for a in acciones:
        ax.axvline(a["aplicada_dia"], color=VERDE, ls="--", lw=0.8, alpha=0.6)


def main() -> None:
    df = pd.read_csv(RAIZ / "operacion" / "salida" / "metricas_diarias.csv")
    acciones = json.loads((RAIZ / "operacion" / "salida" / "acciones.json").read_text())
    alertas = json.loads((RAIZ / "operacion" / "salida" / "alertas.json").read_text())
    router = [a for a in acciones if a["tipo"] == "router"]
    fig, axs = plt.subplots(3, 2, figsize=(12, 10.5))
    ax = axs[0, 0]
    ax.plot(df.dia, df.latencia_p95_s, "o-", color=AZUL, ms=3, label="p95")
    ax.plot(df.dia, df.latencia_p50_s, "o-", color=AZUL, alpha=0.4, ms=3, label="p50")
    ax.axhline(16, color=AMBAR, ls=":", lw=1.5)
    ax.text(30, 16.3, "SLA 16 s", color=AMBAR, ha="right", fontsize=8)
    ax.set(title="Latencia de planificación (s)", ylim=(0, 19))
    ax.legend(frameon=False, loc="lower left", fontsize=8)
    eventos(ax, [])
    ax = axs[0, 1]
    ax.plot(df.dia, df.disponibilidad * 100, "o-", color=VERDE, ms=3, label="disponibilidad")
    ax.bar(df.dia, df.tasa_degradado * 100 * 10, color=AMBAR, alpha=0.7, label="respuestas degradadas (x10)")
    ax.axhline(99.9, color=AMBAR, ls=":", lw=1.5)
    ax.set(title="Disponibilidad y modo degradado (%)", ylim=(0, 105))
    ax.legend(frameon=False, loc="lower left", fontsize=8)
    eventos(ax, [])
    ax = axs[1, 0]
    ax.plot(df.dia, df.costo_por_tarea * 1000, "o-", color=MORADO, ms=3)
    ax.axhline(6, color=AMBAR, ls=":", lw=1.5)
    ax.text(30, 6.1, "umbral FinOps $6/1,000", color=AMBAR, ha="right", fontsize=8)
    ax.set(title="Costo por 1,000 tareas (USD)", ylim=(0, 7))
    eventos(ax, router)
    if router:
        d = router[0]["aplicada_dia"]
        ax.annotate("ajuste del router\n(ADR-0004)", xy=(d, df.loc[df.dia == d + 1, "costo_por_tarea"].iloc[0] * 1000), xytext=(d + 2.5, 1.3),
                    fontsize=8, color=VERDE, arrowprops=dict(arrowstyle="->", color=VERDE))
    ax = axs[1, 1]
    ax.stackplot(df.dia, df.mix_haiku, df.mix_sonnet, df.mix_opus, colors=[VERDE, AZUL, MORADO], alpha=0.85, labels=["Haiku", "Sonnet", "Opus"])
    ax.set(title="Mezcla del router (proporción de llamadas)", ylim=(0, 1))
    ax.legend(frameon=False, loc="upper left", fontsize=8, ncol=3)
    eventos(ax, router)
    ax = axs[2, 0]
    ax.stackplot(df.dia, df.idioma_es, df.idioma_en, df.idioma_pt, colors=["#9DB7D8", "#C9D6E3", AMBAR], labels=["español", "inglés", "portugués"])
    ax2 = ax.twinx()
    ax2.plot(df.dia, df.psi_idioma, "o-", color=ROJO, ms=3, label="PSI")
    ax2.axhline(0.2, color=ROJO, ls=":", lw=1)
    ax2.set_ylabel("PSI", color=ROJO)
    ax2.spines["right"].set_visible(True)
    ax2.grid(False)
    ax.set(title="Mezcla de idiomas y deriva (PSI)", ylim=(0, 1))
    ax.legend(loc="upper left", fontsize=8, ncol=3, framealpha=0.9)
    ax = axs[2, 1]
    ax.plot(df.dia, df.inyeccion_tpr_campeon, "o-", color=GRIS, ms=3, label="campeón (reglas) · aplica")
    ax.plot(df.dia, df.inyeccion_tpr_sombra, "o-", color=VERDE, ms=3, label="clasificador v3.1 · sombra")
    ax.plot(df.dia, df.inyeccion_fp_sombra, "o-", color=ROJO, ms=2, lw=1, label="falsos positivos en sombra")
    ax.set(title="Detección de inyección en producción (ventana de 7 días)", ylim=(-0.02, 1.05))
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    eventos(ax, [])
    for a in axs.flat:
        a.set_xlabel("día de operación")
        a.set_xlim(0.5, 30.5)
    fig.suptitle("Agente OS · operación de la release r-3-1-0 (30 días simulados)", fontsize=13, fontweight="bold", y=0.995)
    fig.tight_layout()
    fig.savefig(SAL / "tablero_operacion.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 3.2))
    sev = {"P1": ROJO, "P2": AMBAR, "P3": AZUL}
    ids = sorted({a["id"] for a in alertas})
    for a in alertas:
        ax.scatter(a["dia"], ids.index(a["id"]), color=sev[a["severidad"]], s=40, zorder=3)
    for a in acciones:
        ax.axvline(a["aplicada_dia"], color=VERDE, ls="--", lw=1)
        ax.text(a["aplicada_dia"] + 0.12, -0.45, a["tipo"].replace("_", " "), rotation=90, fontsize=7, color=VERDE, va="bottom")
    ax.set_yticks(range(len(ids)))
    ax.set_yticklabels(ids)
    ax.set(xlabel="día de operación", xlim=(0.5, 30.5), ylim=(-0.6, len(ids) - 0.5))
    ax.set_title("Alertas por día (punto) y acciones aplicadas (línea verde)", pad=12)
    fig.tight_layout()
    fig.savefig(SAL / "tablero_alertas.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("tableros en", SAL)


if __name__ == "__main__":
    main()
