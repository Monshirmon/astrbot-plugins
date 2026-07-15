from __future__ import annotations

import datetime
import hashlib
import os
import traceback
import zipfile
import io
from datetime import datetime as dt
from pathlib import Path
from typing import Any

from astrbot.api import logger
from quart import jsonify, request, send_file

from .payloads import PLUGIN_NAME, build_plugin_state_payload, sanitize_strategy_payload


class StrategyIndexWebUIApi:
    def __init__(self, plugin):
        self.plugin = plugin

    def register(self) -> None:
        self.plugin.context.register_web_api(
            f"/{PLUGIN_NAME}/state", self._wrap(self.get_state), ["GET"], "Get state")
        self.plugin.context.register_web_api(
            f"/{PLUGIN_NAME}/save-strategy", self._wrap(self.save_strategy), ["POST"], "Save strategy")
        self.plugin.context.register_web_api(
            f"/{PLUGIN_NAME}/delete-strategy", self._wrap(self.delete_strategy), ["POST"], "Delete strategy")
        self.plugin.context.register_web_api(
            f"/{PLUGIN_NAME}/upload-image/<strategy_id>", self._wrap(self.upload_image), ["POST"], "Upload image")
        self.plugin.context.register_web_api(
            f"/{PLUGIN_NAME}/batch-upload", self._wrap(self.batch_upload), ["POST"], "Batch upload")
        self.plugin.context.register_web_api(
            f"/{PLUGIN_NAME}/categories", self._wrap(self.manage_categories), ["GET", "POST"], "Categories")
        self.plugin.context.register_web_api(
            f"/{PLUGIN_NAME}/export-images", self._wrap(self.export_images), ["GET"], "Export all images as zip")

    def _wrap(self, handler):
        async def wrapped(*args, **kwargs):
            try:
                return await handler(*args, **kwargs)
            except ValueError as exc:
                return jsonify({"status": "error", "message": str(exc)})
            except Exception as exc:
                logger.error("WebUI API failed: %s\n%s", exc, traceback.format_exc())
                return jsonify({"status": "error", "message": "操作失败"})
        return wrapped

    async def get_state(self):
        return jsonify(build_plugin_state_payload(self.plugin))

    async def save_strategy(self):
        payload = await request.get_json(force=True)
        sanitized = sanitize_strategy_payload(payload)
        strategy_id = str(payload.get("id", "") or "").strip()

        if strategy_id:
            strategies = self.plugin.data.get("strategies", [])
            found = next((st for st in strategies if st.get("id") == strategy_id), None)
            if not found:
                raise ValueError(f"攻略 {strategy_id} 不存在")
            for key, value in sanitized.items():
                found[key] = value
            found["last_modified"] = dt.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            new_st = {
                "id": self.plugin.utils.generate_strategy_id(),
                "image_paths": [],
                "upload_time": dt.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified": dt.now().strftime("%Y-%m-%d %H:%M:%S"),
                "modify_log": [{"time": dt.now().strftime("%Y-%m-%d %H:%M:%S"), "action": "webui_create", "detail": "WebUI创建"}],
                **sanitized,
            }
            self.plugin.data.setdefault("strategies", []).append(new_st)
            strategy_id = new_st["id"]

        await self.plugin.utils.save_data_async()
        return jsonify({"ok": True, "id": strategy_id, **build_plugin_state_payload(self.plugin)})

    async def delete_strategy(self):
        payload = await request.get_json(force=True)
        strategy_id = str(payload.get("id", "") or "").strip()
        if not strategy_id:
            raise ValueError("攻略ID不能为空")
        strategies = self.plugin.data.get("strategies", [])
        idx = next((i for i, st in enumerate(strategies) if st.get("id") == strategy_id), -1)
        if idx < 0:
            raise ValueError(f"攻略 {strategy_id} 不存在")
        st = strategies[idx]
        for img_path_rel in st.get("image_paths", []):
            img_path = os.path.join(self.plugin.image_dir, img_path_rel)
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                except Exception:
                    pass
        del strategies[idx]
        await self.plugin.utils.save_data_async()
        return jsonify({"ok": True, **build_plugin_state_payload(self.plugin)})

    async def upload_image(self, strategy_id: str):
        strategy_id = str(strategy_id).strip()
        files = await request.files
        file = files.get("file")
        if file is None:
            raise ValueError("未提供上传文件")
        strategies = self.plugin.data.get("strategies", [])
        found = next((st for st in strategies if st.get("id") == strategy_id), None)
        if not found:
            raise ValueError(f"攻略 {strategy_id} 不存在")
        target_dir = Path(self.plugin.image_dir)
        suffix = Path(file.filename or "").suffix or ".png"
        digest = hashlib.md5(f"{file.filename}-{dt.now().timestamp()}".encode()).hexdigest()[:8]
        filename = f"strategy_{dt.now().strftime('%Y%m%d_%H%M%S')}_{digest}{suffix}"
        target_path = target_dir / filename
        await file.save(target_path)
        if "image_paths" not in found:
            found["image_paths"] = []
        found["image_paths"].append(filename)
        found["last_modified"] = dt.now().strftime("%Y-%m-%d %H:%M:%S")
        await self.plugin.utils.save_data_async()
        return jsonify({"ok": True, "image_path": filename, "image_paths": found["image_paths"], **build_plugin_state_payload(self.plugin)})

    async def batch_upload(self):
        payload = await request.get_json(force=True)
        items = payload.get("items", [])
        if not items:
            raise ValueError("未提供攻略数据")
        added = 0
        for item in items:
            try:
                sanitized = sanitize_strategy_payload(item)
                new_st = {
                    "id": self.plugin.utils.generate_strategy_id(), "image_paths": [],
                    "upload_time": dt.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "last_modified": dt.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "modify_log": [{"time": dt.now().strftime("%Y-%m-%d %H:%M:%S"), "action": "batch_webui", "detail": "WebUI批量导入"}],
                    **sanitized,
                }
                self.plugin.data.setdefault("strategies", []).append(new_st)
                added += 1
            except Exception as e:
                logger.warning(f"批量导入单条失败: {e}")
        if added == 0:
            raise ValueError("没有成功导入任何攻略")
        await self.plugin.utils.save_data_async()
        return jsonify({"ok": True, "added": added, **build_plugin_state_payload(self.plugin)})

    async def manage_categories(self):
        if request.method == "GET":
            return jsonify({"categories": self.plugin.data.get("categories", [])})
        payload = await request.get_json(force=True)
        action = str(payload.get("action", "") or "").strip()
        name = str(payload.get("name", "") or "").strip()
        if action == "add" and name:
            if self.plugin.utils.add_category(name):
                await self.plugin.utils.save_data_async()
                return jsonify({"ok": True, "categories": self.plugin.data.get("categories", [])})
            raise ValueError(f"分类 '{name}' 已存在")
        if action == "del" and name:
            if self.plugin.utils.remove_category(name):
                await self.plugin.utils.save_data_async()
                return jsonify({"ok": True, "categories": self.plugin.data.get("categories", [])})
            raise ValueError(f"分类 '{name}' 不存在")
        raise ValueError("无效操作")

    async def export_images(self):
        """导出所有图片为 ZIP 文件。"""
        image_dir = self.plugin.image_dir
        if not os.path.isdir(image_dir):
            raise ValueError("图片目录不存在")

        files = [f for f in os.listdir(image_dir) if os.path.isfile(os.path.join(image_dir, f))]
        if not files:
            raise ValueError("没有可导出的图片")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in files:
                filepath = os.path.join(image_dir, fname)
                zf.write(filepath, fname)
        buf.seek(0)

        return await send_file(
            buf,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"strategy_images_{dt.now().strftime('%Y%m%d_%H%M%S')}.zip",
        )
