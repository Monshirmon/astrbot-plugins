from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools
from astrbot.api import logger
import os

from .modules.resource_upload import ResourceUploadModule
from .modules.player_search import PlayerSearchModule
from .modules.admin_inspect import AdminInspectModule
from .modules.resource_management import ResourceManagementModule
from .modules.image_api import ImageApiModule
from .modules.trigger_match import TriggerMatchModule
from .modules.utils import StrategyUtils
from .webui.api import StrategyIndexWebUIApi


class MCStrategyIndexPlugin(Star):

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.data_dir = StarTools.get_data_dir("astrbot_plugin_mc_strategy_index")
        self.image_dir = os.path.join(self.data_dir, "images")
        self.record_dir = os.path.join(self.data_dir, "records")
        self.video_dir = os.path.join(self.data_dir, "videos")
        self.data_file = os.path.join(self.data_dir, "strategy_index.json")

        os.makedirs(self.image_dir, exist_ok=True)
        os.makedirs(self.record_dir, exist_ok=True)
        os.makedirs(self.video_dir, exist_ok=True)

        self.utils = StrategyUtils(self)
        self.data = self.utils.normalize_data(self.utils.load_data())

        self.upload_module = ResourceUploadModule(self)
        self.search_module = PlayerSearchModule(self)
        self.inspect_module = AdminInspectModule(self)
        self.manage_module = ResourceManagementModule(self)
        self.image_api = ImageApiModule(self)
        self.trigger_module = TriggerMatchModule(self)

        self.webui_api = StrategyIndexWebUIApi(self)
        self.webui_api.register()

    # ==================== 上传 ====================

    async def _do_upload(self, event: AstrMessageEvent):
        msg = event.message_str.strip()
        text = msg
        for prefix in ["/上传攻略", "/上传", "上传攻略", "上传"]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        if text.startswith("批量"):
            async for res in self.upload_module.upload_batch(event):
                yield res
        else:
            async for res in self.upload_module.upload_single_file(event):
                yield res

    @filter.command("上传攻略")
    async def cmd_upload_strategy(self, event):
        async for res in self._do_upload(event):
            yield res

    @filter.command("上传")
    async def cmd_upload(self, event):
        async for res in self._do_upload(event):
            yield res

    # ==================== 索引 ====================

    async def _do_index(self, event: AstrMessageEvent):
        try:
            reply = self.utils.get_index_image_reply(event)
            if reply:
                yield reply
        except Exception as e:
            yield event.plain_result(f"获取索引失败: {e}")

    @filter.command("索引")
    async def cmd_index(self, event):
        async for res in self._do_index(event):
            yield res

    @filter.command("攻略索引")
    async def cmd_strategy_index(self, event):
        async for res in self._do_index(event):
            yield res

    # ==================== 搜索 ====================

    @filter.command("查攻略")
    async def cmd_search(self, event: AstrMessageEvent):
        try:
            async for res in self.search_module.search_strategy(event):
                yield res
        except Exception as e:
            yield event.plain_result(f"查询失败: {e}")

    @filter.command("攻略列表")
    async def cmd_list(self, event: AstrMessageEvent):
        try:
            msg = event.message_str.strip()
            parts = msg.split(None, 1)
            if len(parts) > 1 and parts[1] == "all":
                async for res in self.manage_module.list_all_strategies(event):
                    yield res
            else:
                async for res in self.search_module.list_categories(event):
                    yield res
        except Exception as e:
            yield event.plain_result(f"获取列表失败: {e}")

    # ==================== 巡检/整改 ====================

    @filter.command("巡检攻略")
    async def cmd_inspect(self, event: AstrMessageEvent):
        try:
            async for res in self.inspect_module.inspect_library(event):
                yield res
        except Exception as e:
            yield event.plain_result(f"巡检失败: {e}")

    @filter.command("整改攻略")
    async def cmd_rectify(self, event: AstrMessageEvent):
        try:
            async for res in self.inspect_module.rectify_strategy(event):
                yield res
        except Exception as e:
            yield event.plain_result(f"整改失败: {e}")

    # ==================== 删除/编辑/替换 ====================

    @filter.command("删除攻略")
    async def cmd_delete(self, event: AstrMessageEvent):
        try:
            async for res in self.manage_module.delete_strategy(event):
                yield res
        except Exception as e:
            yield event.plain_result(f"删除失败: {e}")

    @filter.command("编辑攻略")
    async def cmd_edit(self, event: AstrMessageEvent):
        try:
            async for res in self.manage_module.edit_strategy(event):
                yield res
        except Exception as e:
            yield event.plain_result(f"编辑失败: {e}")

    @filter.command("替换攻略图")
    async def cmd_replace_image(self, event: AstrMessageEvent):
        try:
            async for res in self.manage_module.replace_image(event):
                yield res
        except Exception as e:
            yield event.plain_result(f"替换图片失败: {e}")

    @filter.command("攻略分类管理")
    async def cmd_category(self, event: AstrMessageEvent):
        try:
            async for res in self.manage_module.manage_categories(event):
                yield res
        except Exception as e:
            yield event.plain_result(f"分类管理失败: {e}")

    @filter.command("攻略日志")
    async def cmd_log(self, event: AstrMessageEvent):
        try:
            async for res in self.inspect_module.view_logs(event):
                yield res
        except Exception as e:
            yield event.plain_result(f"获取日志失败: {e}")

    # ==================== 消息监听 ====================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        msg = event.message_str.strip()
        if not msg:
            return

        # 内置触发词优先（不经过攻略库匹配）
        builtin = self.utils.build_builtin_trigger_reply(event, msg)
        if builtin:
            yield builtin
            return

        if msg.startswith("/"):
            return

        management_prefixes = [
            "上传攻略", "上传 ", "编辑攻略", "删除攻略",
            "查攻略", "攻略列表", "攻略分类管理", "攻略日志",
            "索引", "攻略索引", "巡检攻略", "整改攻略", "替换攻略图",
        ]
        for p in management_prefixes:
            if msg.startswith(p):
                return

        trigger_result = await self.trigger_module.handle_message(event)
        if trigger_result:
            async for res in self.trigger_module.send_trigger_reply(event, trigger_result):
                yield res
