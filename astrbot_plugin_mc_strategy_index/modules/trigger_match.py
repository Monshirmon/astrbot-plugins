"""严格匹配触发词模块 — 类似参考插件的检测词但严格完全匹配"""

from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger


class TriggerMatchModule:
    """监听群聊消息，对触发词做严格完全匹配（大小写不敏感）并返回关联攻略。"""

    def __init__(self, plugin):
        self.plugin = plugin

    async def handle_message(self, event: AstrMessageEvent) -> dict | None:
        """
        检查消息是否完全匹配某个触发词。
        返回匹配信息: {"strategies": [...], "trigger_word": "xxx"}
        不匹配则返回 None。
        """
        msg = event.message_str.strip()
        if not msg:
            return None

        matched = self.plugin.utils.match_by_trigger_word(msg)
        if matched:
            logger.info(f"触发词匹配: {msg} -> {[s['name'] for s in matched]}")
            return {"strategies": matched, "trigger_word": msg}
        return None

    async def send_trigger_reply(self, event: AstrMessageEvent, result: dict):
        """发送触发匹配的回复。"""
        strategies = result["strategies"]
        trigger_word = result["trigger_word"]
        reply = self.plugin.utils.build_trigger_reply(event, strategies, trigger_word)
        yield reply
        event.stop_event()
