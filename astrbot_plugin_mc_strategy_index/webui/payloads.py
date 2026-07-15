from __future__ import annotations

from typing import Any

PLUGIN_NAME = "astrbot_plugin_mc_strategy_index"


def build_plugin_state_payload(plugin: Any) -> dict[str, Any]:
    return {
        "strategies": [_serialize_strategy(st) for st in plugin.data.get("strategies", [])],
        "categories": list(plugin.data.get("categories", [])),
        "index_image_path": plugin.data.get("index_image_path", ""),
        "trigger_words": plugin.utils.get_all_trigger_words(),
        "defaults": {
            "enable_image_edit": bool(plugin.config.get("enable_image_edit", False)),
        },
        "config": {
            "image_api_provider": plugin.config.get("image_api_provider", "openai"),
            "image_api_model": plugin.config.get("image_api_model", "gpt-4o"),
            "has_api_key": bool(plugin.config.get("image_api_key", "")),
        },
        "image_count": len(os.listdir(plugin.image_dir)) if hasattr(plugin, 'image_dir') and os.path.isdir(plugin.image_dir) else 0,
    }
import os


def _serialize_strategy(st: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": st.get("id", ""),
        "name": st.get("name", ""),
        "category": st.get("category", ""),
        "subcategory": st.get("subcategory", ""),
        "trigger_words": list(st.get("trigger_words", [])),
        "status": st.get("status", "pending_review"),
        "text_content": st.get("text_content", "")[:500],
        "image_paths": list(st.get("image_paths", [])),
        "upload_time": st.get("upload_time", ""),
        "last_modified": st.get("last_modified", ""),
        "modify_log": st.get("modify_log", [])[-10:],
    }


def sanitize_strategy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", "") or "").strip()
    if not name:
        raise ValueError("攻略名称不能为空")
    return {
        "name": name,
        "category": str(payload.get("category", "") or "").strip(),
        "subcategory": str(payload.get("subcategory", "") or "").strip(),
        "trigger_words": _sanitize_list(payload.get("trigger_words", [])),
        "status": str(payload.get("status", "pending_review") or "pending_review"),
        "text_content": str(payload.get("text_content", "") or "")[:4000],
    }


def _sanitize_list(items: Any) -> list[str]:
    if isinstance(items, str):
        items = [kw.strip() for kw in items.split(",") if kw.strip()]
    result = []
    for kw in (items or []):
        kw_str = str(kw).strip()
        if kw_str and kw_str not in result:
            result.append(kw_str)
    return result[:20]
