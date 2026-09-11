"""VocalisLab Pro — Motor autónomo de imágenes terapéuticas.

Genera ilustraciones clínicas en arte de líneas (blanco y negro, fondo blanco)
para los ejercicios del cuadernillo usando proveedores externos, con fallback
automático al dibujo vectorial interno si no hay claves configuradas.

Orden de proveedores (según claves presentes):
  1. FAL.ai (FAL_KEY) — FLUX line art
  2. Recraft V3 (RECRAFT_API_KEY) — style line_art
  3. Replicate (REPLICATE_API_TOKEN) — modelo oficial FLUX

Sin claves → devuelve None y el cuadernillo usa los pictogramas vectoriales.
Las imágenes se cachean en /tmp por hash del prompt (no se regeneran).
"""
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
    base = f"Clinical speech therapy illustration for the exercise '{nombre}'"
    if descripcion:
        base += f": {descripcion[:220]}"
    return f"{base}. Simple clear shapes for elderly patients. {ESTILO_LINEA}"


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


def generar_imagen_ejercicio(nombre: str, descripcion: str = "") -> str | None:
    """Devuelve el path local de la ilustración IA, o None si no hay proveedor
    configurado o fallan todos (el cuadernillo usa el dibujo vectorial)."""
    prompt = _prompt_ejercicio(nombre or "ejercicio vocal", descripcion or "")
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
