"""Corpus sintético del semáforo de riesgo (versión 3).

Historia del corpus:
- v1 (Fase II): léxico de acciones en español neutro e inglés parcial.
- v2 (Actividad 9): + español coloquial mexicano, Spanglish y errores tipográficos.
- v3 (Fase III): + portugués (oleada internacional) y traducción completa al
  inglés del léxico español; el inglés de v1 cubría solo una parte de las acciones.

Es composicional: acción del nivel de riesgo + objeto + marco de frase. La
evaluación se hace con conjuntos escritos por separado (data/evaluacion) y una
prueba automática verifica que ningún texto de evaluación aparezca en el corpus.
"""

import random

SEMILLA = 42
ETIQUETAS = ["bajo", "medio", "alto"]

LEXICO = {
    "es": {
        "bajo": ["abrir {o}", "abre {o}", "mostrar {o}", "muestra {o}", "ver {o}", "leer {o}", "lee {o}", "buscar {o}", "busca {o}",
                 "consultar {o}", "consulta {o}", "copiar {o} al portapapeles", "copia {o}", "resumir {o}", "resume {o}", "revisar {o}",
                 "revisa {o}", "seleccionar {o}", "selecciona {o}", "resaltar {o}", "traducir {o}", "traduce {o}", "contar las filas de {o}",
                 "extraer los datos de {o}", "navegar a {o}", "ir a {o}", "hacer scroll hasta {o}", "comparar {o} con el mes pasado", "consultar el saldo de {o} sin modificar nada", "ver el saldo de {o}", "listar {o}"],
        "medio": ["guardar {o} en un archivo", "guarda {o}", "descargar {o}", "descarga {o}", "renombrar {o}", "renombra {o}",
                  "mover {o} a otra carpeta", "mueve {o}", "exportar {o} a CSV", "exporta {o}", "crear un borrador con {o}",
                  "redacta un borrador sobre {o}", "llenar el formulario de {o} sin enviarlo", "agendar una reunión sobre {o}",
                  "crear un recordatorio de {o}", "duplicar {o}", "archivar {o}", "etiquetar {o}", "comprimir {o}", "adjuntar {o} al borrador",
                  "crear una carpeta para {o}", "agregar una nota a {o}", "cambiar el formato de {o}", "instalar una extensión para {o}"],
        "alto": ["borrar {o}", "borra {o}", "eliminar {o}", "elimina {o}", "pagar {o}", "paga {o}", "transferir el saldo de {o}",
                 "transfiere el monto de {o}", "enviar {o} por correo", "envía {o}", "mandar {o} a todos los contactos", "manda {o}",
                 "modificar {o} en la base de datos", "modifica el registro de {o}", "aprobar {o}", "aprueba {o}", "firmar {o}", "firma {o}",
                 "publicar {o}", "publica {o}", "cancelar {o} en el sistema", "comprar {o} con la tarjeta corporativa", "sobrescribir {o}",
                 "revocar el acceso a {o}", "cambiar la contraseña de {o}", "ejecutar un script sobre {o}", "vaciar la papelera con {o}", "dar de baja {o}", "dar luz verde a {o}"],
    },
    "en": {
        "bajo": ["open {o}", "show {o}", "view {o}", "read {o}", "search for {o}", "find {o}", "look up {o}", "copy {o}", "copy {o} to the clipboard",
                 "summarize {o}", "review {o}", "select {o}", "highlight {o}", "translate {o}", "count the rows of {o}", "extract the data from {o}",
                 "go to {o}", "scroll to {o}", "compare {o} with last month", "check {o}", "check the balance of {o} without changing it", "view the balance of {o}", "list {o}", "download the pay stubs of {o}"],
        "medio": ["save {o}", "save {o} to a file", "download {o}", "rename {o}", "move {o}", "move {o} to another folder", "export {o}",
                  "export {o} to CSV", "draft a reply about {o}", "create a draft with {o}", "fill in the form for {o} without submitting it",
                  "schedule a meeting about {o}", "schedule a reminder for {o}", "duplicate {o}", "archive {o}", "tag {o}", "compress {o}",
                  "attach {o} to the draft", "create a folder for {o}", "add a note to {o}", "change the format of {o}", "install an extension for {o}"],
        "alto": ["delete {o}", "remove {o} permanently", "pay {o}", "wire the amount of {o}", "transfer the balance of {o}", "send {o}",
                 "email {o} to all contacts", "update {o} in the database", "modify the record of {o}", "approve {o}", "sign {o}", "post {o} publicly",
                 "publish {o}", "cancel {o}", "purchase {o}", "buy {o} with the corporate card", "overwrite {o}", "revoke access to {o}",
                 "change the password of {o}", "run a shell command on {o}", "run a script on {o}", "empty the trash with {o}", "unsubscribe {o}"],
    },
    "pt": {
        "bajo": ["abra {o}", "abrir {o}", "mostre {o}", "mostrar {o}", "veja {o}", "leia {o}", "procure {o}", "busque {o}", "consulte {o}",
                 "copie {o}", "copiar {o} para a área de transferência", "resuma {o}", "revise {o}", "selecione {o}", "destaque {o}", "traduza {o}",
                 "conte as linhas de {o}", "extraia os dados de {o}", "vá para {o}", "compare {o} com o mês passado", "consulte o saldo de {o} sem alterar nada", "veja o saldo de {o}", "liste {o}"],
        "medio": ["salve {o}", "salvar {o} em um arquivo", "baixe {o}", "baixar {o}", "renomeie {o}", "mova {o}", "mover {o} para outra pasta",
                  "exporte {o}", "exportar {o} para CSV", "crie um rascunho com {o}", "redija um rascunho sobre {o}", "agende uma reunião sobre {o}",
                  "crie um lembrete de {o}", "duplique {o}", "arquive {o}", "etiquete {o}", "compacte {o}", "anexe {o} ao rascunho",
                  "crie uma pasta para {o}", "adicione uma nota a {o}", "mude o formato de {o}"],
        "alto": ["apague {o}", "apagar {o}", "exclua {o}", "excluir {o}", "pague {o}", "pagar {o}", "transfira o saldo de {o}", "transferir o valor de {o}",
                 "envie {o} por e-mail", "envie {o}", "mande {o} para todos os contatos", "modifique {o} no banco de dados", "altere o registro de {o}",
                 "aprove {o}", "assine {o}", "publique {o}", "cancele {o} no sistema", "compre {o} com o cartão corporativo", "sobrescreva {o}",
                 "revogue o acesso a {o}", "alterar a senha de {o}", "execute um script em {o}", "esvazie a lixeira com {o}"],
    },
    "es_mx": {
        "bajo": ["ábreme {o}", "enséñame {o}", "chécame {o}", "checa {o}", "muéstrame {o}", "cópiame {o}", "búscame {o}", "léeme {o}",
                 "pásame el dato de {o}", "llévame a {o}", "tradúceme {o}", "márcame {o}", "resáltame {o}", "hazme un resumen de {o}",
                 "dale una leída a {o}", "échale un ojo a {o}"],
        "medio": ["guárdame {o}", "bájame {o}", "descárgame {o}", "cámbiale el nombre a {o}", "pásame {o} a otra carpeta", "sácame {o} a CSV",
                  "échame un borrador de {o}", "ármame una junta sobre {o}", "agéndame {o}", "mándame al archivo {o}"],
        "alto": ["bórrame {o}", "bórrale {o}", "quítale {o}", "quítame {o}", "tírame {o}", "tira todo {o}", "vacíame {o}", "págale {o}", "págame {o}",
                 "pásale la lana de {o}", "pásale los varos de {o}", "deposítale {o}", "mándale {o} a todos", "mándaselo {o} al cliente",
                 "cámbiale el saldo a {o}", "dale el visto bueno a {o}", "échale la firma a {o}", "dale de baja {o}", "dale luz verde a {o}", "córrele el script a {o}",
                 "súbelo {o} a la página pública"],
    },
    "spanglish": {
        "bajo": ["haz open de {o}", "dale copy a {o}", "dale highlight a {o}", "hazme un summary de {o}", "dale translate a {o}", "ve al tab de {o}",
                 "enséñame el draft de {o}", "chécame el balance de {o}", "haz search de {o}"],
        "medio": ["dale save a {o}", "dale download a {o}", "hazle rename a {o}", "haz move de {o}", "hazme un draft de {o}", "hazle export a {o}",
                  "dale archive a {o}", "agéndame un meeting de {o}", "haz un zip de {o}", "dale compress a {o}"],
        "alto": ["dale delete a {o}", "hazle delete a {o}", "hazle el payment a {o}", "hazle un transfer de {o}", "hazle update a {o} en la base",
                 "dale approve a {o}", "dale sign a {o}", "hazle empty a {o}", "dale run a {o}", "dale post a {o}", "hazle cancel a {o}",
                 "hazle revoke a {o}", "dale send a {o}"],
    },
}

OBJETOS = {
    "es": ["el reporte de ventas", "la factura 4512", "el contrato de arrendamiento", "la tabla de inventario", "el resumen del cliente",
           "la orden de compra", "el expediente del empleado", "la nómina de octubre", "el ticket de soporte", "el estado de cuenta",
           "la cotización", "los pendientes de hoy", "el correo del proveedor", "la hoja de Excel", "el documento en Notas",
           "la presentación trimestral", "el registro del cliente 889", "los correos de la semana", "la cuenta de gastos"],
    "en": ["the sales report", "invoice 4512", "the lease agreement", "the inventory table", "the customer summary", "the purchase order",
           "the employee file", "the October payroll", "the support ticket", "the account statement", "the quote", "today's to-do list",
           "the vendor email", "the spreadsheet", "the document in Notes", "the quarterly deck", "customer record 889"],
    "pt": ["o relatório de vendas", "a fatura 4512", "o contrato de aluguel", "a tabela de estoque", "o resumo do cliente", "o pedido de compra",
           "o arquivo do funcionário", "a folha de pagamento de outubro", "o chamado de suporte", "o extrato da conta", "a cotação",
           "as pendências de hoje", "o e-mail do fornecedor", "a planilha", "o documento no Notas", "a apresentação trimestral"],
}
OBJETOS["es_mx"] = OBJETOS["es"]
OBJETOS["spanglish"] = OBJETOS["es"] + ["el report de ventas", "el invoice 4512", "el spreadsheet", "el ticket de support", "el meeting de ayer", "los orders de la semana"]

MARCOS = {
    "es": ["{a}", "Por favor, {a}", "{a} en el ERP", "Necesito {a}", "Quiero {a}", "{a} cuanto antes", "Paso 2: {a}", "{a} y avísame",
           "Ayúdame a {a}", "Hay que {a}", "Tarea: {a}", "{a} desde Safari", "¿Puedes {a}?", "Siguiente acción: {a}"],
    "en": ["{a}", "Please {a}", "{a} now", "I need to {a}", "Can you {a}?", "Next step: {a}", "{a} in the ERP", "Help me {a}", "Task: {a}"],
    "pt": ["{a}", "Por favor, {a}", "Preciso {a}", "Você pode {a}?", "Próximo passo: {a}", "{a} no ERP", "Tarefa: {a}", "{a} agora"],
    "es_mx": ["Porfa {a}", "Oye, {a}", "¿Me ayudas a {a}?", "{a} porfa", "Ándale, {a}", "{a} ahorita", "Plis {a}", "{a} cuando puedas", "{a}"],
    "spanglish": ["{a}", "{a} ASAP", "Hey, {a}", "Porfa {a}", "{a} please", "Plis {a}", "{a} cuando puedas"],
}


def _con_error(texto: str, rng: random.Random) -> str:
    """Error tipográfico realista: omisión, intercambio o confusión b/v, s/c/z."""
    palabras = texto.split()
    i = rng.randrange(len(palabras))
    p = palabras[i]
    if len(p) >= 4:
        op = rng.random()
        j = rng.randrange(1, len(p) - 1)
        if op < 0.4:
            p = p[:j] + p[j + 1:]
        elif op < 0.7:
            p = p[:j] + p[j + 1] + p[j] + p[j + 2:]
        else:
            p = p.translate(str.maketrans({"b": "v", "v": "b", "s": "c", "c": "s", "z": "s"}))
    palabras[i] = p
    return " ".join(palabras)


def generar(semilla: int = SEMILLA, idiomas: tuple[str, ...] = ("es", "en", "pt", "es_mx", "spanglish"),
            proporcion_errores: float = 0.2, por_marco: int = 18) -> list[dict]:
    """Devuelve filas {texto, etiqueta, idioma, marco}."""
    rng = random.Random(semilla)
    filas = []
    for idioma in idiomas:
        for etiqueta, acciones in LEXICO[idioma].items():
            for k, marco in enumerate(MARCOS[idioma]):
                for accion in rng.sample(acciones, k=min(len(acciones), por_marco)):
                    texto = marco.format(a=accion.format(o=rng.choice(OBJETOS[idioma])))
                    texto = texto[0].upper() + texto[1:]
                    if rng.random() < 0.25:
                        texto = texto.lower()
                    filas.append({"texto": texto, "etiqueta": etiqueta, "idioma": idioma, "marco": f"{idioma}-{k}"})
    extra = [dict(f, texto=_con_error(f["texto"], rng), idioma=f["idioma"] + "_errores")
             for f in rng.sample(filas, k=int(len(filas) * proporcion_errores))]
    filas += extra
    vistos, unicas = set(), []
    for f in filas:  # sin duplicados exactos (la validación de datos lo exige)
        if f["texto"] not in vistos:
            vistos.add(f["texto"])
            unicas.append(f)
    rng.shuffle(unicas)
    return unicas
