"""资源运维管理模块"""

import os
from datetime import datetime
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger


class ResourceManagementModule:

    def __init__(self, plugin):
        self.plugin = plugin

    async def delete_strategy(self, event: AstrMessageEvent):
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return
        msg = event.message_str.strip()
        parts = msg.split(None, 1)
        if len(parts) < 2:
            yield event.plain_result("格式: /删除攻略 <序号或攻略名称>")
            return
        idx = self.plugin.utils.get_strategy_index(parts[1])
        if idx < 0:
            yield event.plain_result(f"未找到攻略: {parts[1]}")
            return
        strategy = self.plugin.data["strategies"][idx]
        name = strategy.get("name", "未命名")
        for img_path_rel in strategy.get("image_paths", []):
            img_path = os.path.join(self.plugin.image_dir, img_path_rel)
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                except Exception:
                    pass
        del self.plugin.data["strategies"][idx]
        await self.plugin.utils.save_data_async()
        self.plugin.utils.add_log("删除攻略", f"名称: {name}", str(event.get_sender_id()))
        yield event.plain_result(f"已删除攻略「{name}」。")

    async def edit_strategy(self, event: AstrMessageEvent):
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return
        msg = event.message_str.strip()
        parts = msg.split(None, 3)
        if len(parts) < 4:
            yield event.plain_result("格式: /编辑攻略 <序号或名称> <字段> <值>\n字段: name/category/trigger_words/subcategory/text_content\n示例: /编辑攻略 1 trigger_words 钻石,挖矿")
            return
        idx_str, field, value = parts[1], parts[2], parts[3]
        idx = self.plugin.utils.get_strategy_index(idx_str)
        if idx < 0:
            yield event.plain_result(f"未找到攻略: {idx_str}")
            return
        strategy = self.plugin.data["strategies"][idx]
        old_name = strategy.get("name", "")
        valid_fields = ["name", "category", "trigger_words", "subcategory", "text_content", "status"]
        if field not in valid_fields:
            yield event.plain_result(f"无效字段: {field}。有效: {', '.join(valid_fields)}")
            return
        if field == "trigger_words":
            value_list = [tw.strip() for tw in value.split(",") if tw.strip()]
            strategy["trigger_words"] = value_list
            updated_value = ", ".join(value_list)
        elif field == "category":
            if value and value not in self.plugin.data.get("categories", []):
                self.plugin.utils.add_category(value)
            strategy["category"] = value
            updated_value = value
        else:
            strategy[field] = value
            updated_value = value[:50]
        strategy["last_modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        strategy.setdefault("modify_log", []).append({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "action": "edit", "detail": f"修改 {field}: {updated_value}"})
        if strategy.get("category") and strategy.get("trigger_words"):
            strategy["status"] = "needs_image_edit" if not strategy.get("image_paths") else "normal"
        await self.plugin.utils.save_data_async()
        self.plugin.utils.add_log("编辑攻略", f"{old_name}: {field} -> {updated_value}", str(event.get_sender_id()))
        yield event.plain_result(f"已更新「{old_name}」的 {field}: {updated_value}")

    async def replace_image(self, event: AstrMessageEvent):
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return
        msg = event.message_str.strip()
        parts = msg.split(None, 1)
        if len(parts) < 2:
            yield event.plain_result("格式: /替换攻略图 <序号或名称> (附带新图片，可发多张)")
            return
        idx = self.plugin.utils.get_strategy_index(parts[1])
        if idx < 0:
            yield event.plain_result(f"未找到攻略: {parts[1]}")
            return
        strategy = self.plugin.data["strategies"][idx]
        name = strategy.get("name", "未命名")
        new_image_paths = []
        from astrbot.api.message_components import Image
        for comp in event.get_messages():
            if isinstance(comp, Image):
                if comp.file and os.path.exists(comp.file):
                    ext = os.path.splitext(comp.file)[1] or ".png"
                    dst_name = f"{self.plugin.utils.generate_strategy_id()}{ext}"
                    import shutil
                    shutil.copy(comp.file, os.path.join(self.plugin.image_dir, dst_name))
                    new_image_paths.append(dst_name)
                elif comp.url:
                    downloaded = await self.plugin.utils.download_media_file(comp.url, "image")
                    if downloaded:
                        new_image_paths.append(downloaded)
        if not new_image_paths:
            yield event.plain_result("未检测到新图片。")
            return
        for old_rel in strategy.get("image_paths", []):
            old_path = os.path.join(self.plugin.image_dir, old_rel)
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except Exception:
                    pass
        strategy["image_paths"] = new_image_paths
        strategy["last_modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        strategy.setdefault("modify_log", []).append({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "action": "replace_image", "detail": f"替换 ({len(new_image_paths)}张)"})
        if strategy.get("category") and strategy.get("trigger_words"):
            strategy["status"] = "normal"
        await self.plugin.utils.save_data_async()
        self.plugin.utils.add_log("替换图片", f"{name} ({len(new_image_paths)}张)", str(event.get_sender_id()))
        yield event.plain_result(f"已替换「{name}」的图片。（{len(new_image_paths)}张）")

    async def list_all_strategies(self, event: AstrMessageEvent):
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return
        strategies = self.plugin.data.get("strategies", [])
        if not strategies:
            yield event.plain_result("攻略库为空。")
            return
        text = f"全部攻略 ({len(strategies)}篇):\n\n"
        for i, st in enumerate(strategies, 1):
            icon = {"normal": "✓", "pending_review": "⚠", "needs_image_edit": "📷"}.get(st.get("status", ""), "?")
            cat = st.get("category", "未分类")
            text += f"{i}. [{icon}] {st.get('name', '未命名')} | {cat}\n   ID: {st.get('id', '-')} | 触发词: {', '.join(st.get('trigger_words', [])[:3]) or '无'}\n\n"
        yield event.plain_result(text.strip())

    async def manage_categories(self, event: AstrMessageEvent):
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return
        msg = event.message_str.strip()
        parts = msg.split(None, 2)
        if len(parts) < 2:
            cats = self.plugin.data.get("categories", [])
            text = "攻略分类管理:\n\n" + ("(空)\n\n" if not cats else "\n".join(f"  • {c}" for c in cats) + "\n\n") + "用法: /攻略分类管理 add <名称> | /攻略分类管理 del <名称>"
            yield event.plain_result(text)
            return
        action, name = parts[1], parts[2] if len(parts) > 2 else ""
        if action == "add" and name:
            if self.plugin.utils.add_category(name):
                await self.plugin.utils.save_data_async()
                yield event.plain_result(f"已添加分类: {name}")
            else:
                yield event.plain_result(f"分类 '{name}' 已存在。")
        elif action == "del" and name:
            if self.plugin.utils.remove_category(name):
                await self.plugin.utils.save_data_async()
                yield event.plain_result(f"已删除分类: {name}，该分类下的攻略已标记为待整改。")
            else:
                yield event.plain_result(f"分类 '{name}' 不存在。")
        else:
            yield event.plain_result("格式: /攻略分类管理 add <名称> | /攻略分类管理 del <名称>")
