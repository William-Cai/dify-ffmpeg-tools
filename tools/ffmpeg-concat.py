from collections.abc import Generator
from typing import Any
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class FfmpegConcatTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage]:
        raw_urls = tool_parameters.get("video_urls") or "[]"
        output_name = (
            (tool_parameters.get("output_name") or "merged_video").strip()
            or "merged_video"
        )

        # ---- 解析 URL 列表 ----
        try:
            urls = json.loads(raw_urls) if isinstance(raw_urls, str) else raw_urls
        except Exception:
            yield self.create_text_message(
                f"video_urls 不是合法 JSON：{str(raw_urls)[:200]}"
            )
            return
        if not isinstance(urls, list):
            yield self.create_text_message("video_urls 必须是 JSON 数组")
            return
        urls = [u.strip() for u in urls if isinstance(u, str) and u.strip()]
        if not urls:
            yield self.create_text_message("video_urls 为空")
            return

        tmpdir = Path(tempfile.mkdtemp(prefix="merge_"))
        try:
            # ---- 1. 下载 ----
            local_files = []
            with httpx.Client(timeout=300, follow_redirects=True) as client:
                for i, url in enumerate(urls):
                    ext = ".mp4"
                    suffix = Path(urlparse(url).path).suffix.lower()
                    if suffix in (".mp4", ".mov", ".webm", ".mkv"):
                        ext = suffix
                    p = tmpdir / f"part_{i:02d}{ext}"
                    with client.stream("GET", url) as r:
                        r.raise_for_status()
                        with open(p, "wb") as f:
                            for chunk in r.iter_bytes(chunk_size=1 << 20):
                                f.write(chunk)
                    local_files.append(p)

            yield self.create_text_message(
                f"已下载 {len(local_files)} 段视频，开始合并……"
            )

            # ---- 2. 单段直通 ----
            if len(local_files) == 1:
                with open(local_files[0], "rb") as f:
                    blob = f.read()
                yield self.create_blob_message(
                    blob=blob,
                    meta={"mime_type": "video/mp4", "filename": f"{output_name}.mp4"},
                )
                yield self.create_text_message("只有一段视频，未做合并，直接返回。")
                return

            # ---- 3. 写 concat 列表 ----
            list_file = tmpdir / "concat.txt"
            with open(list_file, "w", encoding="utf-8") as f:
                for p in local_files:
                    safe = str(p).replace("'", r"'\''")
                    f.write(f"file '{safe}'\n")

            output = tmpdir / f"{output_name}.mp4"

            # ---- 4. 层 1: 直接 copy ----
            strategy = "stream_copy"
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c", "copy",
                "-movflags", "+faststart",
                str(output),
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)

            # ---- 5. 层 2: 重编码 ----
            if r.returncode != 0:
                yield self.create_text_message(
                    "copy 模式失败，降级为重编码。原因：" + (r.stderr or "")[:200]
                )
                strategy = "reencode"
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", str(list_file),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
                    "-movflags", "+faststart",
                    str(output),
                ]
                r = subprocess.run(cmd, capture_output=True, text=True)

            # ---- 6. 层 3: filter_complex 归一 ----
            if r.returncode != 0:
                yield self.create_text_message(
                    "重编码失败，降级为 filter_complex 归一。原因："
                    + (r.stderr or "")[:200]
                )
                strategy = "filter_complex"

                W, H, FPS = 720, 1280, 30.0
                try:
                    probe = subprocess.run(
                        ["ffprobe", "-v", "error", "-print_format", "json",
                         "-show_streams", str(local_files[0])],
                        capture_output=True, text=True,
                    )
                    pdata = json.loads(probe.stdout)
                    for s in pdata.get("streams", []):
                        if s.get("codec_type") == "video":
                            W = int(s.get("width") or W)
                            H = int(s.get("height") or H)
                            fr = s.get("r_frame_rate", "30/1")
                            n, d = fr.split("/")
                            FPS = float(n) / float(d) if float(d) else 30.0
                            break
                except Exception:
                    pass

                inputs = []
                for p in local_files:
                    inputs += ["-i", str(p)]

                n = len(local_files)
                parts = []
                for i in range(n):
                    has_audio = False
                    try:
                        pinfo = subprocess.run(
                            ["ffprobe", "-v", "error", "-print_format", "json",
                             "-show_streams", str(local_files[i])],
                            capture_output=True, text=True,
                        )
                        pd = json.loads(pinfo.stdout)
                        has_audio = any(
                            s.get("codec_type") == "audio"
                            for s in pd.get("streams", [])
                        )
                    except Exception:
                        pass

                    parts.append(
                        f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
                        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS},"
                        f"format=yuv420p[v{i}]"
                    )
                    if has_audio:
                        parts.append(
                            f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:"
                            f"channel_layouts=stereo[a{i}]"
                        )
                    else:
                        parts.append(
                            f"anullsrc=channel_layout=stereo:sample_rate=44100,"
                            f"atrim=0:15,asetpts=PTS-STARTPTS[a{i}]"
                        )

                concat_in = "".join(f"[v{i}][a{i}]" for i in range(n))
                parts.append(f"{concat_in}concat=n={n}:v=1:a=1[vout][aout]")
                filter_complex = ";".join(parts)

                cmd = ["ffmpeg", "-y"] + inputs + [
                    "-filter_complex", filter_complex,
                    "-map", "[vout]", "-map", "[aout]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    str(output),
                ]
                r = subprocess.run(cmd, capture_output=True, text=True)

            # ---- 7. 全部失败 ----
            if r.returncode != 0:
                yield self.create_text_message(
                    "ffmpeg 合并失败：" + (r.stderr or "")[:500]
                )
                return

            # ---- 8. 返回 ----
            with open(output, "rb") as f:
                blob = f.read()

            yield self.create_blob_message(
                blob=blob,
                meta={"mime_type": "video/mp4", "filename": f"{output_name}.mp4"},
            )
            yield self.create_json_message({
                "status": "success",
                "part_count": len(local_files),
                "strategy": strategy,
                "output_name": f"{output_name}.mp4",
                "size_bytes": len(blob),
            })

        except Exception as e:
            yield self.create_text_message("合并过程中出错：" + str(e)[:500])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)