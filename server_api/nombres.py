"""Nombre de pila para saludar al paciente ("Hola León").

Los nombres llegan en dos órdenes:
- Agenda de Fonoar (mail): "ALVAREZ YESICA" → apellido primero.
- Cargados a mano o desde la planilla de canto: "León Murillo" → nombre primero.

Antes se tomaba siempre la última palabra, y "León Murillo" quedaba "Hola
Murillo". La regla usa el origen del paciente; el profesional igual puede
corregir el saludo antes de mandar el enlace.
"""


def nombre_para_saludo(nombre_completo: str, origen: str = "", tipo_atencion: str = "") -> str:
    palabras = [p for p in (nombre_completo or "").split() if p]
    if not palabras:
        return ""
    # Agenda de Fonoar: APELLIDO NOMBRE(S). Las clases de canto del mail vienen
    # al revés ("CLASE DE CANTO JUAN SORACCO"), así que no se invierten.
    if origen == "agenda_fonoar" and tipo_atencion != "canto" and len(palabras) >= 2:
        pila = " ".join(palabras[1:])
    else:
        pila = palabras[0]
    return " ".join(p.capitalize() for p in pila.split())


def saludo_de_paciente(fila: dict) -> str:
    return nombre_para_saludo(fila.get("nombre_completo") or fila.get("nombre") or "",
                              fila.get("origen") or "", fila.get("tipo_atencion") or "")
