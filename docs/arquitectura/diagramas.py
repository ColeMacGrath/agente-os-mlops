"""Diagramas de la Fase III (SVG/HTML). render.swift los convierte a PNG.

1. pipeline.html: flujo MLOps/GitOps de punta a punta.
2. arquitectura.html: solución en ejecución con monitoreo, auditoría y GitOps.
"""

from html import escape
from pathlib import Path

DIR = Path(__file__).resolve().parent
F = "-apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif"
C = {"t": "#1B2A41", "s": "#5B6B7F", "az": "#2F6DB5", "azf": "#EAF2FB", "ve": "#1E8E5A", "vef": "#E8F6EE", "mo": "#6B4FA8", "mof": "#F3EEFB",
     "am": "#B7791F", "amf": "#FFF8E6", "gr": "#5B6B7F", "grf": "#F4F6F8", "ro": "#C0392B", "rof": "#FDEDEC"}


class L:
    def __init__(self, w, h):
        self.w, self.h, self.e = w, h, []

    def zona(self, x, y, w, h, t, c, sub=None):
        self.e.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{C[c + "f"]}" stroke="{C[c]}" stroke-width="2.2"/>')
        self.e.append(f'<text x="{x + 18}" y="{y + 32}" font-size="21" font-weight="700" fill="{C[c]}">{escape(t)}</text>')
        if sub:
            self.e.append(f'<text x="{x + 18}" y="{y + 56}" font-size="15.5" fill="{C["s"]}">{escape(sub)}</text>')

    def caja(self, x, y, w, h, t, ls=(), c=None, centro=False):
        bd = C[c] if c else "#8A99AD"
        self.e.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="#fff" stroke="{bd}" stroke-width="{2 if c else 1.4}"/>')
        tx, an = (x + w / 2, ' text-anchor="middle"') if centro else (x + 14, "")
        self.e.append(f'<text x="{tx}" y="{y + 27}" font-size="17.5" font-weight="700" fill="{C["t"]}"{an}>{escape(t)}</text>')
        for i, linea in enumerate(ls):
            self.e.append(f'<text x="{tx}" y="{y + 50 + i * 21}" font-size="15" fill="{C["s"]}"{an}>{escape(linea)}</text>')

    def flecha(self, pts, etq=None, color="t", dash=False, dx=0, dy=-8):
        d = " ".join(f"{x},{y}" for x, y in pts)
        self.e.append(f'<polyline points="{d}" fill="none" stroke="{C[color]}" stroke-width="2.4"{" stroke-dasharray=\"7 5\"" if dash else ""} '
                      f'stroke-linejoin="round" marker-end="url(#p{color})"/>')
        if etq:
            (x1, y1), (x2, y2) = pts[0], pts[1]
            self.e.append(f'<text x="{(x1 + x2) / 2 + dx}" y="{(y1 + y2) / 2 + dy}" font-size="14" fill="{C[color] if color != "t" else C["s"]}" '
                          f'text-anchor="middle">{escape(etq)}</text>')

    def texto(self, x, y, t, s=18, p=400, c="t", a="start"):
        self.e.append(f'<text x="{x}" y="{y}" font-size="{s}" font-weight="{p}" fill="{C[c]}" text-anchor="{a}">{escape(t)}</text>')

    def svg(self):
        marc = "".join(f'<marker id="p{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                       f'<path d="M0,0 L10,5 L0,10 z" fill="{C[k]}"/></marker>' for k in ("t", "ve", "ro", "am", "az", "mo"))
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" font-family="{F}"><defs>{marc}</defs>'
                f'<rect width="100%" height="100%" fill="#fff"/>{"".join(self.e)}</svg>')


def pipeline():
    d = L(2400, 1215)
    d.texto(40, 50, "Pipeline MLOps / GitOps de la Capa Nube del Agente OS", 32, 800)
    d.texto(40, 84, "Cada cambio de código, datos o parámetros recorre el mismo camino; nada llega a producción sin pasar sus compuertas.", 18, 400, "s")
    d.zona(40, 115, 380, 470, "1 · Código y datos (Git + DVC)", "az", "fuente de verdad versionada")
    for i, (t, ls) in enumerate([("src/ · pipelines/ · tests/", ["código del servicio y del pipeline"]), ("params.yaml", ["hiperparámetros y umbrales de compuerta"]),
                                 ("data/evaluacion/", ["conjuntos por grupo: A9, F3, F4 (ciego)"]), ("dvc.yaml · dvc.lock", ["etapas y hash de cada artefacto"]),
                                 ("docs/adr/ · docs/bitacora.md", ["decisiones y registro del trabajo"])]):
        d.caja(60, 190 + i * 76, 340, 64, t, ls)
    d.zona(470, 115, 1020, 470, "2 · Integración continua (GitHub Actions · ci.yml)", "ve", "se ejecuta en cada pull request y en main")
    etapas = [("Lint", ["ruff"]), ("Pruebas", ["unitarias y de datos"]), ("dvc repro", ["5 etapas"]), ("Pruebas", ["modelo y API"]), ("MLflow", ["registro"]),
              ("Imagen", ["Docker + humo"])]
    for i, (t, ls) in enumerate(etapas):
        x = 490 + i * 164
        d.caja(x, 190, 150, 82, t, ls, "ve", True)
        if i:
            d.flecha([(x - 14, 231), (x, 231)])
    d.caja(490, 300, 980, 270, "Etapas de dvc repro", [], "ve")
    sub = [("preparar_datos", ["corpus sintéticos", "versionados"]), ("validar_datos", ["contratos, duplicados,", "fuga, sin PII"]),
           ("entrenar", ["riesgo + inyección,", "calibración en dev"]), ("evaluar", ["TPR, FPR e impacto", "dispar por grupo"]),
           ("compuerta", ["umbrales + no regresión", "→ modo por componente"])]
    for i, (t, lineas) in enumerate(sub):
        x = 510 + i * 192
        d.caja(x, 345, 178, 92, t, lineas, None, True)
        if i:
            d.flecha([(x - 14, 391), (x, 391)])
    d.texto(510, 475, "Salida: models/release.json →  riesgo: aplicar · inyección: sombra · PII: aplicar", 16, 700, "ve")
    d.texto(510, 503, "Si un componente falla, nunca se aplica: queda en sombra o se mantiene el campeón. Los umbrales no se relajan.", 15, 400, "s")
    d.texto(510, 531, "Primera corrida: la validación detectó 210 duplicados y desbalance 82/18; la compuerta rechazó v3.0 y v3.1 (inyección).", 15, 400, "s")
    d.zona(1540, 115, 820, 470, "3 · Registro y artefactos", "mo", "linaje reproducible")
    for i, (t, ls) in enumerate([("MLflow Tracking", ["parámetros, métricas por grupo, reportes, hashes"]),
                                 ("MLflow Model Registry", ["alias: candidato → campeon · sombra", "tags: compuerta, modo, versión"]),
                                 ("Tarjeta de modelo", ["propósito, datos, evaluación, límites"]),
                                 ("Imagen ghcr.io/…/agente-os-cloud:<sha>", ["incluye los modelos aprobados"])]):
        d.caja(1560, 190 + i * 96, 780, 82, t, ls, "mo")
    d.flecha([(1490, 430), (1540, 430)], color="ve")
    d.zona(40, 630, 1450, 500, "4 · Despliegue continuo GitOps (cd.yml)", "am", "el estado deseado vive en deploy/entornos/ y solo cambia por pull request")
    pasos = [("PR automático", ["release de staging", "imagen + versiones"]), ("Merge", ["revisión humana"]),
             ("Reconciliador", ["aplica estado deseado", "Cloud Run o simulado"]), ("Análisis canary", ["10% → 50% → 100%", "error, p95, costo"]),
             ("PR a producción", ["aprobación del", "dueño y Seguridad"])]
    for i, (t, ls) in enumerate(pasos):
        x = 60 + i * 284
        d.caja(x, 715, 260, 104, t, ls, "am", True)
        if i:
            d.flecha([(x - 24, 767), (x, 767)])
    d.caja(60, 860, 690, 240, "Promoción", ["Canary aprobado en cada paso: commit 'avanzar al 50%' y '100%'.", "Al final: promover.py mueve el alias 'campeon'",
                                             "en MLflow y actualiza campeon.json.", "Producción: r-2-0 → r-3-1-0 sin errores;",
                                             "costo por tarea $0.0149 → $0.0040."], "ve")
    d.caja(780, 860, 690, 240, "Rollback automático", ["Si el canary incumple un criterio, el mismo ciclo", "regresa el 100% del tráfico a la revisión estable.",
                                                       "Prueba: r-3-1-1 con 15% de errores inyectados", "→ tasa de error 0.28 → rollback al 10%.",
                                                       "Todo queda en gitops/historial.md y la bitácora."], "ro")
    d.zona(1540, 630, 820, 500, "5 · Operación continua", "gr", "monitoreo, auditoría y mejora")
    for i, (t, ls) in enumerate([("/metrics (Prometheus) + alertas", ["SLO, costo por tarea, mezcla del router,", "deriva de idioma, sombra, PII"]),
                                 ("Bitácora encadenada SHA-256", ["cada decisión con versiones y ruta;", "verificación de integridad"]),
                                 ("Monitoreo semanal (monitoreo.yml)", ["reevalúa por grupo y abre un issue", "si un componente sale de compuerta"]),
                                 ("Acciones de optimización", ["ADR + PR al release (p. ej. router)", "→ vuelve al paso 1"])]):
        d.caja(1560, 705 + i * 104, 780, 90, t, ls)
    d.flecha([(1950, 1130), (1950, 1165), (22, 1165), (22, 350), (40, 350)], None, "gr", True)
    d.texto(980, 1195, "retroalimentación: las acciones de operación vuelven como nuevas versiones de datos, modelos y configuración", 15, 400, "s", "middle")
    d.flecha([(1950, 585), (1950, 630)], color="mo")
    d.flecha([(760, 585), (760, 630)], color="ve")
    return d


def arquitectura():
    d = L(2400, 1080)
    d.texto(40, 50, "Arquitectura en producción · release r-3-1-0", 32, 800)
    d.texto(40, 84, "Implementa el rediseño de la Actividad 9 y agrega operación: métricas, bitácora, sombra y GitOps.", 18, 400, "s")
    d.zona(40, 115, 470, 600, "Dispositivo · Capa Local", "az", "app de macOS (Fase II)")
    for i, (t, ls) in enumerate([("Captura + OCR de ventana", ["Vision, en el equipo"]), ("Filtro Ciego v2", ["seis países, dígito verificador"]),
                                 ("Router local", ["85% se resuelve en el equipo"]), ("Touch ID + Libro Mayor", ["acciones de riesgo alto"])]):
        d.caja(60, 190 + i * 120, 430, 100, t, ls)
    d.zona(570, 115, 1220, 600, "Google Cloud · Cloud Run en dos regiones", "gr", "gateway asíncrono sin estado · 1 a 20 instancias por región")
    d.caja(590, 190, 280, 500, "Barreras", ["1. Filtro Ciego v3", "   (segunda capa)", "", "2. Validador de inyección", "   reglas aplican", "   clasificador v3.1", "   en sombra", "",
                                          "3. Semáforo de riesgo", "   v3.1 (campeón)", "   nunca baja un nivel"], "ro")
    d.caja(900, 190, 300, 230, "Router de modelos", ["simple → Haiku 5.5", "media → Sonnet 5.5", "compleja → Opus 5.5", "OCR primero · participios", "excluidos (ADR-0004)"], "az")
    d.caja(900, 440, 300, 250, "Resiliencia", ["caché de planes (TTL 1 h)", "modo degradado:", "planificador determinista", "si la API falla", "", "INC-F3-021: 0 errores"], "ve")
    d.caja(1230, 190, 540, 160, "Observabilidad · /metrics", ["latencia, errores, costo USD por modelo, tokens,", "ruta, caché, bloqueos, PII en servidor,",
                                                             "idioma de entrada, concordancia de la sombra"], "mo")
    d.caja(1230, 370, 540, 150, "Auditoría · bitácora encadenada", ["solo metadatos: versiones, ruta, decisión, costo", "SHA-256 encadenado con bloqueo de archivo",
                                                                   "12,029 entradas íntegras en 30 días"], "am")
    d.caja(1230, 540, 540, 150, "/v1/version · linaje", ["versión del servicio y de cada modelo,", "modo (aplicar o sombra), hash de los datos",
                                                        "de entrenamiento y commit"], "mo")
    d.zona(1850, 115, 510, 600, "API de Claude (ZDR)", "mo", "ruteada por complejidad")
    for i, (t, ls) in enumerate([("Claude Haiku 5.5", ["~51% de las llamadas"]), ("Claude Sonnet 5.5", ["~41%"]), ("Claude Opus 5.5", ["~8%"]),
                                 ("Caché de prompt + Batch", ["prefijo estable en caché"])]):
        d.caja(1870, 190 + i * 125, 470, 105, t, ls, "mo")
    d.flecha([(510, 400), (590, 400)], "HTTPS")
    d.flecha([(870, 300), (900, 300)])
    d.flecha([(1200, 300), (1230, 300)], dash=True, color="mo")
    d.flecha([(1050, 190), (1050, 172), (1830, 172), (1830, 240), (1870, 240)], color="mo")
    d.texto(1440, 165, "solicitud de plan al modelo elegido", 14, 400, "mo", "middle")
    d.zona(40, 760, 2320, 290, "Ciclo MLOps / GitOps que alimenta esta arquitectura", "ve")
    pasos = [("GitHub", ["código, params,", "release.yaml"]), ("CI", ["lint, pruebas,", "dvc repro"]), ("Compuerta", ["calidad, equidad,", "no regresión"]),
             ("MLflow", ["registro y", "alias"]), ("Imagen", ["GHCR"]), ("PR GitOps", ["estado deseado"]), ("Canary", ["10 / 50 / 100%"]), ("Operación", ["alertas →", "acciones"])]
    for i, (t, ls) in enumerate(pasos):
        x = 70 + i * 287
        d.caja(x, 840, 250, 120, t, ls, "ve", True)
        if i:
            d.flecha([(x - 37, 900), (x, 900)], color="ve")
    d.flecha([(2195, 960), (2195, 1015), (195, 1015), (195, 960)], None, "gr", True)
    d.texto(1195, 1040, "monitoreo semanal y acciones de optimización regresan como cambios versionados", 15, 400, "s", "middle")
    return d


def main():
    for nombre, f in (("pipeline", pipeline), ("arquitectura", arquitectura)):
        lz = f()
        (DIR / f"{nombre}.html").write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>body{{margin:0}}</style></head><body>{lz.svg()}</body></html>',
                                            encoding="utf-8")
        (DIR / f"{nombre}.svg").write_text(lz.svg(), encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()
