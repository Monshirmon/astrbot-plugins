"""萌新玩家触发词/分类检索模块"""

from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import Image, Plain, Reply
from astrbot.api.event import MessageEventResult


class PlayerSearchModule:
    """面向全体公会萌新开放检索功能。"""

    def __init__(self, plugin):
        self.plugin = plugin

    async def search_strategy(self, event: AstrMessageEvent):
        """搜索攻略。用法: /查攻略 <关键词>"""
        msg = event.message_str.strip()
        parts = msg.split(None, 1)
        if len(parts) < 2:
            yield self.plugin.utils.build_category_list_reply(event)
            return

        query = parts[1]
        results = self.plugin.utils.match_strategies_by_name(query, limit=5)

        reply = self.plugin.utils.build_search_reply(event, results, query)
        yield reply

    async def list_categories(self, event: AstrMessageEvent):
        """查看攻略分类列表。用法: /攻略列表 [分类名]"""
        msg = event.message_str.strip()
        parts = msg.split(None, 1)

        if len(parts) < 2:
            yield self.plugin.utils.build_category_list_reply(event)
            return

        category = parts[1]
        strategies = self.plugin.data.get("strategies", [])
        matched = [s for s in strategies if s.get("category") == category]

        chain = []
        if not matched:
            chain.append(Plain(f"分类「{category}」下暂无攻略。\n发送 /攻略列表 查看所有分类。"))
            yield MessageEventResult(chain=chain)
            return

        text = f"{category} ({len(matched)}篇):\n\n"
        for i, st in enumerate(matched[:10], 1):
            text += f"  {i}. {st.get('name', '未命名')}"
            tws = st.get("trigger_words", [])
            if tws:
                text += f" [{', '.join(tws[:3])}]"
            status = "✓" if st.get("status") == "normal" else "⚠"
            text += f" {status}\n"

        if len(matched) > 10:
            text += f"\n... 等共 {len(matched)} 篇攻略"
        text += f"发送 /查攻略 <关键词> 搜索具体内容"
        chain.append(Plain(text))
        yield MessageEventResult(chain=chain)
