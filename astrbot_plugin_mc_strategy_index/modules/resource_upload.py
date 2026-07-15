"""批量资源上传 & 自动建库模块"""

import os
import re
import zipfile
from datetime import datetime

from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import Image, Plain
from astrbot.api import logger


class ResourceUploadModule:

    def __init__(self, plugin):
        self.plugin = plugin

    def _parse_upload_command(self, event: AstrMessageEvent) -> tuple[str, str, str]:
        """
        从消息组件中解析命令，返回 (name, category, remaining_text)。
        直接从 Plain 组件中取文本，Image 组件独立收集，避免图片导致 message_str 错乱。
        """
        messages = event.get_messages()
        all_text_parts = []
        for comp in messages:
            if isinstance(comp, Plain):
                all_text_parts.append(comp.text)

        full_text = " ".join(all_text_parts).strip()

        # 去掉指令前缀
        for prefix in ["/上传攻略", "/上传", "上传攻略", "上传"]:
            if full_text.startswith(prefix):
                full_text = full_text[len(prefix):].strip()
                break

        # 取第一个词作为 name
        parts = full_text.split(None, 2)
        name = parts[0] if len(parts) > 0 else ""
        category = parts[1] if len(parts) > 1 else ""
        remaining = parts[2] if len(parts) > 2 else ""

        return name, category, remaining.strip()

    async def _collect_images_from_message(self, event: AstrMessageEvent) -> list[str]:
        image_paths = []
        messages = event.get_messages()
        import shutil
        for comp in messages:
            if isinstance(comp, Image):
                if comp.file and os.path.exists(comp.file):
                    src = comp.file
                    ext = os.path.splitext(src)[1] or ".png"
                    sid = self.plugin.utils.generate_strategy_id()
                    dst_name = f"{sid}{ext}"
                    dst = os.path.join(self.plugin.image_dir, dst_name)
                    try:
                        shutil.copy(src, dst)
                        image_paths.append(dst_name)
                    except Exception as e:
                        logger.error(f"保存图片失败: {e}")
                elif comp.url:
                    downloaded = await self.plugin.utils.download_media_file(comp.url, "image")
                    if downloaded:
                        image_paths.append(downloaded)
        return image_paths

    # ---- 单文件上传 ----

    async def upload_single_file(self, event: AstrMessageEvent):
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return

        name, category, remaining_text = self._parse_upload_command(event)

        if not name:
            yield event.plain_result(
                "格式: /上传攻略 <攻略名> <分类名> [图片...] [文字...]\n"
                "分类自动创建，发送的图片全部收录。"
            )
            return

        if not category:
            category = self.plugin.utils.guess_category_from_name(name)

        if category and category not in self.plugin.data.get("categories", []):
            self.plugin.utils.add_category(category)

        image_paths = await self._collect_images_from_message(event)
        trigger_words = [name.strip()]

        conflicts = self.plugin.utils.find_duplicate_trigger_words(trigger_words)
        conflict_msgs = []
        if conflicts:
            removed_from = []
            for tw, old_name in conflicts.items():
                removed_from.append(f"「{tw}」(原归属: {old_name})")
            self.plugin.utils.resolve_trigger_conflicts(trigger_words)
            conflict_msgs.append("触发词冲突已自动解决: " + ", ".join(removed_from))

        strategy = {
            "id": self.plugin.utils.generate_strategy_id(),
            "name": name,
            "category": category,
            "subcategory": "",
            "trigger_words": trigger_words,
            "status": "pending_review" if not category else "needs_image_edit" if not image_paths else "normal",
            "text_content": remaining_text[:4000],
            "image_paths": image_paths,
            "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modify_log": [{"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "action": "upload", "detail": f"上传, {len(image_paths)}张图片"}],
        }

        self.plugin.data.setdefault("strategies", []).append(strategy)
        await self.plugin.utils.save_data_async()
        self.plugin.utils.add_log("上传攻略", f"{name}, 触发词: {', '.join(trigger_words)}, 分类: {category or '未分类'}", str(event.get_sender_id()))

        await self.plugin.utils.regenerate_index_image()

        status_text = "已规范" if strategy["status"] == "normal" else "待整改(缺少分类/图片)"
        result_text = f"攻略「{name}」上传成功！\n触发词: {', '.join(trigger_words)}\n分类: {category or '未分类'}\n图片: {len(image_paths)}张\n状态: {status_text}"
        if conflict_msgs:
            result_text += "\n" + "\n".join(conflict_msgs)
        yield event.plain_result(result_text)

    # ---- 批量上传 ----

    async def upload_batch(self, event: AstrMessageEvent):
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return

        msg = event.message_str.strip()
        text = msg
        for prefix in ["/上传攻略", "/上传", "上传攻略", "上传"]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        if not text.startswith("批量"):
            yield event.plain_result("格式: /上传攻略 批量 <附带ZIP压缩包>")
            return

        messages = event.get_messages()
        zip_path = None
        for comp in messages:
            if hasattr(comp, "file") and comp.file and os.path.exists(comp.file):
                if comp.file.lower().endswith(".zip"):
                    zip_path = comp.file
                    break
        if not zip_path:
            yield event.plain_result("未找到ZIP压缩包。")
            return

        try:
            extracted_dir = os.path.join(self.plugin.data_dir, f"temp_{self.plugin.utils.generate_strategy_id()}")
            os.makedirs(extracted_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extracted_dir)

            uploaded, failed = 0, 0
            results = []
            for root, dirs, files in os.walk(extracted_dir):
                txt_files = [f for f in files if self.plugin.utils.is_text_file(f)]
                img_files = [f for f in files if self.plugin.utils.is_image_file(f)]
                for txt_file in txt_files:
                    filepath = os.path.join(root, txt_file)
                    try:
                        imgs = []
                        for img_file in img_files:
                            saved = await self._copy_image(os.path.join(root, img_file))
                            if saved:
                                imgs.append(saved)
                        st = self._strategy_from_text(filepath, txt_file, imgs)
                        if st:
                            self.plugin.data.setdefault("strategies", []).append(st)
                            uploaded += 1
                            results.append(f"  + {txt_file}")
                    except Exception as e:
                        failed += 1
                        results.append(f"  x {txt_file}: {e}")
                standalone = [f for f in img_files if not any(t.replace('.txt','').replace('.md','') in f for t in txt_files)]
                for img_file in standalone:
                    try:
                        saved = await self._copy_image(os.path.join(root, img_file))
                        if saved:
                            st = self._strategy_from_image(img_file, [saved])
                            self.plugin.data.setdefault("strategies", []).append(st)
                            uploaded += 1
                            results.append(f"  + {img_file}")
                    except Exception as e:
                        failed += 1
            await self.plugin.utils.save_data_async()
            self.plugin.utils.add_log("批量上传", f"成功: {uploaded}, 失败: {failed}", str(event.get_sender_id()))
            await self.plugin.utils.regenerate_index_image()
            import shutil
            try:
                shutil.rmtree(extracted_dir)
            except Exception:
                pass
            yield event.plain_result(f"批量上传完成: 成功 {uploaded}, 失败 {failed}\n" + "\n".join(results[:15]))
        except Exception as e:
            logger.error(f"批量上传异常: {e}", exc_info=True)
            yield event.plain_result(f"批量上传失败: {e}")

    async def _copy_image(self, source_path: str) -> str | None:
        import shutil
        try:
            ext = os.path.splitext(source_path)[1] or ".png"
            dst_name = f"{self.plugin.utils.generate_strategy_id()}{ext}"
            shutil.copy(source_path, os.path.join(self.plugin.image_dir, dst_name))
            return dst_name
        except Exception:
            return None

    def _strategy_from_text(self, filepath, filename, imgs):
        content = self.plugin.utils.read_text_file(filepath)
        name = os.path.splitext(filename)[0]
        cat = self.plugin.utils.guess_category_from_name(name)
        return {
            "id": self.plugin.utils.generate_strategy_id(), "name": name, "category": cat,
            "subcategory": "", "trigger_words": [name.strip()],
            "status": "pending_review" if not cat else "needs_image_edit" if not imgs else "normal",
            "text_content": content[:4000], "image_paths": imgs,
            "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modify_log": [{"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "action": "batch", "detail": filename}],
        }

    def _strategy_from_image(self, filename, imgs):
        name = os.path.splitext(filename)[0]
        cat = self.plugin.utils.guess_category_from_name(name)
        return {
            "id": self.plugin.utils.generate_strategy_id(), "name": name, "category": cat,
            "subcategory": "", "trigger_words": [name.strip()],
            "status": "pending_review" if not cat else "needs_image_edit",
            "text_content": "", "image_paths": imgs,
            "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modify_log": [{"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "action": "batch_image", "detail": filename}],
        }
