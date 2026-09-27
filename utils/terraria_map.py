from __future__ import annotations

import asyncio
import base64
import json
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
TERRARIA_RENDERER_DIR = ROOT_DIR / "scripts" / "terraria-player-map-renderer"
TERRARIA_MAP_SCRIPT = ROOT_DIR / "scripts" / "terraria_map.mjs"


def find_terraria_renderer_dir() -> Path:
    return TERRARIA_RENDERER_DIR


def check_terraria_environment() -> tuple[bool, str]:
    if not shutil.which("node"):
        return False, "Node.js executable not found in system PATH"
    if not TERRARIA_RENDERER_DIR.exists():
        return False, f"Terraria renderer directory not found at '{TERRARIA_RENDERER_DIR}'"
    missing = [
        rel_path
        for rel_path in [
            "scripts/terraria_map.mjs",
            "scripts/terraria-player-map-renderer/PlayerMapRenderer.js",
            "scripts/terraria-player-map-renderer/examples/map-from-parsed-world.mjs",
        ]
        if not (ROOT_DIR / rel_path).exists()
    ]
    if missing:
        return False, "Terraria renderer files missing: " + ", ".join(missing)
    return True, ""


async def render_terraria_world_map(world_bytes: bytes) -> tuple[bytes, str]:
    ok, reason = check_terraria_environment()
    if not ok:
        raise RuntimeError(reason)

    proc = await asyncio.create_subprocess_exec(
        "node",
        str(TERRARIA_MAP_SCRIPT),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(world_bytes)

    if proc.returncode != 0:
        error = stderr.decode(errors="replace").strip() or "Unknown Node.js error"
        raise RuntimeError(f"Terraria map conversion failed: {error}")

    try:
        payload = json.loads(stdout.decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Terraria map conversion returned invalid JSON output") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Terraria map conversion returned an invalid payload")

    filename = payload.get("filename")
    encoded = payload.get("data")
    if not isinstance(filename, str) or not filename:
        raise RuntimeError("Terraria map conversion returned no filename")
    if not isinstance(encoded, str):
        raise RuntimeError("Terraria map conversion returned no map data")

    try:
        map_bytes = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise RuntimeError("Terraria map conversion returned invalid base64 data") from exc

    return map_bytes, filename
