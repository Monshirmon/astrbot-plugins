import asyncio
import hashlib
import json
import os
import random
import time
from datetime import datetime
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageEventResult
from astrbot.api.message_components import Image, Plain


class StrategyUtils:

    def __init__(self, plugin):
        self.plugin = plugin
        self.default_categories = []

    # ---- data ----

    def load_data(self) -> dict:
        if os.path.exists(self.plugin.data_file):
            try:
                with open(self.plugin.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for st in data.get("strategies", []):
                        if "image_path" in st and "image_paths" not in st:
                            old = st.pop("image_path")
                            st["image_paths"] = [old] if old else []
                        st.pop("image_hash", None)
                        st.pop("keywords", None)
                    return data
            except Exception as e:
                logger.error(f"load data failed: {e}")
        default = {"strategies": [], "categories": [], "logs": [], "index_image_path": ""}
        self._save_data_sync(default)
        return default

    def normalize_data(self, data: dict) -> dict:
        if not isinstance(data, dict):
            data = {}
        data.setdefault("strategies", [])
        data.setdefault("categories", [])
        data.setdefault("logs", [])
        data.setdefault("index_image_path", "")
        for st in data.get("strategies", []):
            st.setdefault("id", "")
            st.setdefault("name", "")
            st.setdefault("category", "")
            st.setdefault("subcategory", "")
            st.setdefault("trigger_words", [])
            st.setdefault("status", "pending_review")
            st.setdefault("text_content", "")
            st.setdefault("image_paths", [])
            st.setdefault("upload_time", "")
            st.setdefault("last_modified", "")
            st.setdefault("modify_log", [])
            st.pop("keywords", None)
        return data

    def _save_data_sync(self, data: dict):
        try:
            with open(self.plugin.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"save data failed: {e}")

    async def save_data_async(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._save_data_sync, self.plugin.data)

    # ---- log ----

    def add_log(self, action: str, detail: str, operator: str):
        entry = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "action": action, "detail": detail, "operator": operator}
        self.plugin.data.setdefault("logs", []).append(entry)
        if len(self.plugin.data["logs"]) > 500:
            self.plugin.data["logs"] = self.plugin.data["logs"][-500:]

    # ---- auth ----

    def is_admin(self, event: AstrMessageEvent) -> bool:
        if event.is_admin():
            return True
        sender_id = str(event.get_sender_id())
        whitelist = {str(uid) for uid in self.plugin.config.get("admin_whitelist", [])}
        return sender_id in whitelist

    def permission_denied_result(self, event: AstrMessageEvent, message: str = "权限不足"):
        if self.plugin.config.get("notify_permission_denied", True):
            return event.plain_result(message)
        return None

    # ---- files ----

    def generate_strategy_id(self) -> str:
        return hashlib.md5(str(time.time()).encode()).hexdigest()[:12]

    def is_image_file(self, filename: str) -> bool:
        return filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"))

    def is_text_file(self, filename: str) -> bool:
        return filename.lower().endswith((".txt", ".md", ".log"))

    def read_text_file(self, filepath: str, max_chars: int = 4000) -> str:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read(max_chars)
        except UnicodeDecodeError:
            try:
                with open(filepath, "r", encoding="gbk") as f:
                    return f.read(max_chars)
            except Exception:
                return ""
        except Exception:
            return ""

    def guess_category_from_name(self, name: str) -> str:
        name_lower = name.lower()
        mapping = {
            "战斗": "战斗技巧", "boss": "战斗技巧", "怪物": "战斗技巧", "pvp": "战斗技巧",
            "挖矿": "资源收集", "矿物": "资源收集", "收集": "资源收集", "资源": "资源收集", "农场": "资源收集",
            "建筑": "建筑教程", "房子": "建筑教程", "装饰": "建筑教程",
            "红石": "红石科技", "活塞": "红石科技", "电路": "红石科技", "机器": "红石科技",
            "生存": "生存指南", "新手": "生存指南", "入门": "生存指南",
            "探索": "探索冒险", "地图": "探索冒险", "遗迹": "探索冒险",
            "模组": "模组攻略", "mod": "模组攻略",
            "服务器": "服务器玩法",
        }
        for keyword, category in mapping.items():
            if keyword in name_lower:
                return category
        return ""

    # ---- trigger words ----

    def match_by_trigger_word(self, msg: str) -> list[dict]:
        msg_stripped = msg.strip()
        matched = []
        seen_ids = set()
        for st in self.plugin.data.get("strategies", []):
            for tw in st.get("trigger_words", []):
                if tw.strip().lower() == msg_stripped.lower() and st["id"] not in seen_ids:
                    matched.append(st)
                    seen_ids.add(st["id"])
                    break
        return matched

    def get_all_trigger_words(self) -> list[str]:
        words = set()
        for st in self.plugin.data.get("strategies", []):
            for tw in st.get("trigger_words", []):
                tw = tw.strip()
                if tw:
                    words.add(tw)
        return sorted(words)

    def find_duplicate_trigger_words(self, trigger_words: list[str], exclude_id: str = "") -> dict:
        conflicts = {}
        for tw in trigger_words:
            tw_lower = tw.strip().lower()
            for st in self.plugin.data.get("strategies", []):
                if exclude_id and st.get("id") == exclude_id:
                    continue
                for existing_tw in st.get("trigger_words", []):
                    if existing_tw.strip().lower() == tw_lower:
                        conflicts[tw] = st.get("name", "未知")
                        break
        return conflicts

    def resolve_trigger_conflicts(self, trigger_words: list[str], exclude_id: str = "") -> list[str]:
        cleaned = []
        for tw in trigger_words:
            tw_lower = tw.strip().lower()
            for st in self.plugin.data.get("strategies", []):
                if exclude_id and st.get("id") == exclude_id:
                    continue
                existing_tws = st.get("trigger_words", [])
                new_tws = [t for t in existing_tws if t.strip().lower() != tw_lower]
                if len(new_tws) < len(existing_tws):
                    st["trigger_words"] = new_tws
            cleaned.append(tw)
        return cleaned

    def match_strategies_by_name(self, query: str, limit: int = 5) -> list[dict]:
        results = []
        q = query.lower()
        for st in self.plugin.data.get("strategies", []):
            searchable = " ".join([
                st.get("name", ""), st.get("category", ""),
                st.get("subcategory", ""), st.get("text_content", ""),
                *st.get("trigger_words", []),
            ]).lower()
            if q in searchable:
                results.append(st)
            if len(results) >= limit:
                break
        return results

    # ---- message building ----

    def build_strategy_preview(self, strategy: dict, index: int = 0) -> str:
        lines = [f"【{index}】{strategy.get('name', '未命名')}" if index > 0 else f"攻略: {strategy.get('name', '未命名')}"]
        cat = strategy.get("category", "")
        sub = strategy.get("subcategory", "")
        if cat:
            lines.append(f"分类: {f'{cat}/{sub}' if sub else cat}")
        tws = strategy.get("trigger_words", [])
        if tws:
            lines.append(f"触发词: {', '.join(tws)}")
        txt = strategy.get("text_content", "").strip()
        if txt:
            lines.append(f"{txt[:200]}{'...' if len(txt) > 200 else ''}")
        status_map = {"normal": "已规范", "pending_review": "待整改", "needs_image_edit": "待优化图片"}
        lines.append(f"状态: {status_map.get(strategy.get('status', ''), '未知')}")
        return "\n".join(lines)

    def build_search_reply(self, event: AstrMessageEvent, strategies: list[dict], query: str) -> MessageEventResult:
        chain = []
        if not strategies:
            chain.append(Plain(f"未找到与「{query}」相关的攻略。\n发送 /攻略列表 查看全部"))
            return MessageEventResult(chain=chain)
        text = f"搜索「{query}」找到 {len(strategies)} 个攻略:\n\n"
        image_to_send = None
        for i, st in enumerate(strategies, 1):
            text += f"{self.build_strategy_preview(st, i)}\n\n"
            if image_to_send is None and st.get("image_paths"):
                full_path = os.path.join(self.plugin.image_dir, st["image_paths"][0])
                if os.path.exists(full_path):
                    image_to_send = full_path
        if len(strategies) > 1:
            text += "提示: 输入更精准的关键词可缩小范围。"
        chain.append(Plain(text.strip()))
        if image_to_send:
            chain.append(Image(file=image_to_send))
        return MessageEventResult(chain=chain)

    def build_trigger_reply(self, event: AstrMessageEvent, strategies: list[dict], trigger_word: str) -> MessageEventResult:
        chain = []
        if not strategies:
            chain.append(Plain(f"触发词「{trigger_word}」未匹配到任何攻略。"))
            return MessageEventResult(chain=chain)
        text_parts = []
        for st in strategies:
            name = st.get("name", "未命名")
            txt = st.get("text_content", "").strip()
            text_parts.append(f"【{name}】")
            if txt:
                text_parts.append(txt[:500])
            text_parts.append("")
        chain.append(Plain("\n".join(text_parts).strip()))
        for st in strategies:
            for img_path_rel in st.get("image_paths", []):
                full_path = os.path.join(self.plugin.image_dir, img_path_rel)
                if os.path.exists(full_path):
                    chain.append(Image(file=full_path))
        return MessageEventResult(chain=chain)

    # ---- index image ----

    async def regenerate_index_image(self) -> str | None:
        if not self.plugin.image_api.is_available:
            return None
        words = self.get_all_trigger_words()
        if not words:
            return None
        word_list = "\n".join(f"- {w}" for w in words)
        prompt = (
            "Generate a Minecraft strategy index guide image. Title: 'MC Guide Index' at top. "
            "Subtitle: 'Send these keywords to get guides'. List the following trigger words in the middle:\n"
            f"{word_list}\n"
            "Bottom text: 'Type any keyword above in the group chat'. Minecraft pixel art style, green/brown theme."
        )
        new_path = None
        try:
            import aiohttp
            api_key = self.plugin.config.get("image_api_key", "")
            base_url = self.plugin.config.get("image_api_base_url", "https://api.openai.com").rstrip("/")
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": "dall-e-3", "prompt": prompt, "n": 1, "size": "1024x1024", "quality": "standard"}
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{base_url}/v1/images/generations", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        image_url = data["data"][0].get("url")
                        if image_url and image_url.startswith("http"):
                            new_path = await self.download_media_file(image_url, "image")
                            if new_path:
                                self.plugin.data["index_image_path"] = new_path
                                await self.save_data_async()
        except Exception as e:
            logger.error(f"index image gen error: {e}")
        if not new_path:
            fake = {"name": "攻略索引", "category": "系统", "trigger_words": words}
            new_path = await self.plugin.image_api.generate_index_image(fake)
            if new_path:
                self.plugin.data["index_image_path"] = new_path
                await self.save_data_async()
        return new_path

    def get_index_image_reply(self, event: AstrMessageEvent) -> MessageEventResult:
        chain = []
        words = self.get_all_trigger_words()
        if not words:
            chain.append(Plain("暂无攻略触发词。管理员可通过 /上传攻略 <名称> <分类> 添加。"))
            return MessageEventResult(chain=chain)
        index_path = self.plugin.data.get("index_image_path", "")
        full_path = os.path.join(self.plugin.image_dir, index_path) if index_path else ""
        text = "可用攻略触发词 (直接发送即可获取攻略):\n\n"
        for w in words:
            names = [st.get("name", "?") for st in self.plugin.data.get("strategies", []) if w in st.get("trigger_words", [])]
            name_part = f" -> {', '.join(names[:2])}" if names else ""
            text += f"  {w}{name_part}\n"
        chain.append(Plain(text.strip()))
        if full_path and os.path.exists(full_path):
            chain.append(Image(file=full_path))
        elif not index_path:
            chain.append(Plain("\n索引图尚未生成，管理员使用 /巡检攻略 后自动生成。"))
        return MessageEventResult(chain=chain)

    def build_category_list_reply(self, event: AstrMessageEvent) -> MessageEventResult:
        chain = []
        categories = self.plugin.data.get("categories", [])
        strategies = self.plugin.data.get("strategies", [])
        if not categories:
            chain.append(Plain("暂无分类。发送 /上传攻略 <名称> <分类> 添加第一篇即可自动创建分类。"))
            return MessageEventResult(chain=chain)
        text = "可用攻略分类:\n"
        for cat in categories:
            count = sum(1 for s in strategies if s.get("category") == cat)
            text += f"  {cat} ({count}篇)\n"
        text += f"\n共 {len(strategies)} 篇 | /查攻略 <关键词> 搜索 | /索引 查看触发词"
        chain.append(Plain(text))
        return MessageEventResult(chain=chain)

    # ---- categories ----

    def add_category(self, name: str) -> bool:
        if name not in self.plugin.data.get("categories", []):
            self.plugin.data["categories"].append(name)
            return True
        return False

    def remove_category(self, name: str) -> bool:
        cats = self.plugin.data.get("categories", [])
        if name in cats:
            cats.remove(name)
            for st in self.plugin.data.get("strategies", []):
                if st.get("category") == name:
                    st["category"] = ""
                    st["status"] = "pending_review"
            return True
        return False

    async def download_media_file(self, url: str, media_type: str) -> str | None:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        fhash = hashlib.md5(content).hexdigest()
                        ext = ".png" if media_type == "image" else ".mp4" if media_type == "video" else ".amr"
                        filename = fhash + ext
                        target_dir = {"image": self.plugin.image_dir, "record": self.plugin.record_dir, "video": self.plugin.video_dir}[media_type]
                        path = os.path.join(target_dir, filename)
                        with open(path, "wb") as f:
                            f.write(content)
                        return filename
        except Exception as e:
            logger.error(f"download media failed({media_type}): {e}")
        return None

    def find_strategy_by_index(self, idx_str: str) -> dict | None:
        strategies = self.plugin.data.get("strategies", [])
        try:
            idx = int(idx_str) - 1
            if 0 <= idx < len(strategies):
                return strategies[idx]
        except ValueError:
            pass
        for st in strategies:
            if st.get("id") == idx_str or st.get("name") == idx_str:
                return st
        for st in strategies:
            if idx_str.lower() in st.get("name", "").lower():
                return st
        return None

    def get_strategy_index(self, idx_str: str) -> int:
        strategies = self.plugin.data.get("strategies", [])
        try:
            idx = int(idx_str) - 1
            if 0 <= idx < len(strategies):
                return idx
        except ValueError:
            pass
        for i, st in enumerate(strategies):
            if st.get("id") == idx_str or st.get("name") == idx_str:
                return i
        return -1

    def collect_referenced_images(self) -> set:
        refs = set()
        for st in self.plugin.data.get("strategies", []):
            for path in st.get("image_paths", []):
                if path:
                    refs.add(path)
        index_path = self.plugin.data.get("index_image_path", "")
        if index_path:
            refs.add(index_path)
        return refs

    def cleanup_unused_images(self):
        try:
            referenced = self.collect_referenced_images()
            removed = 0
            for name in os.listdir(self.plugin.image_dir):
                full_path = os.path.join(self.plugin.image_dir, name)
                if os.path.isfile(full_path) and name not in referenced:
                    try:
                        os.remove(full_path)
                        removed += 1
                    except Exception:
                        pass
            if removed > 0:
                logger.info(f"cleaned {removed} unused images")
        except Exception as e:
            logger.error(f"cleanup images failed: {e}")

    def build_builtin_trigger_reply(self, event: AstrMessageEvent, trigger_word: str) -> MessageEventResult | None:
        if trigger_word.strip() == "开光线":
            n = random.randint(1, 14)
            return event.plain_result(f"{n}线")
        return None
