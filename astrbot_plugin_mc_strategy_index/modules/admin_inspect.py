"""管理员专属检索巡检命令模块"""

import os
from datetime import datetime
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger


class AdminInspectModule:

    def __init__(self, plugin):
        self.plugin = plugin

    async def inspect_library(self, event: AstrMessageEvent):
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return
        strategies = self.plugin.data.get("strategies", [])
        if not strategies:
            yield event.plain_result("攻略库为空。")
            return
        issues = []
        valid_categories = set(self.plugin.data.get("categories", []))
        for st in strategies:
            problems = []
            cat = st.get("category", "")
            if not cat:
                problems.append("无分类")
            elif valid_categories and cat not in valid_categories:
                problems.append(f"分类 '{cat}' 不在有效分类列表中")
            if not st.get("trigger_words", []):
                problems.append("无触发词")
            imgs = st.get("image_paths", [])
            if not imgs:
                problems.append("缺少攻略图片")
            else:
                missing = [img for img in imgs if not os.path.exists(os.path.join(self.plugin.image_dir, img))]
                if missing:
                    problems.append(f"{len(missing)}张图片文件缺失")
            if problems:
                issues.append({"strategy": st, "problems": problems})

        index_updated = await self.plugin.utils.regenerate_index_image()
        if not issues:
            text = f"巡检完成: 所有攻略资源均符合规范。\n共检查 {len(strategies)} 篇攻略。"
            if index_updated:
                text += "\n索引图已更新。"
            yield event.plain_result(text)
            return
        text = f"攻略库巡检报告\n\n总计: {len(strategies)} 篇 | 异常: {len(issues)} 篇\n\n"
        for i, item in enumerate(issues, 1):
            st = item["strategy"]
            text += f"【{i}】{st.get('name', '未命名')} (ID: {st.get('id', '-')})\n"
            text += f"  分类: {st.get('category') or '无'}\n"
            text += f"  触发词: {', '.join(st.get('trigger_words', [])) or '无'}\n"
            text += f"  图片: {len(st.get('image_paths', []))}张\n"
            text += f"  问题: {' | '.join(item['problems'])}\n\n"
        if index_updated:
            text += "索引图已自动更新。\n"
        enable_edit = self.plugin.config.get("enable_image_edit", False)
        has_api_key = bool(self.plugin.config.get("image_api_key", ""))
        text += "发送 /整改攻略 <序号> 整改" if (enable_edit and has_api_key) else "发送 /编辑攻略 <序号> 手动修正"
        yield event.plain_result(text)

    async def rectify_strategy(self, event: AstrMessageEvent):
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return
        msg = event.message_str.strip()
        parts = msg.split(None, 1)
        if len(parts) < 2:
            yield event.plain_result("格式: /整改攻略 <序号或攻略名称>")
            return
        idx_str = parts[1]
        strategy = self.plugin.utils.find_strategy_by_index(idx_str)
        if not strategy:
            yield event.plain_result(f"未找到攻略: {idx_str}")
            return
        if not self.plugin.config.get("enable_image_edit", False):
            yield event.plain_result("图片编辑功能未启用。")
            return
        yield event.plain_result(f"正在整改「{strategy.get('name')}」...")
        new_image = await self.plugin.image_api.generate_index_image(strategy)
        if new_image:
            for old_img in strategy.get("image_paths", []):
                old_path = os.path.join(self.plugin.image_dir, old_img)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception:
                        pass
            strategy["image_paths"] = [new_image]
        name = strategy.get("name", "")
        if not strategy.get("category"):
            strategy["category"] = self.plugin.utils.guess_category_from_name(name)
        if not strategy.get("trigger_words"):
            strategy["trigger_words"] = [name.strip()]
        has_cat = bool(strategy.get("category"))
        has_imgs = bool(strategy.get("image_paths"))
        has_tws = bool(strategy.get("trigger_words"))
        strategy["status"] = "normal" if (has_cat and has_imgs and has_tws) else "pending_review"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        strategy["last_modified"] = now_str
        strategy.setdefault("modify_log", []).append({"time": now_str, "action": "rectify", "detail": "巡检整改"})
        await self.plugin.utils.save_data_async()
        self.plugin.utils.add_log("整改攻略", f"名称: {name}", str(event.get_sender_id()))
        await self.plugin.utils.regenerate_index_image()
        yield event.plain_result(f"整改完成「{name}」\n状态: {'已规范' if strategy['status'] == 'normal' else '部分完善'}\n分类: {strategy.get('category', '未分类')}\n触发词: {', '.join(strategy.get('trigger_words', []))}\n图片: {'已更新' if new_image else '未变更'}")

    async def view_logs(self, event: AstrMessageEvent):
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return
        msg = event.message_str.strip()
        parts = msg.split(None, 1)
        count = 20
        if len(parts) > 1:
            try:
                count = min(int(parts[1]), 50)
            except ValueError:
                pass
        logs = self.plugin.data.get("logs", [])
        if not logs:
            yield event.plain_result("暂无操作日志。")
            return
        recent = logs[-count:][::-1]
        text = f"最近 {len(recent)} 条操作日志:\n\n"
        for log in recent:
            text += f"[{log.get('time', '')}] {log.get('action', '')}\n  {log.get('detail', '')} | {log.get('operator', '')}\n"
        yield event.plain_result(text)
