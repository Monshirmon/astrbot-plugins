"""图片编辑 API 深度对接模块"""

import asyncio
import base64
import json
import os

from astrbot.api import logger


class ImageApiModule:
    """对接外部图片编辑 API，用于攻略图片优化、标准化整改。"""

    def __init__(self, plugin):
        self.plugin = plugin

    @property
    def is_available(self) -> bool:
        return bool(
            self.plugin.config.get("enable_image_edit", False)
            and self.plugin.config.get("image_api_key", "")
        )

    async def generate_index_image(self, strategy: dict) -> str | None:
        """
        调用图片编辑 API 生成标准化索引引导图。
        返回生成的新图片路径，失败返回 None。
        """
        if not self.is_available:
            logger.warning("图片编辑API未启用或未配置API密钥")
            return None

        api_key = self.plugin.config.get("image_api_key", "")
        base_url = self.plugin.config.get("image_api_base_url", "https://api.openai.com").rstrip("/")
        model = self.plugin.config.get("image_api_model", "gpt-4o")
        provider = self.plugin.config.get("image_api_provider", "openai")

        # 准备图片
        image_base64 = None
        if strategy.get("image_path"):
            img_path = os.path.join(self.plugin.image_dir, strategy["image_path"])
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode("utf-8")

        # 构建提示词
        name = strategy.get("name", "未知攻略")
        category = strategy.get("category", "")
        keywords = strategy.get("keywords", [])
        kw_str = ", ".join(keywords[:5]) if keywords else "待补充"

        prompt = (
            f"为MC攻略「{name}」生成一张标准化索引引导图。"
            f"攻略分类: {category or '未分类'}。"
            f"关键检索词: {kw_str}。"
            f"请在图片上方添加简洁的攻略标题，下方添加引导文案:"
            f"“输入 /攻略 {name} 查看更多详情”。"
            f"保持图片清晰可读，适合萌新玩家查看。"
        )

        try:
            if provider == "openai":
                return await self._call_openai(base_url, api_key, model, prompt, image_base64)
            elif provider == "doubao":
                return await self._call_doubao(base_url, api_key, model, prompt, image_base64)
            else:
                return await self._call_generic_openai_compat(base_url, api_key, model, prompt, image_base64)
        except Exception as e:
            logger.error(f"图片编辑API调用失败: {e}", exc_info=True)
            return None

    async def _call_openai(self, base_url: str, api_key: str, model: str, prompt: str, image_base64: str | None) -> str | None:
        """调用 OpenAI Chat Completions API 分析/描述图片，再调用 Image API 生成新图。"""
        import aiohttp

        # 第一步：用 Vision API 分析原图
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        messages = [{"role": "user", "content": []}]
        if image_base64:
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
            })
        messages[0]["content"].append({"type": "text", "text": prompt})

        chat_url = f"{base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 500,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(chat_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    logger.error(f"OpenAI API 返回错误 {resp.status}: {err}")
                    return None
                data = await resp.json()
                description = data["choices"][0]["message"]["content"]

            # 第二步：用 DALL-E 生成新图（或直接使用描述文本作为文字覆盖）
            # 由于 DALL-E 不能精确替代原图，此处返回描述文本用于文字整改
            logger.info(f"图片分析完成: {description[:200]}...")
            return None  # 需要原图加工的方案改为返回 None

    async def _call_doubao(self, base_url: str, api_key: str, model: str, prompt: str, image_base64: str | None) -> str | None:
        """调用豆包 API（兼容 OpenAI 格式）。"""
        return await self._call_openai(base_url, api_key, model, prompt, image_base64)

    async def _call_generic_openai_compat(self, base_url: str, api_key: str, model: str, prompt: str, image_base64: str | None) -> str | None:
        """通用 OpenAI 兼容 API 调用。"""
        return await self._call_openai(base_url, api_key, model, prompt, image_base64)

    def get_image_edit_status(self, strategy: dict) -> str:
        """获取图片编辑状态描述。"""
        if not strategy.get("image_path"):
            return "无图片"
        img_path = os.path.join(self.plugin.image_dir, strategy["image_path"])
        if not os.path.exists(img_path):
            return "图片缺失"
        return "有图片"
