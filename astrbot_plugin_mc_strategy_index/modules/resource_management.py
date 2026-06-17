"""资源运维管理模块（增删改查）"""

import os
from datetime import datetime

from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger


class ResourceManagementModule:
    """攻略资源增删改查管理模块。"""

    def __init__(self, plugin):
        self.plugin = plugin

    # ---- 删除攻略 ----

    async def delete_strategy(self, event: AstrMessageEvent):
        """删除指定攻略。用法: /删除攻略 <序号或名称>"""
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

        idx_str = parts[1]
        idx = self.plugin.utils.get_strategy_index(idx_str)
        if idx < 0:
            yield event.plain_result(f"未找到攻略: {idx_str}")
            return

        strategy = self.plugin.data["strategies"][idx]
        name = strategy.get("name", "未命名")

        # 清理图片文件
        for img_path_rel in strategy.get("image_paths", []):
            img_path = os.path.join(self.plugin.image_dir, img_path_rel)
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                except Exception as e:
                    logger.warning(f"删除图片文件失败: {e}")

        del self.plugin.data["strategies"][idx]
        await self.plugin.utils.save_data_async()
        self.plugin.utils.add_log("删除攻略", f"名称: {name}", str(event.get_sender_id()))
        yield event.plain_result(f"已删除攻略「{name}」。")

    # ---- 编辑攻略 ----

    async def edit_strategy(self, event: AstrMessageEvent):
        """
        编辑攻略元数据。
        用法: /编辑攻略 <序号或名称> <字段> <值>
        字段: name/category/keywords
        """
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return

        msg = event.message_str.strip()
        parts = msg.split(None, 3)
        if len(parts) < 4:
            yield event.plain_result(
                "格式: /编辑攻略 <序号或名称> <字段> <值>\n"
                "字段: name(名称) | category(分类) | keywords(关键词,逗号分隔)\n"
                "示例: /编辑攻略 1 name 钻石挖矿指南\n"
                "示例: /编辑攻略 2 category 资源收集\n"
                "示例: /编辑攻略 3 keywords 钻石,挖矿,11层"
            )
            return

        idx_str = parts[1]
        field = parts[2]
        value = parts[3]

        idx = self.plugin.utils.get_strategy_index(idx_str)
        if idx < 0:
            yield event.plain_result(f"未找到攻略: {idx_str}")
            return

        strategy = self.plugin.data["strategies"][idx]
        old_name = strategy.get("name", "")
        valid_fields = ["name", "category", "trigger_words", "subcategory", "text_content"]

        if field not in valid_fields:
            yield event.plain_result(f"无效字段: {field}。有效字段: {', '.join(valid_fields)}")
            return

        if field == "trigger_words":
            value_list = [tw.strip() for tw in value.split(",") if tw.strip()]
            strategy["trigger_words"] = value_list
            updated_value = ", ".join(value_list)
        elif field == "category":
            category = value
            cats = self.plugin.data.get("categories", [])
            if category and category not in cats:
                self.plugin.utils.add_category(category)
            strategy["category"] = category
            updated_value = category
        else:
            strategy[field] = value
            updated_value = value[:50]

        strategy["last_modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        strategy.setdefault("modify_log", []).append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": "edit",
            "detail": f"修改 {field}: {updated_value}"
        })

        # 自动更新状态
        if strategy.get("category") and strategy.get("keywords"):
            if strategy.get("status") == "pending_review":
                strategy["status"] = "needs_image_edit" if not strategy.get("image_path") else "normal"

        await self.plugin.utils.save_data_async()
        self.plugin.utils.add_log("编辑攻略", f"{old_name}: {field} -> {updated_value}", str(event.get_sender_id()))
        yield event.plain_result(f"已更新攻略「{old_name}」的 {field}: {updated_value}")

    # ---- 替换图片 ----

    async def replace_image(self, event: AstrMessageEvent):
        """替换指定攻略的图片。用法: /替换攻略图 <序号或名称> (附带新图片，可发多张)"""
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return

        msg = event.message_str.strip()
        parts = msg.split(None, 1)
        if len(parts) < 2:
            yield event.plain_result("格式: /替换攻略图 <序号或攻略名称> (同时发送新图片，可发多张)")
            return

        idx_str = parts[1]
        idx = self.plugin.utils.get_strategy_index(idx_str)
        if idx < 0:
            yield event.plain_result(f"未找到攻略: {idx_str}")
            return

        strategy = self.plugin.data["strategies"][idx]
        name = strategy.get("name", "未命名")

        # 从消息收集所有新图片
        messages = event.get_messages()
        new_image_paths = []

        from astrbot.api.message_components import Image
        for comp in messages:
            if isinstance(comp, Image):
                if comp.file and os.path.exists(comp.file):
                    src = comp.file
                    ext = os.path.splitext(src)[1] or ".png"
                    sid = self.plugin.utils.generate_strategy_id()
                    dst_name = f"{sid}{ext}"
                    dst = os.path.join(self.plugin.image_dir, dst_name)
                    import shutil
                    shutil.copy(src, dst)
                    new_image_paths.append(dst_name)
                elif comp.url:
                    downloaded = await self.plugin.utils.download_media_file(comp.url, "image")
                    if downloaded:
                        new_image_paths.append(downloaded)

        if not new_image_paths:
            yield event.plain_result("未检测到新图片。请在发送命令时附带图片消息。")
            return

        # 删除旧图片
        for old_rel in strategy.get("image_paths", []):
            old_path = os.path.join(self.plugin.image_dir, old_rel)
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except Exception:
                    pass

        strategy["image_paths"] = new_image_paths
        strategy["last_modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        strategy.setdefault("modify_log", []).append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": "replace_image",
            "detail": f"替换攻略图片 ({len(new_image_paths)}张)"
        })

        # 更新状态
        if strategy.get("category") and strategy.get("trigger_words"):
            strategy["status"] = "normal"

        await self.plugin.utils.save_data_async()
        self.plugin.utils.add_log("替换图片", f"攻略: {name} ({len(new_image_paths)}张)", str(event.get_sender_id()))
        yield event.plain_result(f"已替换攻略「{name}」的图片。（{len(new_image_paths)}张）")

    # ---- 查看所有攻略(管理员视角) ----

    async def list_all_strategies(self, event: AstrMessageEvent):
        """管理员查看全部攻略列表（含状态）。用法: /攻略列表 all"""
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return

        strategies = self.plugin.data.get("strategies", [])
        if not strategies:
            yield event.plain_result("攻略库为空。")
            return

        text = f"📚 全部攻略 ({len(strategies)}篇):\n\n"
        for i, st in enumerate(strategies, 1):
            status_icon = {"normal": "✓", "pending_review": "⚠", "needs_image_edit": "📷"}.get(
                st.get("status", ""), "?"
            )
            cat = st.get("category", "未分类")
            text += f"{i}. [{status_icon}] {st.get('name', '未命名')} | {cat}\n"
            text += f"   ID: {st.get('id', '-')} | 关键词: {', '.join(st.get('keywords', [])[:3]) or '无'}\n\n"

        yield event.plain_result(text.strip())

    # ---- 分类管理 ----

    async def manage_categories(self, event: AstrMessageEvent):
        """管理攻略分类。用法: /攻略分类 [add/del/列表] [分类名]"""
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return

        msg = event.message_str.strip()
        parts = msg.split(None, 2)

        if len(parts) < 2:
            # 列出所有分类
            cats = self.plugin.data.get("categories", [])
            strategies = self.plugin.data.get("strategies", [])
            text = "📂 攻略分类管理:\n\n"
            for cat in cats:
                count = sum(1 for s in strategies if s.get("category") == cat)
                text += f"  • {cat} ({count}篇)\n"
            text += "\n用法: /攻略分类 add <名称> | /攻略分类 del <名称>"
            yield event.plain_result(text)
            return

        action = parts[1]
        if action == "add" and len(parts) > 2:
            name = parts[2]
            if self.plugin.utils.add_category(name):
                await self.plugin.utils.save_data_async()
                yield event.plain_result(f"已添加分类: {name}")
            else:
                yield event.plain_result(f"分类 '{name}' 已存在。")
        elif action == "del" and len(parts) > 2:
            name = parts[2]
            if self.plugin.utils.remove_category(name):
                await self.plugin.utils.save_data_async()
                yield event.plain_result(f"已删除分类: {name}，该分类下的攻略已标记为待整改。")
            else:
                yield event.plain_result(f"分类 '{name}' 不存在。")
        else:
            yield event.plain_result("格式: /攻略分类 add <名称> | /攻略分类 del <名称> | /攻略分类")
