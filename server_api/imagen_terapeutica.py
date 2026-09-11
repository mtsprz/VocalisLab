"""VocalisLab Pro — Motor autónomo de imágenes terapéuticas.

Genera ilustraciones clínicas en arte de líneas (blanco y negro, fondo blanco)
para los ejercicios del cuadernillo, con fallback automático al dibujo
vectorial interno si no hay claves configuradas.

Orden de proveedores:
  1. Gemini Flash Image / Nano Banana (GEMINI_API_KEY) — GRATUITO con la key
     existente. Modelos: gemini-2.5-flash-image, gemini-2.0-flash-preview-image-generation.
  2. FAL.ai (FAL_KEY) — FLUX line art.
  3. Recraft V3 (RECRAFT_API_KEY) — style line_art.
  4. Replicate (REPLICATE_API_TOKEN) — modelo oficial FLUX.

Sin claves → devuelve None y el cuadernillo usa los pictogramas vectoriales.
Las imágenes se cachean en /tmp por hash del prompt (no se regeneran).
"""

PROMPT_BASE = ("Minimalist 2D medical line art illustration of {desc}, clean black "
               "strokes on white background, simple pedagogical style, vector icon "
               "style, no shading, no colors, high legibility --ar 1:1")

# Descripciones específicas obligatorias por ejercicio (inglés, estilo line-art)
IMG_DESC_POR_EJERCICIO = {
    "rotacion_hombros": "human upper torso showing neck side bend and shoulder roll arrows",
    "respiracion_abdominal": "human torso side-view showing abdominal expansion arrows during breathing",
    "tubo_agua": "clear glass with water, submerged silicone tube at 1.5 cm depth, bubbling effect",
    "popote_aire": "side profile of human mouth blowing through a thin straw in open air, no glass, no water",
    "humming_m": "side view of human face with gentle vibration lines around nasolabial and mask area",
    "frases_balanceadas": "person speaking clearly with expanding soundwave arcs extending forward 3 meters",
    "calentamiento": "three ascending warm-up steps for voice training with arrows going up",
    "enfriamiento": "three descending cool-down steps for voice training with arrows going down",
    "le_huche": "person breathing deeply with relaxed shoulders, respiratory cycle arrows",
    "shiatsu_cabeza": "head pressure points marked with dots on temples and jaw for self-massage",
    "masaje_laringeo": "hands gently massaging the front of the neck, laryngeal area",
    "descenso_laringeo": "wide yawn with open mouth showing lowered larynx arrow",
    "oclusion_succion": "lips sealed around a narrow straw sucking gently",
    "expansion_costo_lateral": "ribcage with lateral expansion arrows on lower ribs",
    "soplo_escalonado": "stepped ascending airflow blocks from whisper to voiced sound",
    "empuje_glotico": "two vocal folds closing firmly with inward arrows",
    "vibracion_labial": "lips vibrating with trill motion lines",
    "consonantes_fricativas": "teeth with continuous airflow producing v and z sounds",
    "escalas_vocalicas": "five ascending musical stairs with notes going up and down",
    "pautas_rlf": "inclined bed wedge pillow and clock showing no food 2.5 hours before sleep",
}

GEMINI_IMAGE_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-2.0-flash-preview-image-generation",
]


def _gemini_image_models():
    env = os.environ.get("GEMINI_IMAGE_MODEL", "").strip()
    if env:
        return [m.strip() for m in env.split(",") if m.strip()]
    return list(GEMINI_IMAGE_MODELS)


def _descripcion_ejercicio(exercise_id: str, nombre: str, descripcion: str) -> str:
    ex_id = str(exercise_id or "").strip().lower()
    if ex_id in IMG_DESC_POR_EJERCICIO:
        return IMG_DESC_POR_EJERCICIO[ex_id]
    base = (nombre or "vocal exercise").strip()
    if descripcion:
        base += f" ({descripcion[:120].strip()})"
    return f"speech therapy for voice: {base}"
import os
import hashlib
import tempfile
import traceback

CACHE_DIR = os.path.join(tempfile.gettempdir(), "vocalislab_img")
ESTILO_LINEA = ("Black and white line art vector, pure white background, "
                "high contrast, clinical illustration, no color, "
                "no background shadows")


def _cache_path(prompt: str, proveedor: str) -> str:
    h = hashlib.sha1(f"{proveedor}:{prompt}".encode()).hexdigest()[:16]
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{proveedor}_{h}.png")


def _descargar(url: str, destino: str, timeout: int = 60) -> bool:
    try:
        import httpx
        r = httpx.get(url, timeout=timeout, follow_redirects=True)
        if r.status_code == 200 and len(r.content) > 2000:
            with open(destino, "wb") as f:
                f.write(r.content)
            return True
    except Exception as e:
        print(f"[imagen_terapeutica] Descarga falló: {e}")
    return False


def _es_imagen_valida(path: str) -> bool:
    try:
        return os.path.exists(path) and os.path.getsize(path) > 2000
    except Exception:
        return False


def _prompt_ejercicio(nombre: str, descripcion: str) -> str:
    return PROMPT_BASE.format(desc=f"{nombre}. {descripcion[:220]}".strip())


def _via_gemini(prompt: str) -> str | None:
    """Nano Banana / Gemini Flash Image (gratuito con GEMINI_API_KEY)."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    try:
        import httpx
    except ImportError:
        return None
    for model in _gemini_image_models():
        try:
            r = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseModalities": ["IMAGE"]},
                },
                timeout=120,
            )
            if r.status_code != 200:
                print(f"[imagen_terapeutica] Gemini {model} {r.status_code}: {r.text[:200]}")
                continue
            for cand in (r.json().get("candidates") or []):
                for part in ((cand.get("content") or {}).get("parts") or []):
                    inline = part.get("inlineData") or part.get("inline_data") or {}
                    b64 = inline.get("data", "")
                    if b64:
                        import base64
                        dest = _cache_path(prompt, "gemini")
                        with open(dest, "wb") as f:
                            f.write(base64.b64decode(b64))
                        if _es_imagen_valida(dest):
                            return dest
            print(f"[imagen_terapeutica] Gemini {model}: sin imagen en respuesta")
        except Exception:
            traceback.print_exc()
            continue
    return None


def _via_fal(prompt: str) -> str | None:
    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        return None
    try:
        import httpx
        r = httpx.post(
            "https://fal.run/fal-ai/flux/schnell",
            headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
            json={"prompt": prompt, "image_size": "square", "num_images": 1},
            timeout=120,
        )
        if r.status_code != 200:
            print(f"[imagen_terapeutica] FAL {r.status_code}: {r.text[:200]}")
            return None
        data = r.json()
        imgs = data.get("images") or []
        if not imgs:
            return None
        dest = _cache_path(prompt, "fal")
        return dest if _descargar(imgs[0].get("url", ""), dest) else None
    except Exception:
        traceback.print_exc()
        return None


def _via_recraft(prompt: str) -> str | None:
    key = os.environ.get("RECRAFT_API_KEY", "").strip()
    if not key:
        return None
    try:
        import httpx
        r = httpx.post(
            "https://external.api.recraft.ai/v1/images/generations",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"prompt": prompt, "style": "line_art", "size": "1024x1024", "n": 1},
            timeout=120,
        )
        if r.status_code != 200:
            print(f"[imagen_terapeutica] Recraft {r.status_code}: {r.text[:200]}")
            return None
        data = r.json()
        items = data.get("data") or []
        if not items:
            return None
        dest = _cache_path(prompt, "recraft")
        url = items[0].get("url", "")
        if url:
            return dest if _descargar(url, dest) else None
        b64 = items[0].get("b64_json", "")
        if b64:
            import base64
            with open(dest, "wb") as f:
                f.write(base64.b64decode(b64))
            return dest if _es_imagen_valida(dest) else None
        return None
    except Exception:
        traceback.print_exc()
        return None


def _via_replicate(prompt: str) -> str | None:
    token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not token:
        return None
    model = os.environ.get("REPLICATE_MODEL", "black-forest-labs/flux-schnell").strip()
    try:
        import httpx
        import time
        r = httpx.post(
            f"https://api.replicate.com/v1/models/{model}/predictions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                      "Prefer": "wait"},
            json={"input": {"prompt": prompt, "aspect_ratio": "1:1"}},
            timeout=120,
        )
        if r.status_code not in (200, 201):
            print(f"[imagen_terapeutica] Replicate {r.status_code}: {r.text[:200]}")
            return None
        pred = r.json()
        for _ in range(24):
            status = pred.get("status")
            if status == "succeeded":
                out = pred.get("output")
                urls = out if isinstance(out, list) else [out]
                if urls and urls[0]:
                    dest = _cache_path(prompt, "replicate")
                    return dest if _descargar(urls[0], dest) else None
                return None
            if status in ("failed", "canceled"):
                print(f"[imagen_terapeutica] Replicate {status}: {pred.get('error')}")
                return None
            get_url = pred.get("urls", {}).get("get")
            if not get_url:
                return None
            time.sleep(5)
            pr = httpx.get(get_url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
            if pr.status_code != 200:
                return None
            pred = pr.json()
        return None
    except Exception:
        traceback.print_exc()
        return None


def proveedores_disponibles() -> list:
    provs = []
    if os.environ.get("FAL_KEY", "").strip():
        provs.append("fal")
    if os.environ.get("RECRAFT_API_KEY", "").strip():
        provs.append("recraft")
    if os.environ.get("REPLICATE_API_TOKEN", "").strip():
        provs.append("replicate")
    return provs


def generar_imagen_ejercicio(nombre: str, descripcion: str = "",
                            exercise_id: str = "") -> str | None:
    """Devuelve el path local de la ilustración IA, o None si no hay proveedor
    configurado o fallan todos (el cuadernillo usa el dibujo vectorial)."""
    desc = _descripcion_ejercicio(exercise_id, nombre or "ejercicio vocal",
                                  descripcion or "")
    prompt = PROMPT_BASE.format(desc=desc)
    dest = _cache_path(prompt, "gemini")
    if _es_imagen_valida(dest):
        return dest
    path = _via_gemini(prompt)
    if path and _es_imagen_valida(path):
        return path
    for prov, fn in (("fal", _via_fal), ("recraft", _via_recraft),
                     ("replicate", _via_replicate)):
        dest = _cache_path(prompt, prov)
        if _es_imagen_valida(dest):
            return dest
        path = fn(prompt)
        if path and _es_imagen_valida(path):
            return path
    return None


def generar_desde_boceto(boceto_bytes: bytes, nombre: str, descripcion: str = "") -> str | None:
    """Sketch-to-Image: refina un boceto del profesional a arte de líneas limpio.
    Usa FAL FLUX con imagen de referencia si hay clave; si no, devuelve None."""
    key = os.environ.get("FAL_KEY", "").strip()
    if not key or not boceto_bytes or len(boceto_bytes) < 500:
        return None
    try:
        import httpx
        import base64
        b64 = base64.b64encode(boceto_bytes).decode()
        data_url = f"data:image/png;base64,{b64}"
        prompt = (_prompt_ejercicio(nombre, descripcion)
                  + ". Redraw this exact sketch cleanly, keep the same composition.")
        r = httpx.post(
            "https://fal.run/fal-ai/flux-pro/v1/redraw",
            headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
            json={"prompt": prompt, "image_url": data_url, "strength": 0.75,
                  "image_size": "square"},
            timeout=180,
        )
        if r.status_code != 200:
            print(f"[imagen_terapeutica] Boceto FAL {r.status_code}: {r.text[:200]}")
            return None
        imgs = (r.json().get("images") or [])
        if not imgs:
            return None
        dest = _cache_path(prompt + ":boceto", "fal")
        return dest if _descargar(imgs[0].get("url", ""), dest) else None
    except Exception:
        traceback.print_exc()
        return None
