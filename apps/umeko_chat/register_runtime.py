"""Explicit one-time registration of the LIME host and currently served model.

This only adds missing identities; a reused model key is never repointed to
another model because old runtime.instances refer to that identity.
"""

import os
import platform

from db import _required_env, get_connection
from intelligence import IntelligenceClient


def register(conn, *, host_key: str, model_key: str, served_model: str):
    if not host_key or not model_key:
        raise ValueError("Host and model keys must be set")
    if model_key.startswith("ollama:"):
        raise ValueError("Choose a new model key for the llama.cpp runtime")
    with conn.transaction():
        conn.execute(
            """
            INSERT INTO runtime.hosts (host_key, hostname, display_name, host_type, os_name)
            VALUES (%s, %s, %s, 'machine', %s)
            ON CONFLICT (host_key) DO NOTHING
            """,
            (host_key, platform.node(), host_key, platform.system()),
        )
        conn.execute(
            """
            INSERT INTO runtime.models (model_key, provider, model_name, base_model_name)
            VALUES (%s, 'llama.cpp', %s, 'gpt-oss-20b')
            ON CONFLICT (model_key) DO NOTHING
            """,
            (model_key, served_model),
        )
        host = conn.execute(
            "SELECT hostname FROM runtime.hosts WHERE host_key = %s AND enabled",
            (host_key,),
        ).fetchone()
        model = conn.execute(
            "SELECT provider, model_name FROM runtime.models WHERE model_key = %s AND enabled",
            (model_key,),
        ).fetchone()
        if not host or host[0].casefold() != platform.node().casefold():
            raise RuntimeError(f"Host key {host_key!r} is already assigned to another host")
        if model != ("llama.cpp", served_model):
            raise RuntimeError(f"Model key {model_key!r} already identifies a different model")


def main():
    client = IntelligenceClient(
        os.getenv("INTELLIGENCE_BASE_URL", "http://127.0.0.1:8081"),
        os.getenv("INTELLIGENCE_MODEL"),
    )
    served_model = client.resolve_model()
    with get_connection() as conn:
        register(
            conn,
            host_key=_required_env("FLAMORIS_HOST_KEY"),
            model_key=_required_env("FLAMORIS_MODEL_KEY"),
            served_model=served_model,
        )
    print(f"Registered host and model: {served_model}")


if __name__ == "__main__":
    main()
