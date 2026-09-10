"""VocalisLab Pro — Cliente Groq compartido con fallback automático de modelos.

Groq retira modelos periódicamente (ej. llama-3.3-70b-versatile). Este helper
prueba cada modelo candidato en orden hasta que uno responde. El orden se puede
sobrescribir con la variable de entorno GROQ_MODEL (lista separada por comas).
"""
import os

DEFAULT_GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "moonshotai/kimi-k2-instruct",
    "qwen/qwen3-32b",
    "openai/gpt-oss-20b",
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
