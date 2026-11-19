"""VocalisLab Pro — Cliente Groq compartido con fallback automático de modelos.

Groq retira modelos periódicamente (ej. llama-3.3-70b-versatile). Este helper
prueba cada modelo candidato en orden hasta que uno responde. El orden se puede
sobrescribir con la variable de entorno GROQ_MODEL (lista separada por comas).
"""
import os

# Modelos vigentes en Groq a Sep-2026 (llama-3.1, llama-4 y qwen3-32b
# fueron dados de baja; reemplazos oficiales de Groq).
DEFAULT_GROQ_MODELS = [
    "openai/gpt-oss-20b",
    "moonshotai/kimi-k2-instruct",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-120b",
]


def get_groq_models():
    env = os.environ.get("GROQ_MODEL", "").strip()
    if env:
        return [m.strip() for m in env.split(",") if m.strip()]
    return list(DEFAULT_GROQ_MODELS)


def groq_chat(messages, temperature=0.3, max_tokens=1500, response_format=None, timeout=30.0):
    """Llama a Groq probando modelos en orden. Devuelve (texto, modelo_usado).

    Si un modelo falla (retirado, sin acceso, rate-limit, sin JSON-mode...),
    pasa automáticamente al siguiente. Lanza excepción solo si ninguno responde.
    """
    from groq import Groq
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY no configurada")
    client = Groq(api_key=key, timeout=timeout)
    last_err: Exception = RuntimeError("Sin modelos Groq configurados")
    for model in get_groq_models():
        try:
            kwargs = dict(messages=messages, model=model,
                          temperature=temperature, max_tokens=max_tokens)
            if response_format is not None:
                kwargs["response_format"] = response_format
            resp = client.chat.completions.create(**kwargs)
            return (resp.choices[0].message.content or ""), model
        except Exception as e:
            last_err = e
            print(f"[llm_client] Modelo {model} fallo ({str(e)[:120]}). Probando siguiente...")
            continue
    raise last_err


# ─── Gemini: cliente único con respaldo de modelos ─────────────────────
# Google apaga modelos seguido (gemini-2.0-flash se apagó el 1/6/2026;
# gemini-2.5-flash se apaga el 1/12/2026). Antes cada módulo tenía el nombre
# escrito a mano y dejaba de andar sin aviso. Ahora todos pasan por acá:
# se prueba el modelo configurado (si no está apagado) y después los
# vigentes, en orden. Lista oficial: aistudio.google.com/docs/deprecations
GEMINI_TEXT_MODELS = [
    "gemini-3.6-flash",       # reemplazo oficial de gemini-2.0-flash
    "gemini-3.5-flash-lite",  # reemplazo oficial de gemini-2.5-flash
    "gemini-2.5-flash-lite",  # sin fecha de baja anunciada
]
GEMINI_IMAGE_MODELS = [
    "gemini-nano-banana-2.1",
    "gemini-3.1-flash-image",
    "gemini-2.5-flash-image",  # se apaga el 15/3/2027
]
# Prefijos de modelos ya apagados: se saltean aunque estén configurados.
GEMINI_APAGADOS = ("gemini-1.0", "gemini-1.5", "gemini-2.0")
_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def gemini_models(tipo: str = "texto", preferidos=None) -> list:
    """Modelos Gemini a probar, en orden: los preferidos/configurados que no
    estén apagados y luego los vigentes por defecto."""
    if preferidos is None:
        var = "GEMINI_IMAGE_MODEL" if tipo == "imagen" else "GEMINI_MODEL"
        preferidos = [os.environ.get(var, "")]
        if tipo != "imagen":
            preferidos.append(os.environ.get("AI_MODEL", ""))
    candidatos = []
    for valor in preferidos:
        candidatos += [m.strip() for m in str(valor or "").split(",") if m.strip()]
    candidatos += GEMINI_IMAGE_MODELS if tipo == "imagen" else GEMINI_TEXT_MODELS
    return [m for m in dict.fromkeys(candidatos)
            if m.startswith("gemini") and not m.startswith(GEMINI_APAGADOS)]


def gemini_texto(data: dict) -> str:
    """Texto de la primera respuesta de Gemini ("" si no hay)."""
    cands = (data or {}).get("candidates") or []
    parts = ((cands[0].get("content") or {}).get("parts") or []) if cands else []
    return "".join(p.get("text", "") for p in parts if isinstance(p, dict))


def _gemini_body(parts, generation_config):
    body = {"contents": [{"parts": parts}]}
    if generation_config:
        body["generationConfig"] = generation_config
    return body


def _gemini_respuesta_util(resp) -> dict:
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    if not data.get("candidates"):
        raise RuntimeError(f"sin respuesta: {str(data)[:200]}")
    return data


def gemini_generate(parts, generation_config=None, tipo="texto", modelos=None,
                    timeout=120.0):
    """Llama a Gemini probando modelos en orden. Devuelve (json, modelo).
    `parts` es la lista de partes del contenido (texto, imágenes)."""
    import httpx
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY no configurada")
    errores = []
    for model in (modelos or gemini_models(tipo)):
        try:
            r = httpx.post(_GEMINI_URL.format(model=model), params={"key": key},
                           json=_gemini_body(parts, generation_config), timeout=timeout)
            return _gemini_respuesta_util(r), model
        except Exception as e:
            errores.append(f"{model}: {str(e)[:150]}")
            print(f"[llm_client] Gemini {model} falló ({str(e)[:120]}). Probando siguiente...")
    raise RuntimeError("Ningún modelo Gemini respondió: " + " | ".join(errores))


async def gemini_generate_async(parts, generation_config=None, tipo="texto",
                                modelos=None, timeout=120.0):
    """Versión async de gemini_generate. Devuelve (json, modelo)."""
    import httpx
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY no configurada")
    errores = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        for model in (modelos or gemini_models(tipo)):
            try:
                r = await client.post(_GEMINI_URL.format(model=model), params={"key": key},
                                      json=_gemini_body(parts, generation_config))
                return _gemini_respuesta_util(r), model
            except Exception as e:
                errores.append(f"{model}: {str(e)[:150]}")
                print(f"[llm_client] Gemini {model} falló ({str(e)[:120]}). Probando siguiente...")
    raise RuntimeError("Ningún modelo Gemini respondió: " + " | ".join(errores))


def gemini_texto_completo(prompt: str, temperature: float = 0.2, max_tokens: int = 16000,
                          timeout: float = 150.0, continuaciones: int = 2) -> tuple:
    """Texto largo SIN cortes. Los modelos que "piensan" gastan parte del
    límite razonando y la respuesta quedaba a mitad de frase: se usa un
    límite amplio y, si igual corta (finishReason MAX_TOKENS), se le pide que
    siga exactamente donde quedó. Devuelve (texto, modelo, completo)."""
    import httpx
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY no configurada")
    errores = []
    for model in gemini_models("texto"):
        try:
            contents = [{"role": "user", "parts": [{"text": prompt}]}]
            texto, completo = "", False
            for _ in range(continuaciones + 1):
                r = httpx.post(_GEMINI_URL.format(model=model), params={"key": key}, timeout=timeout,
                               json={"contents": contents,
                                     "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}})
                data = _gemini_respuesta_util(r)
                parte = gemini_texto(data)
                texto += parte
                motivo = (data["candidates"][0].get("finishReason") or "").upper()
                if motivo != "MAX_TOKENS":
                    completo = motivo in ("STOP", "")
                    break
                contents += [{"role": "model", "parts": [{"text": parte}]},
                             {"role": "user", "parts": [{"text": "Seguí exactamente desde donde quedaste, sin repetir nada."}]}]
            if texto.strip():
                return texto.strip(), model, completo
            errores.append(f"{model}: respuesta vacía")
        except Exception as e:
            errores.append(f"{model}: {str(e)[:150]}")
            print(f"[llm_client] Gemini {model} falló ({str(e)[:120]}). Probando siguiente...")
    raise RuntimeError("Ningún modelo Gemini respondió: " + " | ".join(errores))
