"""VocalisLab — Render del cuadernillo terapéutico (CUADERNILLO_SPEC.md §1).

Motor único: WeasyPrint (HTML/CSS + Jinja2).

Uso:
    python -m server_api.rendering.render \
        --fixture fixtures/prescripcion_a.json \
        --out out/cuadernillo.pdf [--png out/pages]
"""
import argparse
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HORARIO_HORAS = [f"{h:02d}:00" for h in range(7, 23)]
DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes",
               "Sábado", "Domingo"]


class PrescriptionError(Exception):
    """Dato de prescripción inválido: el PDF NUNCA se genera."""


def _req(obj: dict, key: str, donde: str) -> str:
    v = (obj or {}).get(key)
    if v is None or (isinstance(v, str) and not v.strip()):
        raise PrescriptionError(f"Falta campo requerido '{key}' en {donde}")
    return v


def validate_prescription(data: dict) -> None:
    """Valida el contrato de §2. Prohibidos los placeholders."""
    if not isinstance(data, dict):
        raise PrescriptionError("La prescripción debe ser un objeto JSON")
    pac = data.get("paciente") or {}
    _req(pac, "nombre", "paciente")
    pro = data.get("profesional") or {}
    for k in ("nombre", "matricula", "contacto"):
        _req(pro, k, "profesional")
    pre = data.get("prescripcion") or {}
    for k in ("titulo", "fecha_inicio", "sesiones", "frecuencia",
              "duracion_sesion_min"):
        _req(pre, k, "prescripcion")
    ejs = data.get("ejercicios") or []
    if not ejs:
        raise PrescriptionError("La prescripción no trae ejercicios")
    from .validators import validar_familias
    errores = validar_familias(ejs)
    for i, ex in enumerate(ejs):
        for k in ("codigo", "nombre", "familia", "para_que", "nivel",
                  "nivel_nombre", "dosis_min"):
            if ex.get(k) in (None, ""):
                errores.append(f"ejercicios[{i}]: falta '{k}' (requerido)")
        cons = ex.get("consignas") or []
        if not cons:
            errores.append(f"ejercicios[{i}]: sin consignas")
        if len(cons) > 9:
            errores.append(f"ejercicios[{i}]: {len(cons)} consignas (máx 9: "
                           f"dato a revisar con el profesional)")
        ml = (ex.get("micro_leyenda") or "").strip()
        if ml and len(ml.split()) > 6:
            errores.append(f"ejercicios[{i}]: micro_leyenda supera 6 palabras")
    if errores:
        raise PrescriptionError("Prescripción inválida:\n- " + "\n- ".join(errores))


def load_fixture(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_context(data: dict, svg_dir: str) -> dict:
    """Enriquece la prescripción para la plantilla (n, svg inline, oraciones)."""
    from .validators import ilustracion_para
    ejercicios = []
    for n, ex in enumerate(data["ejercicios"], 1):
        fam = ex["familia"]
        override = (ex.get("ilustracion") or "").strip()
        tabla_registro = (override == "tabla_registro")
        if tabla_registro:
            svg, caption = None, ""
        else:
            archivo, caption = ilustracion_para(fam, "", override)
            svg = None
            if archivo:  # higiene → sin ilustración (§6)
                with open(os.path.join(svg_dir, archivo),
                          encoding="utf-8") as f:
                    svg = f.read()
        ejercicios.append({
            "n": n,
            "codigo": ex["codigo"],
            "nombre": ex["nombre"],
            "familia": fam,
            "svg": svg,
            "tabla_registro": tabla_registro,
            "caption": caption,
            "para_que": ex["para_que"],
            "nota_tecnica": (ex.get("nota_tecnica") or "").strip(),
            "precaucion": (ex.get("precaucion") or "").strip(),
            "nivel": ex["nivel"],
            "nivel_nombre": ex["nivel_nombre"],
            "dosis_min": ex["dosis_min"],
            "micro_leyenda": (ex.get("micro_leyenda") or "").strip(),
            "consignas": list(ex["consignas"]),
        })
    frases = ((data.get("anexos") or {}).get("frases") or [])[:8]
    oraciones = [{"texto": (f.get("texto") or ""),
                  "contexto": (f.get("contexto") or "")} for f in frases]
    while len(oraciones) < 8:
        oraciones.append({"texto": "", "contexto": ""})
    return {
        "paciente": data["paciente"],
        "profesional": data["profesional"],
        "prescripcion": data["prescripcion"],
        "ejercicios": ejercicios,
        "anexos": data.get("anexos") or {},
        "oraciones": oraciones,
        "horario_horas": HORARIO_HORAS,
        "dias_semana": DIAS_SEMANA,
    }


def render_html(data: dict, svg_dir: str) -> str:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(
        loader=FileSystemLoader(BASE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template("cuadernillo.html")
    return tpl.render(**build_context(data, svg_dir))


def render_pdf(data: dict, svg_dir: str, out_pdf: str) -> int:
    """Renderiza el PDF. Devuelve cantidad de páginas."""
    from weasyprint import HTML
    os.makedirs(os.path.dirname(os.path.abspath(out_pdf)), exist_ok=True)
    html = render_html(data, svg_dir)
    doc = HTML(string=html, base_url=BASE_DIR).write_pdf(out_pdf)
    del doc
    from pypdf import PdfReader
    return len(PdfReader(out_pdf).pages)


def render_pngs(pdf_path: str, out_dir: str, dpi: int = 110) -> list:
    import fitz
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    paths = []
    for i in range(len(doc)):
        p = os.path.join(out_dir, f"p-{i + 1:02d}.png")
        doc.load_page(i).get_pixmap(dpi=dpi).save(p)
        paths.append(p)
    doc.close()
    return paths


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Render del cuadernillo vocal")
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--png", default="")
    args = ap.parse_args(argv)

    try:
        data = load_fixture(args.fixture)
        validate_prescription(data)
    except PrescriptionError as e:
        print(f"ERROR de prescripción: {e}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR leyendo fixture: {e}", file=sys.stderr)
        return 2

    svg_dir = os.path.join(BASE_DIR, "svg")
    try:
        paginas = render_pdf(data, svg_dir, args.out)
    except Exception as e:
        print(f"ERROR renderizando PDF: {e}", file=sys.stderr)
        return 1
    print(f"PDF OK: {args.out} ({paginas} páginas, "
          f"{len(data['ejercicios'])} ejercicios)")

    if "prescripcion_a" in os.path.basename(args.fixture) and paginas > 14:
        print(f"AVISO densidad: fixture_a con {paginas} páginas (presupuesto "
              f"≤ 14). Revisar densidad antes de achicar tipografía.")

    if args.png:
        try:
            paths = render_pngs(args.out, args.png)
            print(f"PNG OK: {len(paths)} páginas en {args.png}/")
        except Exception as e:
            print(f"ERROR rasterizando PNG: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
