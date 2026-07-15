"""严格匹配触发词模块"""

from astrbot.api.event import AstrMessageEvent


class TriggerMatchModule:

    def __init__(self, plugin):
        self.plugin = plugin

    async def handle_message(self, event: AstrMessageEvent) -> dict | None:
        msg = event.message_str.strip()
        if not msg:
            return None
        matched = self.plugin.utils.match_by_trigger_word(msg)
        if matched:
            return {"strategies": matched, "trigger_word": msg}
        return None

    async def send_trigger_reply(self, event: AstrMessageEvent, result: dict):
        strategies = result["strategies"]
        trigger_word = result["trigger_word"]
        reply = self.plugin.utils.build_trigger_reply(event, strategies, trigger_word)
        yield reply
        event.stop_event()
