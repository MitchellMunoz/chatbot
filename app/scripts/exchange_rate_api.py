import requests
from datetime import datetime
from decimal import Decimal
from xml.etree import ElementTree

#banco de guatemala only speaks soap, the request is a posted xml envelope
URL = "https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx"

SOAP_ACTION = "http://www.banguat.gob.gt/variables/ws/TipoCambioRango"

NAMESPACE = "{http://www.banguat.gob.gt/variables/ws/}"

#TipoCambioDia only publishes referencia, this is the call that gives venta
BODY = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <TipoCambioRango xmlns="http://www.banguat.gob.gt/variables/ws/">
      <fechainit>{start_date}</fechainit>
      <fechafin>{end_date}</fechafin>
    </TipoCambioRango>
  </soap:Body>
</soap:Envelope>"""


def get_exchange_rates(start_date, end_date):
    #banguat reads and writes dates as dd/mm/yyyy
    body = BODY.format(
        start_date=start_date.strftime("%d/%m/%Y"),
        end_date=end_date.strftime("%d/%m/%Y"),
    )
    response = requests.post(
        URL,
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": SOAP_ACTION,
        },
        timeout=30,
    )
    response.raise_for_status()

    tree = ElementTree.fromstring(response.text)

    #banguat answers with one Var node per day, weekends and holidays are skipped
    rates = []
    for var in tree.iter(f"{NAMESPACE}Var"):
        fecha = var.find(f"{NAMESPACE}fecha").text
        venta = var.find(f"{NAMESPACE}venta").text
        rates.append({
            "date": datetime.strptime(fecha, "%d/%m/%Y").date(),
            "venta": Decimal(venta),
        })
    return rates
