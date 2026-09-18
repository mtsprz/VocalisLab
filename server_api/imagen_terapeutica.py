"""VocalisLab Pro — Motor autónomo de imágenes terapéuticas.

Genera ilustraciones clínicas en arte de líneas (blanco y negro, fondo blanco)
para los ejercicios del cuadernillo, con fallback automático al dibujo
vectorial interno si no hay claves configuradas.

Orden de proveedores:
  0. Cloudflare Workers AI (CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN) —
     modelo vía CLOUDFLARE_MODEL, default FLUX.1 Schnell (alta coherencia
     anatómica; SDXL-Lightning solo si se fuerza por env).
  1. Wavespeed (WAVESPEED_API_KEY) — z-image/turbo (o WAVESPEED_MODEL).
  2. Pixazo (PIXAZO_API_KEY) — Flux Schnell vía gateway (probado end-to-end).
  3. Gemini Flash Image / Nano Banana (GEMINI_API_KEY) — gratuito.
  4. FAL.ai (FAL_KEY) — FLUX line art.
  5. Recraft V3 (RECRAFT_API_KEY) — style line_art.
  6. Replicate (REPLICATE_API_TOKEN) — modelo oficial FLUX.

Estilo (vía ESTILO_IMAGEN o parámetro): '3d_vector' (default, ilustración
médica 3D) o 'vector_2d' (diagrama clínico plano). Fotorrealismo PROHIBIDO en
toda la app (directiva clínica 2026). Todos los prompts exigen anatomía correcta,
fondo blanco puro y prohíben texto/marcas de agua; SD de base usa prompt negativo.

Sin claves → devuelve None y el cuadernillo usa los pictogramas vectoriales.
Las imágenes se cachean en /tmp por hash del prompt (no se regeneran).
"""

PROMPT_BASE = ("Medical 3D vector diagram of {desc}, minimalist clinical style, clean lines, "
               "professional anatomical accuracy, pure white background #FFFFFF, "
               "medical textbook illustration style, 8k, soft shadows, "
               "institutional blue and lavender accents, no text, no labels, no watermark")

# Modo diagrama médico 3D/2D vectorial (reemplaza cualquier estilo fotorrealista prohibido)
PROMPT_REALISTA_BASE = PROMPT_BASE

# Prompt negativo mandatorio estricto
NEGATIVO_CLINICO = ("photorealistic, real human photo, real skin, photographic, cinematic photo, "
                    "extra fingers, mutated hands, deformed fingers, 6 fingers, floating hands, dislocated limbs, "
                    "distorted anatomy, text, labels, gibberish writing, letters, words, blurry, "
                    "noisy background, realistic faces, room background, furniture, shadows on wall")

# Descripciones específicas por ejercicio (inglés, encuadre diagrama clínico;
# se prefiere objeto/esquema sobre persona para evitar rostros y manos IA)
IMG_DESC_POR_EJERCICIO = {
    "rotacion_hombros": "upper torso vector diagram showing neck side bend and shoulder roll direction arrows",
    "respiracion_abdominal": "torso side-view vector diagram showing abdominal expansion arrows during breathing",
    "tubo_agua": "clear glass with water, submerged silicone tube at 1.5 cm depth, bubbling effect, no hands",
    "popote_aire": "thin straw in open air with airflow lines, side-view mouth silhouette diagram, no glass, no water",
    "humming_m": "head profile vector diagram with vibration highlight on nasolabial and mask area",
    "frases_balanceadas": "head profile silhouette with expanding soundwave arcs extending forward",
    "calentamiento": "three ascending warm-up steps diagram for voice training with arrows going up",
    "enfriamiento": "three descending cool-down steps diagram for voice training with arrows going down",
    "le_huche": "torso vector diagram of breathing cycle with relaxed shoulders and airflow arrows",
    "shiatsu_cabeza": "head vector diagram with pressure point dots on temples and jaw for self-massage",
    "masaje_laringeo": "3D medical vector diagram of correct hand placement on the front of the neck, laryngeal area",
    "descenso_laringeo": "head profile vector diagram of wide yawn with lowered larynx arrow",
    "oclusion_succion": "lip silhouette diagram sealed around a narrow straw",
    "expansion_costo_lateral": "ribcage vector diagram with lateral expansion arrows on lower ribs",
    "soplo_escalonado": "stepped ascending airflow blocks diagram from whisper to voiced sound",
    "empuje_glotico": "vocal folds vector diagram closing firmly with inward arrows, top view",
    "vibracion_labial": "lip vector diagram with trill motion lines",
    "consonantes_fricativas": "teeth vector diagram with continuous airflow lines producing v and z sounds",
    "escalas_vocalicas": "five ascending musical stairs diagram with notes going up and down",
    "pautas_rlf": "inclined bed wedge pillow vector diagram and clock icon showing no food 2.5 hours before sleep",
    "oclusion_nasal": "nose and lip vector diagram showing nasal resonance placement with /m/ airflow",
    "coordinacion_costo_abdominal": "torso vector diagram showing coordinated abdominal and rib airflow with /s/ and /z/ flow lines",
    "glissandos": "smooth ascending and descending pitch curve diagram, siren line, no text",
}

GEMINI_IMAGE_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-2.0-flash-preview-image-generation",
]

# Modelos Cloudflare Workers AI (texto→imagen). FLUX.1 Schnell por defecto:
# muy superior en coherencia anatómica al SDXL-Lightning de 4 pasos.
CLOUDFLARE_IMAGE_MODELS = [
    "@cf/black-forest-labs/flux-1-schnell",
    "@cf/bytedance/stable-diffusion-xl-lightning",
    "@cf/stabilityai/stable-diffusion-xl-base-1.0",
]


def _cloudflare_model() -> str:
    env = os.environ.get("CLOUDFLARE_MODEL", "").strip()
    return env or CLOUDFLARE_IMAGE_MODELS[0]


def _estilo_imagen() -> str:
    """Estilo global canónico: '3d_vector' (default) o 'vector_2d'.
    Se puede forzar con la env ESTILO_IMAGEN. Legacy 'realista'→3d_vector,
    'lineart'→vector_2d (ver mediacion_clinica.normalizar_estilo)."""
    from mediacion_clinica import normalizar_estilo
    return normalizar_estilo(os.environ.get("ESTILO_IMAGEN", "3d_vector"))


def _prompt_clinico(desc: str, estilo: str = "") -> str:
    """Compat: envuelve la descripción en el template vectorial del estilo pedido."""
    from mediacion_clinica import normalizar_estilo, PROMPT_3D_VECTOR, PROMPT_2D_VECTOR
    est = normalizar_estilo(estilo or _estilo_imagen())
    template = PROMPT_2D_VECTOR if est == "vector_2d" else PROMPT_3D_VECTOR
    return template.format(detalle=desc, reglas_cat="")  # reglas las aporta la mediación


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


def _cache_path(prompt: str, proveedor: str, ext: str = "png") -> str:
    h = hashlib.sha1(f"{proveedor}:{prompt}".encode()).hexdigest()[:16]
    os.makedirs(CACHE_DIR, exist_ok=True)
    ext = (ext or "png").strip().lstrip(".").lower() or "png"
    return os.path.join(CACHE_DIR, f"{proveedor}_{h}.{ext}")


def _sniff_ext(raw: bytes) -> str:
    """Detecta la extensión real por magic bytes (Workers AI devuelve
    PNG binario o JPEG en base64 dentro de JSON según el modelo)."""
    if raw[:2] == b"\xff\xd8":
        return "jpg"
    if raw[:4] == b"\x89PNG":
        return "png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    return "png"


def _extraer_imagen_cf(payload, ctype: str = ""):
    """Extrae (ext, bytes) de una respuesta de Workers AI.
    Soporta: binario image/*, {"result": {"image": "<b64>"}},
    {"result": "<b64>"}, {"image"/"data": "<b64>"}. Devuelve (None, None)
    si no hay imagen."""
    import base64 as _b64
    raw = None
    if isinstance(payload, (bytes, bytearray)) and "image" in (ctype or ""):
        raw = bytes(payload)
    elif isinstance(payload, dict):
        res = payload.get("result", None)
        cand = ""
        if isinstance(res, dict):
            cand = res.get("image", "") or ""
        elif isinstance(res, str):
            cand = res
        if not (isinstance(cand, str) and len(cand) > 1000):
            for key in ("image", "data"):
                val = payload.get(key)
                if isinstance(val, str) and len(val) > 1000:
                    cand = val
                    break
        if isinstance(cand, str) and len(cand) > 1000:
            # Puede venir como data URL o base64 puro
            if "," in cand and cand.startswith("data:"):
                cand = cand.split(",", 1)[1]
            try:
                raw = _b64.b64decode(cand)
            except Exception:
                raw = None
    if raw and len(raw) > 2000:
        return _sniff_ext(raw), raw
    return None, None


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


def _prompt_ejercicio(nombre: str, descripcion: str, exercise_id: str = "") -> str:
    # Usa la descripción específica por ejercicio (no el nombre genérico)
    # para que la IA ilustre el contenido real y no un título histórico.
    desc = _descripcion_ejercicio(exercise_id, nombre or "ejercicio vocal",
                                 descripcion or "")
    return PROMPT_BASE.format(desc=desc[:300].strip())


def _via_cloudflare(prompt: str, desc_fallback: str = "",
                      negative: str = "") -> str | None:
    """Cloudflare Workers AI — modelo configurable vía CLOUDFLARE_MODEL
    (default: FLUX.1 Schnell, alta coherencia anatómica).
    Responde binario image/png o JSON con b64 anidado según el modelo.
    Si el filtro NSFW (8007) bloquea el prompt realista, reintenta una vez
    con el template line-art ("diagram/illustration"), que el filtro acepta.
    Gratuito con tu cuenta Cloudflare."""
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not (account and token):
        return None
    try:
        import httpx
        model = _cloudflare_model()

        def _body(p: str) -> dict:
            b: dict = {"prompt": p}
            # Los Stable Diffusion aceptan prompt negativo y pasos; FLUX no.
            if "stable-diffusion" in model and "lightning" not in model:
                b["negative_prompt"] = negative or NEGATIVO_CLINICO
                try:
                    steps = int(os.environ.get("CLOUDFLARE_STEPS", "30"))
                    b["num_steps"] = max(1, min(steps, 50))
                except Exception:
                    pass
            return b

        def _post(p: str):
            return httpx.post(
                f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=_body(p),
                timeout=180,
            )

        dest = None
        for _ext in ("png", "jpg", "webp"):
            _cand = _cache_path(f"{model}:{prompt}", "cloudflare", _ext)
            if _es_imagen_valida(_cand):
                return _cand
        r = _post(prompt)
        if r.status_code != 200 and "8007" in r.text and desc_fallback:
            from mediacion_clinica import mediar_prompt as _mediar
            alt = _mediar(desc_fallback, "", "vector_2d")["prompt"]
            if alt != prompt:
                print("[imagen_terapeutica] Cloudflare filtro NSFW (8007), reintentando vector 2D")
                prompt = alt
                r = _post(prompt)
        if r.status_code != 200:
            print(f"[imagen_terapeutica] Cloudflare {r.status_code}: {r.text[:200]}")
            return None
        ctype = r.headers.get("content-type", "")
        if "image" in ctype:
            ext, raw = _extraer_imagen_cf(r.content, ctype)
        else:
            try:
                ext, raw = _extraer_imagen_cf(r.json(), ctype)
            except Exception:
                ext, raw = None, None
        if not raw:
            print(f"[imagen_terapeutica] Cloudflare no devolvió imagen: {ctype} ({len(r.content)} bytes)")
            return None
        dest = _cache_path(f"{model}:{prompt}", "cloudflare", ext or "png")
        with open(dest, "wb") as f:
            f.write(raw)
        return dest if _es_imagen_valida(dest) else None
    except Exception:
        traceback.print_exc()
        return None


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


PROMPT_3D_BASE = ("Medical 3D vector diagram of {desc}, minimalist clinical style, "
                  "clean lines, professional anatomical accuracy, pure white background, "
                  "medical textbook illustration style, 8k, soft shadows, no text, no labels")


def _estilo_pixazo() -> str:
    return os.environ.get("PIXAZO_STYLE", "lineart").strip().lower()


def _via_wavespeed(prompt: str) -> str | None:
    """Wavespeed gateway: submit + polling hasta COMPLETED."""
    key = os.environ.get("WAVESPEED_API_KEY", "").strip()
    if not key:
        return None
    model = os.environ.get("WAVESPEED_MODEL", "wavespeed-ai/z-image/turbo").strip()
    try:
        import httpx
        import time
        r = httpx.post(
            f"https://api.wavespeed.ai/api/v3/{model}",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"prompt": prompt, "size": "1024*1024"},
            timeout=60,
        )
        if r.status_code != 200:
            print(f"[imagen_terapeutica] Wavespeed submit {r.status_code}: {r.text[:200]}")
            return None
        body = r.json()
        if body.get("code") != 200:
            print(f"[imagen_terapeutica] Wavespeed error: {str(body)[:200]}")
            return None
        get_url = ((body.get("data") or {}).get("urls") or {}).get("get", "")
        if not get_url:
            return None
        for _ in range(25):
            time.sleep(6)
            g = httpx.get(get_url, headers={"Authorization": f"Bearer {key}"}, timeout=30)
            if g.status_code != 200:
                continue
            gd = g.json()
            data = gd.get("data") or {}
            if data.get("status") == "completed":
                outs = data.get("outputs") or []
                if outs and outs[0]:
                    dest = _cache_path(prompt, "wavespeed")
                    return dest if _descargar(outs[0], dest, timeout=90) else None
                return None
            if data.get("status") in ("failed", "error"):
                print(f"[imagen_terapeutica] Wavespeed falló: {str(gd)[:200]}")
                return None
        print("[imagen_terapeutica] Wavespeed timeout esperando imagen")
        return None
    except Exception:
        traceback.print_exc()
        return None


def _via_pixazo(prompt: str, prompt_3d: str = "") -> str | None:
    """Pixazo gateway (Flux Schnell). Síncrono: devuelve URL directa."""
    key = os.environ.get("PIXAZO_API_KEY", "").strip()
    if not key:
        return None
    try:
        import httpx
        texto = prompt_3d if _estilo_pixazo() == "3d" and prompt_3d else prompt
        prov = "pixazo3d" if (prompt_3d and _estilo_pixazo() == "3d") else "pixazo"
        dest = _cache_path(texto, prov)
        if _es_imagen_valida(dest):
            return dest
        r = httpx.post(
            "https://gateway.pixazo.ai/flux-1-schnell/v1/getData",
            headers={"Content-Type": "application/json", "Cache-Control": "no-cache",
                      "Ocp-Apim-Subscription-Key": key},
            json={"prompt": texto},
            timeout=180,
        )
        if r.status_code != 200:
            print(f"[imagen_terapeutica] Pixazo {r.status_code}: {r.text[:200]}")
            return None
        url = (r.json().get("output") or "")
        if not url:
            return None
        return dest if _descargar(url, dest, timeout=90) else None
    except Exception:
        traceback.print_exc()
        return None


def _via_pollinations(prompt: str) -> str | None:
    """Pollinations.ai — gratuito, sin key. Flux con nologo."""
    try:
        import httpx
        import urllib.parse
        dest = _cache_path(prompt, "pollinations")
        if _es_imagen_valida(dest):
            return dest
        q = urllib.parse.quote(prompt[:1500])
        url = (f"https://image.pollinations.ai/prompt/{q}"
               "?width=1024&height=1024&model=flux&nologo=true&seed=7")
        r = httpx.get(url, timeout=180, follow_redirects=True)
        ctype = r.headers.get("content-type", "")
        if r.status_code != 200 or "image" not in ctype or len(r.content) < 2000:
            print(f"[imagen_terapeutica] Pollinations {r.status_code}: {ctype}")
            return None
        with open(dest, "wb") as f:
            f.write(r.content)
        return dest if _es_imagen_valida(dest) else None
    except Exception:
        traceback.print_exc()
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


def _supabase():
    try:
        from supabase import create_client
        url = __import__("os").environ.get("SUPABASE_URL", "")
        key = __import__("os").environ.get("SUPABASE_SERVICE_KEY",
                                           __import__("os").environ.get("SUPABASE_ANON_KEY", ""))
        if url and key:
            return create_client(url, key)
    except Exception as e:
        print(f"[imagen_terapeutica] Supabase no disponible: {e}")
    return None


BUCKET = "ejercicios"


def _ensure_bucket(sb) -> bool:
    try:
        sb.storage.get_bucket(BUCKET)
        return True
    except Exception:
        try:
            sb.storage.create_bucket(BUCKET, options={"public": True})
            return True
        except Exception as e:
            print(f"[imagen_terapeutica] No se pudo crear bucket: {e}")
            return False


def buscar_imagen_guardada(exercise_id: str) -> str | None:
    """Devuelve el path local de la imagen persistida para el ejercicio, o None.
    1) Fila en ejercicio_imagenes → 2) descarga de Storage a caché local."""
    ex_id = str(exercise_id or "").strip().lower()
    if not ex_id:
        return None
    sb = _supabase()
    if not sb:
        return None
    try:
        res = sb.table("ejercicio_imagenes").select("image_url, storage_path")\
            .eq("exercise_id", ex_id).limit(1).execute()
        rows = res.data or []
        if not rows:
            return None
        row = rows[0]
        # 1) caché local por hash estable del exercise_id
        dest = _cache_path(f"ejercicio:{ex_id}", "db")
        if _es_imagen_valida(dest):
            return dest
        # 2) descargar desde la URL persistida
        url = row.get("image_url", "")
        if url and _descargar(url, dest, timeout=60):
            return dest
        return None
    except Exception as e:
        print(f"[imagen_terapeutica] Lookup DB falló: {e}")
        return None


def guardar_imagen_ejercicio(exercise_id: str, local_path: str, prompt: str = "",
                             proveedor: str = "") -> str | None:
    """Sube la imagen a Storage y la asocia al ejercicio. Devuelve la URL pública."""
    ex_id = str(exercise_id or "").strip().lower()
    if not ex_id or not local_path:
        return None
    sb = _supabase()
    if not sb:
        return None
    try:
        if not _ensure_bucket(sb):
            return None
        ext = ".png"
        low = local_path.lower()
        if low.endswith((".jpg", ".jpeg")):
            ext = ".jpg"
        elif low.endswith(".webp"):
            ext = ".webp"
        storage_path = f"{ex_id}{ext}"
        with open(local_path, "rb") as f:
            sb.storage.from_(BUCKET).upload(
                storage_path, f,
                {"content-type": f"image/{'jpeg' if ext == '.jpg' else ext[1:]}",
                 "upsert": "true"})
        pub = sb.storage.from_(BUCKET).get_public_url(storage_path)
        sb.table("ejercicio_imagenes").upsert({
            "exercise_id": ex_id,
            "image_url": pub,
            "storage_path": storage_path,
            "prompt": (prompt or "")[:2000],
            "proveedor": proveedor,
        }, on_conflict="exercise_id").execute()
        return pub
    except Exception as e:
        print(f"[imagen_terapeutica] No se pudo persistir imagen de {ex_id}: {e}")
        return None


def proveedores_disponibles() -> list:
    provs = []
    if os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip() and os.environ.get("CLOUDFLARE_API_TOKEN", "").strip():
        provs.append("cloudflare")
    if os.environ.get("WAVESPEED_API_KEY", "").strip():
        provs.append("wavespeed")
    if os.environ.get("PIXAZO_API_KEY", "").strip():
        provs.append("pixazo")
    if os.environ.get("GEMINI_API_KEY", "").strip():
        provs.append("gemini")
    if os.environ.get("FAL_KEY", "").strip():
        provs.append("fal")
    if os.environ.get("RECRAFT_API_KEY", "").strip():
        provs.append("recraft")
    if os.environ.get("REPLICATE_API_TOKEN", "").strip():
        provs.append("replicate")
    return provs


# Descripciones 3D por CONTENIDO del ejercicio (ver _SVG_POR_EJERCICIO en
# cuadernillo_pdf.py: los IDs arrastran nombres históricos distintos).
IMG_DESC_3D = {
    "le_huche": "3D torso diagram of slow breathing cycle with /f/ inhale and /sh/ exhale airflow arrows, relaxed shoulders",
    "shiatsu_cabeza": "3D head diagram with marked self-massage pressure dots on crown, temples, jaw and neck, no hands",
    "rotacion_hombros": "3D anatomical render of human upper torso showing neck side bend and shoulder roll, clinical style",
    "masaje_laringeo": "3D medical vector diagram of correct hand placement on the front of the neck, laryngeal area",
    "descenso_laringeo": "head profile vector diagram of wide yawn with lowered larynx arrow",
    "oclusion_succion": "head profile diagram phonating low rounded 'hu-hu' with lowered larynx indicator",
    "empuje_glotico": "mouth and vowel shaping diagram alternating open O-A and U-I positions with low larynx",
    "respiracion_abdominal": "3D anatomical render of human torso side-view showing abdominal expansion during breathing",
    "expansion_costo_lateral": "3D ribcage diagram with lateral expansion arrows on lower ribs during 4-4-8-2 breathing",
    "soplo_escalonado": "3D torso diagram of full 3D breathing expansion front sides and lumbar back, pursed-lip exhale",
    "coordinacion_costo_abdominal": "3D torso diagram showing sustained /s/ and /z/ airflow lines with stable breath support",
    "tubo_agua": "smooth pitch siren glide diagram on /m/ sliding from low to high tone and back, no glass no water",
    "vibracion_labial": "close-up lip and face mask diagram with /m/ vibration ripple lines on lips nose and cheeks",
    "popote_aire": "five ascending musical stairs diagram with notes going up and down, 3rd 5th octave",
    "consonantes_fricativas": "person chanting proverbs in sung speech with gentle melodic modulation lines",
    "humming_m": "open book with balanced reading sentences diagram and clear speech soundwave arcs",
    "oclusion_nasal": "nose and lip diagram showing nasal /m/ resonance flowing into open vowels",
    "glissandos": "smooth continuous siren pitch curve ascending and descending without breaks",
    "escalas_vocalicas": "person speaking monologue confidently for 2-3 minutes with breath support indicator",
    "frases_balanceadas": "person speaking clearly in 3D clinical render with expanding soundwave arcs extending forward, medical textbook aesthetic",
    "calentamiento": "three ascending warm-up steps diagram for voice training with arrows going up",
    "enfriamiento": "three descending cool-down steps diagram for voice training with arrows going down",
    "pautas_rlf": "inclined bed wedge pillow vector diagram and clock icon showing no food 2.5 hours before sleep",
}


def imagen_ia_habilitada() -> bool:
    """True si hay algún proveedor con key o si el modo libre está activo.
    Pollinations (gratuito, sin key) solo se usa con POLLINATIONS_ENABLED=1
    porque cada imagen tarda 30-90s y frenaría el PDF por defecto."""
    if proveedores_disponibles():
        return True
    return os.environ.get("POLLINATIONS_ENABLED", "").strip() in ("1", "true", "True")


def _pollinations_permitido() -> bool:
    return os.environ.get("POLLINATIONS_ENABLED", "").strip() in ("1", "true", "True")


def generar_imagen_ejercicio(nombre: str, descripcion: str = "",
                             exercise_id: str = "", estilo: str = "") -> str | None:
    """Devuelve el path local de la ilustración IA, o None si no hay proveedor
    configurado o fallan todos (el cuadernillo usa el dibujo vectorial).

    estilo: '3d_vector' (default, ilustración médica 3D) o 'vector_2d'
    (diagrama clínico plano). Fotorrealismo prohibido (directiva 2026).
    Orden: 1) imagen ya asociada en DB → 2) proveedores en cascada →
    3) la recién generada se sube a Storage y se asocia (no se regenera más).
    """
    ex_id = str(exercise_id or "").strip().lower()
    if ex_id:
        db_path = buscar_imagen_guardada(ex_id)
        if db_path:
            return db_path
    from mediacion_clinica import mediar_prompt, normalizar_estilo
    est = normalizar_estilo(estilo or _estilo_imagen())
    desc = _descripcion_ejercicio(ex_id, nombre or "ejercicio vocal",
                                  descripcion or "")
    # Motor de mediación universal: clasifica la maniobra y ensambla el prompt
    # en 4 capas (categoría + detalle + seguridad clínica + calidad/estilo).
    # Ningún prompt libre llega a las APIs sin sanitización.
    med = mediar_prompt(desc, "", est)
    prompt = med["prompt"]
    negativo_cat = med["negative_prompt"]
    desc3d = IMG_DESC_3D.get(ex_id, f"speech therapy exercise: {desc}")
    prompt_3d = PROMPT_3D_BASE.format(desc=desc3d)

    def _ok(path, prov, prm):
        if path and _es_imagen_valida(path):
            if ex_id:
                guardar_imagen_ejercicio(ex_id, path, prm, prov)
            return path
        return None

    # Cloudflare primero (tu cuenta, gratuito y rápido), luego Wavespeed, resto
    # (el archivo cacheado puede ser .png o .jpg según lo que devuelva el modelo)
    for _ext in ("png", "jpg", "webp"):
        _cand = _cache_path(f"{_cloudflare_model()}:{prompt}", "cloudflare", _ext)
        if _es_imagen_valida(_cand):
            return _cand
    r = _ok(_via_cloudflare(prompt, desc, negativo_cat), "cloudflare", prompt)
    if r:
        return r
    # Wavespeed primero (key dedicada del consultorio), luego el resto
    dest = _cache_path(prompt, "wavespeed")
    if _es_imagen_valida(dest):
        return dest
    r = _ok(_via_wavespeed(prompt), "wavespeed", prompt)
    if r:
        return r
    # En modo 3D Pixazo usa el prompt vectorial 3D (FLUX Schnell)
    prompt_pix = prompt_3d if est == "3d_vector" or _estilo_pixazo() == "3d" else prompt
    prov_pix = "pixazo3d" if prompt_pix is prompt_3d else "pixazo"
    dest = _cache_path(prompt_pix, prov_pix)
    if _es_imagen_valida(dest):
        return dest
    r = _ok(_via_pixazo(prompt_pix, prompt_3d), prov_pix, prompt_pix)
    if r:
        return r
    if _pollinations_permitido():
        r = _ok(_via_pollinations(prompt), "pollinations", prompt)
        if r:
            return r
    dest = _cache_path(prompt, "gemini")
    if _es_imagen_valida(dest):
        return dest
    r = _ok(_via_gemini(prompt), "gemini", prompt)
    if r:
        return r
    for prov, fn in (("fal", _via_fal), ("recraft", _via_recraft),
                     ("replicate", _via_replicate)):
        dest = _cache_path(prompt, prov)
        if _es_imagen_valida(dest):
            return dest
        r = _ok(fn(prompt), prov, prompt)
        if r:
            return r
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
