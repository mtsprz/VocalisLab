"""Firma del profesional en todos los documentos impresos.

El profesional firma como "Fonoaudiólogo", nunca como licenciado. El nombre
puede venir con "Lic." desde datos guardados en el navegador (el valor por
defecto viejo era "Lic. Matias Perez"), así que se limpia siempre antes de
imprimir, en lugar de confiar en lo que llega.
"""
import re

NOMBRE_DEFECTO = "Matías Pérez"
TITULO_DEFECTO = "Fonoaudiólogo"

# "Lic.", "Lic", "Licenciado", "Licenciada", "Lic. en Fonoaudiología" al inicio.
_PREFIJO_LIC = re.compile(
    r"^\s*(?:lic(?:enciad[oa])?\.?)(?:\s+en\s+fonoaudiolog[ií]a)?[\s,.:-]*",
    re.IGNORECASE)
_MENCION_LIC = re.compile(r"\blic(?:enciad[oa]|enciatura)?\b\.?", re.IGNORECASE)


def limpiar_nombre(nombre: str, defecto: str = NOMBRE_DEFECTO) -> str:
    """Quita el tratamiento de licenciado del nombre ("Lic. Matias Perez" →
    "Matias Perez"). Vacío → nombre por defecto."""
    n = _PREFIJO_LIC.sub("", str(nombre or "")).strip()
    # El valor viejo guardado en el navegador venía sin tildes.
    if _sin_tildes(n).lower() == _sin_tildes(NOMBRE_DEFECTO).lower():
        return NOMBRE_DEFECTO
    return n or defecto


def _sin_tildes(texto: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def limpiar_titulo(titulo: str, defecto: str = TITULO_DEFECTO) -> str:
    """Cualquier título que mencione licenciatura pasa a "Fonoaudiólogo"."""
    t = str(titulo or "").strip()
    if not t or _MENCION_LIC.search(t):
        return defecto
    return t


# ─── Sin menciones a "IA" en lo que se imprime ───────────────────────
# El criterio clínico y los documentos son del profesional: ningún PDF dice
# "IA", "Prescripción IA" ni "generado por inteligencia artificial".
_IA = r"(?:IA|I\.A\.|inteligencia\s+artificial)"
# Leyendas completas del tipo "Interpretación generada por IA — Requiere...".
_LEYENDA_IA = re.compile(
    r"[^\n.]*\b(?:generad|asistid|redactad|elaborad|sintetizad|propuest)[oa]s?\s+"
    r"(?:por|con)\s+(?:la\s+)?" + _IA + r"\b[^\n]*", re.IGNORECASE)
# La palabra suelta en títulos ("Prescripción IA Fonoaudiológica").
_PALABRA_IA = re.compile(r"\s*\b(?:IA|I\.A\.)(?=\s|$|[^\w])")


def sin_mencion_ia(texto: str) -> str:
    """Quita leyendas "generado por IA" y la palabra IA de un texto impreso."""
    t = _LEYENDA_IA.sub("", str(texto or ""))
    t = _PALABRA_IA.sub("", t)
    t = re.sub(r"\(\s*\)", "", t)  # "(IA)" → "()" → nada
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()
