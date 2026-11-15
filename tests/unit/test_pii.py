"""Filtro Ciego: formatos por país, validadores y ausencia de falsos positivos."""

import pytest

from agente_os.guardrails.pii import clabe_ok, cpf_ok, dni_es_ok, enmascarar, iban_ok, luhn_ok


@pytest.mark.parametrize("texto,tipo", [
    ("Mi tarjeta es 4111 1111 1111 1111", "tarjeta"),
    ("CLABE 032180000118359719", "clabe"),
    ("RFC GODE561231GR8", "rfc"),
    ("CURP GODE561231HDFRRN09", "curp"),
    ("correo ana@empresa.mx", "correo"),
    ("SSN 123-45-6789", "ssn"),
    ("DNI 12345678Z", "dni_nie"),
    ("IBAN ES91 2100 0418 4502 0005 1332", "iban"),
    ("CPF 529.982.247-25", "cpf"),
    ("CUIT 20-12345678-6", "cuit"),
    ("Tel +54 9 11 2345-6789", "telefono"),
])
def test_enmascara_formatos_por_pais(texto, tipo):
    r = enmascarar(texto)
    assert tipo in r.conteos, r


@pytest.mark.parametrize("texto", [
    "Factura A-1021 por $4,320.00 con vencimiento 15/11/2026",
    "Orden de compra 4471, centro de costos TI-0042",
    "SKU 7501234567890 en inventario",
    "Pedido 2026-11-14 folio 883421",
])
def test_no_enmascara_datos_de_negocio(texto):
    assert enmascarar(texto).total == 0


def test_validadores_rechazan_digito_incorrecto():
    assert luhn_ok("4111111111111111") and not luhn_ok("4111111111111112")
    assert clabe_ok("032180000118359719") and not clabe_ok("032180000118359710")
    assert dni_es_ok("12345678Z") and not dni_es_ok("12345678A")
    assert iban_ok("ES9121000418450200051332") and not iban_ok("ES9121000418450200051333")
    assert cpf_ok("529.982.247-25") and not cpf_ok("529.982.247-26")
