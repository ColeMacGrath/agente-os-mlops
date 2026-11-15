"""Carga de trabajo sintética de la Capa Nube (reutilizada de la Actividad 9).

Cada solicitud imita lo que la app de macOS envía a /v1/analyze cuando el
router local decide que la tarea necesita la nube: una tarea, el texto de la
pantalla ya enmascarado, el contexto de la app y, a veces, una captura.

La mezcla se diseñó a partir de los escenarios de demo de Fase II e incluye
un 12% de tareas repetidas (mismo texto y misma pantalla), que es lo que un
caché de planes puede aprovechar.
"""

import base64
import random

# Imagen PNG mínima válida (1x1). El costo en tokens de una captura real se
# contabiliza aparte con TOKENS_IMAGEN_* porque el backend solo valida el formato.
PNG_1x1 = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
    )
).decode()

PANTALLA_FACTURAS = """Proveedor   Factura   Monto   Vence
Papelería del Centro   A-1021   $4,320.00   15/11/2026
Servicios TI Norte   F-8812   $18,900.00   20/11/2026
Limpieza Integral   L-3301   $6,150.00   30/11/2026
Total pendiente: $29,370.00"""

PANTALLA_CORREO = """De: Laura Méndez <[CORREO]>
Asunto: Pendientes de la semana
Hola equipo, les comparto lo pendiente:
- Revisar el contrato de arrendamiento antes del viernes
- Enviar el reporte de gastos de octubre
- Firmar la orden de compra 4471
- Entregar la presentación del comité el lunes
Saludos"""

PANTALLA_CRM = """Cliente: Grupo Alfa Logística   RFC: [RFC]
Estatus: Activo   Ejecutivo: Jorge Paredes
Últimas interacciones:
12/11 Llamada de seguimiento, interesado en plan anual
08/11 Envío de cotización COT-2291 por $145,000
02/11 Reunión inicial con dirección de operaciones"""

PANTALLA_TABLERO = """Ventas por región - Octubre 2026
Norte   $1,240,000   +8%
Centro   $2,010,000   +3%
Sur   $ 890,000   -4%
Occidente   $1,530,000   +11%
Meta mensual: $5,500,000   Avance: 103%"""

PANTALLA_ERP = """Orden de compra 4471   Estado: Pendiente de aprobación
Solicitante: Compras Corporativas
Partidas: 12 laptops, 12 monitores, 12 bases
Importe: $412,800.00 MXN
Centro de costos: TI-0042"""

# (tarea, pantalla, app, lleva_imagen, complejidad_real)
CATALOGO = [
    ("Copia el total pendiente de facturas", PANTALLA_FACTURAS, "Excel", False, "simple"),
    ("Resume los pendientes del correo", PANTALLA_CORREO, "Mail", False, "simple"),
    ("Abre el portal del SAT en Safari", "", "Finder", False, "simple"),
    ("Guarda la tabla de ventas como CSV", PANTALLA_TABLERO, "Numbers", False, "simple"),
    ("Copia el RFC del cliente", PANTALLA_CRM, "Salesforce", False, "simple"),
    ("Extrae las facturas que vencen este mes", PANTALLA_FACTURAS, "Excel", True, "simple"),
    ("Abre la app Notas", "", "Finder", False, "simple"),
    ("Copia la meta mensual del tablero", PANTALLA_TABLERO, "Safari", True, "simple"),
    ("Haz una lista de pendientes del correo", PANTALLA_CORREO, "Mail", False, "simple"),
    ("Guarda el resumen del cliente en un archivo", PANTALLA_CRM, "Salesforce", False, "simple"),
    ("Resume las últimas interacciones con el cliente y prepara un borrador de seguimiento", PANTALLA_CRM, "Salesforce", True, "media"),
    ("Compara las ventas por región y guarda las que crecieron en un archivo", PANTALLA_TABLERO, "Numbers", True, "media"),
    ("Agenda un recordatorio para cada pendiente del correo", PANTALLA_CORREO, "Mail", False, "media"),
    ("Exporta las facturas a CSV y abre la carpeta de Descargas", PANTALLA_FACTURAS, "Excel", True, "media"),
    ("Prepara un borrador de respuesta a Laura con el estado de cada pendiente", PANTALLA_CORREO, "Mail", True, "media"),
    ("Revisa la orden de compra y prepara la aprobación para firma", PANTALLA_ERP, "SAP", True, "media"),
    ("Paga la factura de Servicios TI Norte", PANTALLA_FACTURAS, "Banca en línea", True, "media"),
    ("Analiza la orden 4471, compárala con el presupuesto de TI, prepara la aprobación y después envía el resumen al comité", PANTALLA_ERP, "SAP", True, "compleja"),
    ("Concilia las facturas pendientes contra el reporte de gastos, identifica diferencias y luego redacta un correo a cada proveedor", PANTALLA_FACTURAS, "Excel", True, "compleja"),
    ("Revisa el tablero, detecta la región con caída, busca las causas en el CRM y después prepara una presentación para dirección", PANTALLA_TABLERO, "Safari", True, "compleja"),
]

PESOS_COMPLEJIDAD = {"simple": 0.55, "media": 0.35, "compleja": 0.10}
TASA_REPETICION = 0.12


def generar(n: int, semilla: int = 7) -> list[dict]:
    """Genera n solicitudes respetando la mezcla de complejidad y la tasa de repetición."""
    rng = random.Random(semilla)
    por_nivel = {nivel: [c for c in CATALOGO if c[4] == nivel] for nivel in PESOS_COMPLEJIDAD}
    solicitudes: list[dict] = []
    for i in range(n):
        if solicitudes and rng.random() < TASA_REPETICION:
            # Las repeticiones son locales en el tiempo: el mismo usuario repite
            # una tarea reciente (ventana de las últimas 300 solicitudes).
            solicitudes.append(dict(rng.choice(solicitudes[-300:])))
            continue
        nivel = rng.choices(list(PESOS_COMPLEJIDAD), weights=PESOS_COMPLEJIDAD.values())[0]
        tarea, pantalla, app, imagen, _ = rng.choice(por_nivel[nivel])
        # Variación para que las tareas no repetidas no compartan caché.
        sufijo = f" (ref {i:06d})"
        solicitudes.append({
            "task": tarea + sufijo,
            "screen_text": pantalla,
            "app_context": app,
            "image_base64": PNG_1x1 if imagen else None,
            "_complejidad": nivel,
        })
    return solicitudes
