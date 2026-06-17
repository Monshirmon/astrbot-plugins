"""批量资源上传 & 自动建库模块"""

import os
import re
import zipfile
from datetime import datetime

from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import Image, Plain
from astrbot.api import logger


class ResourceUploadModule:
    """批量资源上传 & 自动建库模块"""

    def __init__(self, plugin):
        self.plugin = plugin

    def _parse_upload_command(self, msg: str) -> tuple[str, str, str]:
        """
        解析上传命令，返回 (name, category, remaining_text)。
        格式: /上传 攻略名 分类名 [图片...] [文字...]
        第二参数直接作为分类名，新分类自动添加。
        """
        # 去掉指令前缀
        text = msg.strip()
        for prefix in ["/上传攻略", "/上传", "上传攻略", "上传"]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break

        parts = text.split(None, 2)
        name = parts[0] if len(parts) > 0 else ""
        category = parts[1] if len(parts) > 1 else ""
        remaining = parts[2] if len(parts) > 2 else ""

        return name, category, remaining.strip()

    async def _collect_images_from_message(self, event: AstrMessageEvent) -> list[str]:
        """从消息中收集所有图片组件。"""
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
        """
        上传攻略。
        格式: /上传 攻略名 分类名 [图片...] [额外文字...]
        发送的图片全部收录，命令后面的文字自动作为攻略文字内容。
        """
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return

        msg = event.message_str.strip()
        name, category, remaining_text = self._parse_upload_command(msg)

        if not name:
            yield event.plain_result(
                "格式: /上传 <攻略名> <分类名> [图片...] [文字...]\n"
                "可选分类: " + ", ".join(self.plugin.data.get("categories", [])[:8])
            )
            return

        if not category:
            category = self.plugin.utils.guess_category_from_name(name)

        if category and category not in self.plugin.data.get("categories", []):
            self.plugin.utils.add_category(category)

        # 收集全部图片
        image_paths = await self._collect_images_from_message(event)

        # 自动用名称作为触发词
        trigger_words = [name.strip()]

        # 检测触发词冲突并自动解决
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
            "modify_log": [{
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "action": "upload",
                "detail": f"上传, {len(image_paths)}张图片"
            }],
        }

        self.plugin.data.setdefault("strategies", []).append(strategy)
        await self.plugin.utils.save_data_async()
        self.plugin.utils.add_log("上传攻略", f"名称: {name}, 触发词: {', '.join(trigger_words)}, 分类: {category or '未分类'}, 图片: {len(image_paths)}张", str(event.get_sender_id()))

        # 新收录后尝试更新索引图
        await self.plugin.utils.regenerate_index_image()

        status_text = "已规范" if strategy["status"] == "normal" else "待整改(缺少分类/图片)"
        result_text = (
            f"攻略「{name}」上传成功！\n"
            f"触发词: {', '.join(trigger_words)}\n"
            f"分类: {category or '未分类'}\n"
            f"图片: {len(image_paths)}张\n"
            f"状态: {status_text}"
        )
        if conflict_msgs:
            result_text += "\n" + "\n".join(conflict_msgs)
        yield event.plain_result(result_text)

    # ---- 批量打包上传 ----

    async def upload_batch(self, event: AstrMessageEvent):
        """批量上传攻略资源包（ZIP）。用法: /上传 批量 <附带ZIP文件>"""
        if not self.plugin.utils.is_admin(event):
            denied = self.plugin.utils.permission_denied_result(event)
            if denied:
                yield denied
            return

        msg = event.message_str.strip()
        # 解析批量命令
        text = msg
        for prefix in ["/上传攻略", "/上传", "上传攻略", "上传"]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        if not text.startswith("批量"):
            yield event.plain_result("格式: /上传 批量 <附带ZIP压缩包>")
            return

        messages = event.get_messages()
        zip_path = None

        for comp in messages:
            if hasattr(comp, "file") and comp.file and os.path.exists(comp.file):
                if comp.file.lower().endswith(".zip"):
                    zip_path = comp.file
                    break

        if not zip_path:
            yield event.plain_result("未找到ZIP压缩包。请将攻略资源打包为ZIP文件发送。")
            return

        try:
            extracted_dir = os.path.join(self.plugin.data_dir, f"temp_extract_{self.plugin.utils.generate_strategy_id()}")
            os.makedirs(extracted_dir, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extracted_dir)

            uploaded = 0
            failed = 0
            results = []

            for root, dirs, files in os.walk(extracted_dir):
                txt_files = [f for f in files if self.plugin.utils.is_text_file(f)]
                img_files = [f for f in files if self.plugin.utils.is_image_file(f)]

                for txt_file in txt_files:
                    filepath = os.path.join(root, txt_file)
                    try:
                        related_images = []
                        for img_file in img_files:
                            img_path = os.path.join(root, img_file)
                            saved = await self._copy_image_to_storage(img_path)
                            if saved:
                                related_images.append(saved)

                        strategy = self._create_strategy_from_text(filepath, txt_file, related_images)
                        if strategy:
                            self.plugin.data.setdefault("strategies", []).append(strategy)
                            uploaded += 1
                            results.append(f"  + {txt_file}")
                        else:
                            failed += 1
                    except Exception as e:
                        failed += 1
                        results.append(f"  x {txt_file}: {e}")

                standalone = [f for f in img_files if not any(t.replace('.txt','').replace('.md','') in f for t in txt_files)]
                for img_file in standalone:
                    img_path = os.path.join(root, img_file)
                    try:
                        saved = await self._copy_image_to_storage(img_path)
                        if saved:
                            strategy = self._create_strategy_from_image(img_file, [saved])
                            self.plugin.data.setdefault("strategies", []).append(strategy)
                            uploaded += 1
                            results.append(f"  + {img_file}")
                    except Exception as e:
                        failed += 1
                        results.append(f"  x {img_file}: {e}")

            await self.plugin.utils.save_data_async()
            self.plugin.utils.add_log("批量上传", f"成功: {uploaded}, 失败: {failed}", str(event.get_sender_id()))

            await self.plugin.utils.regenerate_index_image()

            import shutil
            try:
                shutil.rmtree(extracted_dir)
            except Exception:
                pass

            summary = f"批量上传完成: 成功 {uploaded} 篇, 失败 {failed} 篇\n\n" + "\n".join(results[:15])
            if len(results) > 15:
                summary += f"\n... 等共 {len(results)} 个文件"
            yield event.plain_result(summary)

        except zipfile.BadZipFile:
            yield event.plain_result("无效的ZIP文件，请检查文件格式。")
        except Exception as e:
            logger.error(f"批量上传异常: {e}", exc_info=True)
            yield event.plain_result(f"批量上传失败: {e}")

    # ---- 辅助方法 ----

    async def _copy_image_to_storage(self, source_path: str) -> str | None:
        import shutil
        try:
            ext = os.path.splitext(source_path)[1] or ".png"
            sid = self.plugin.utils.generate_strategy_id()
            dst_name = f"{sid}{ext}"
            dst = os.path.join(self.plugin.image_dir, dst_name)
            shutil.copy(source_path, dst)
            return dst_name
        except Exception as e:
            logger.error(f"复制图片失败 {source_path}: {e}")
            return None

    def _create_strategy_from_text(self, filepath: str, filename: str, related_images: list[str]) -> dict | None:
        content = self.plugin.utils.read_text_file(filepath)
        name = os.path.splitext(filename)[0]
        category = self.plugin.utils.guess_category_from_name(name)

        return {
            "id": self.plugin.utils.generate_strategy_id(),
            "name": name,
            "category": category,
            "subcategory": "",
            "trigger_words": [name.strip()],
            "status": "pending_review" if not category else "needs_image_edit" if not related_images else "normal",
            "text_content": content[:4000],
            "image_paths": related_images,
            "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modify_log": [{"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "action": "batch_upload", "detail": f"批量: {filename}"}],
        }

    def _create_strategy_from_image(self, filename: str, image_paths: list[str]) -> dict:
        name = os.path.splitext(filename)[0]
        category = self.plugin.utils.guess_category_from_name(name)

        return {
            "id": self.plugin.utils.generate_strategy_id(),
            "name": name,
            "category": category,
            "subcategory": "",
            "trigger_words": [name.strip()],
            "status": "pending_review" if not category else "needs_image_edit",
            "text_content": "",
            "image_paths": image_paths,
            "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modify_log": [{"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "action": "batch_upload", "detail": f"批量图片: {filename}"}],
        }
