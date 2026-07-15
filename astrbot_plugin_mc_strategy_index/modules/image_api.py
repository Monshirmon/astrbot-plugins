"""图片编辑 API 深度对接模块"""

import base64
import json
import os

from astrbot.api import logger


class ImageApiModule:

    def __init__(self, plugin):
        self.plugin = plugin

    @property
    def is_available(self) -> bool:
        return bool(
            self.plugin.config.get("enable_image_edit", False)
            and self.plugin.config.get("image_api_key", "")
        )

    async def generate_index_image(self, strategy: dict) -> str | None:
        if not self.is_available:
            return None

        api_key = self.plugin.config.get("image_api_key", "")
        base_url = self.plugin.config.get("image_api_base_url", "https://api.openai.com").rstrip("/")
        model = self.plugin.config.get("image_api_model", "gpt-4o")
        provider = self.plugin.config.get("image_api_provider", "openai")

        image_base64 = None
        imgs = strategy.get("image_paths", [])
        if imgs:
            img_path = os.path.join(self.plugin.image_dir, imgs[0])
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode("utf-8")

        name = strategy.get("name", "未知攻略")
        category = strategy.get("category", "")
        kws = strategy.get("trigger_words", strategy.get("keywords", []))
        kw_str = ", ".join(kws[:5]) if kws else "待补充"

        prompt = (
            f"为MC攻略「{name}」生成一张标准化索引引导图。"
            f"攻略分类: {category or '未分类'}。关键检索词: {kw_str}。"
            f"请在图片上方添加简洁的攻略标题，下方添加引导文案:'输入触发词获取详情'。"
            f"保持图片清晰可读，适合萌新玩家查看。"
        )

        try:
            import aiohttp
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            messages = [{"role": "user", "content": []}]
            if image_base64:
                messages[0]["content"].append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}})
            messages[0]["content"].append({"type": "text", "text": prompt})
            chat_url = f"{base_url}/v1/chat/completions"
            payload = {"model": model, "messages": messages, "max_tokens": 500}
            async with aiohttp.ClientSession() as session:
                async with session.post(chat_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        desc = data["choices"][0]["message"]["content"]
                        logger.info(f"图片分析完成: {desc[:200]}...")
        except Exception as e:
            logger.error(f"图片编辑API调用失败: {e}")
        return None
