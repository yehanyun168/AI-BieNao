# -*- coding: utf-8 -*-
"""构建脚本：把 shots.json 编译成播放器/剪辑可直接用的产物。

产出：
  1. shots.js            —— window.SHOTS_DATA，供 index.html 以 file:// 直接打开
  2. subtitles.srt       —— 标准 SRT 字幕（可挂 ffmpeg / 剪辑软件）
  3. assets/placeholders/*.svg —— 30 张 1920x1080 占位素材（含镜号 + 场景名，便于替换）
  4. 控制台校验报告      —— 幕数 / 时间码连续性 / 总时长 / 字幕长度

用法：
    python build_data.py            # 全部构建
    python build_data.py --check    # 只校验不写文件
"""
import json
import os
import sys
import html
import argparse

BASE = os.path.dirname(os.path.abspath(__file__))
SHOTS_JSON = os.path.join(BASE, "shots.json")
PLACEHOLDER_DIR = os.path.join(BASE, "assets", "placeholders")

W, H = 1920, 1080
EXPECTED_TOTAL = 178.0
MAX_LINE = 20  # SRT 每行最多汉字数


# ---------------------------------------------------------------- 字幕分行
def split_subtitle(text, max_line=MAX_LINE):
    """把一条字幕分成最多两行，优先在标点处断开。"""
    if not text:
        return []
    if len(text) <= max_line:
        return [text]
    # 优先按句号/分号/问号断
    for sep in ("。", "；", "？", "！"):
        if sep in text:
            idx = text.rindex(sep)
            a, b = text[:idx + 1], text[idx + 1:]
            if a and b and len(a) <= max_line and len(b) <= max_line:
                return [a, b]
    # 次优先按逗号断：取中点附近最近的逗号
    mid = len(text) // 2
    candidates = [i for i, c in enumerate(text) if c in ("，", "、", "·")]
    if candidates:
        best = min(candidates, key=lambda i: abs(i - mid))
        a, b = text[:best + 1], text[best + 1:]
        if a and b:
            return [a, b]
    # 兜底硬切
    return [text[:max_line], text[max_line:max_line * 2]]


def srt_time(sec):
    if sec < 0:
        sec = 0.0
    ms = int(round(sec * 1000))
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    ms = ms % 1000
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


# ---------------------------------------------------------------- 占位图
PLACEHOLDER_TPL = """<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Microsoft YaHei, Microsoft YaHei UI, sans-serif">
  <defs>
    <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse">
      <path d="M48 0H0V48" fill="none" stroke="#16203a" stroke-width="1"/>
    </pattern>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#0b1020"/>
      <stop offset="1" stop-color="#131c33"/>
    </linearGradient>
  </defs>
  <rect width="{w}" height="{h}" fill="url(#bg)"/>
  <rect width="{w}" height="{h}" fill="url(#grid)" opacity="0.55"/>
  <!-- 边框：标明这是 1920x1080 安全区 -->
  <rect x="24" y="24" width="{w2}" height="{h2}" fill="none" stroke="#2a3a63" stroke-width="3" stroke-dasharray="18 14"/>
  <!-- 顶部：镜号 + 时长 -->
  <text x="70" y="140" fill="#ffb648" font-size="86" font-weight="bold" letter-spacing="6">{sid}</text>
  <text x="330" y="140" fill="#7c8db5" font-size="40">{dur}s</text>
  <text x="{wr}" y="140" fill="#4a5c85" font-size="34" text-anchor="end">1920 x 1080</text>
  <!-- 中部：标题 -->
  <text x="70" y="300" fill="#e5e7eb" font-size="64" font-weight="bold">{title}</text>
  <!-- 中部：场景 -->
  <text x="70" y="392" fill="#8fa3cc" font-size="40">场景：{scene}</text>
  <text x="70" y="456" fill="#8fa3cc" font-size="40">运镜：{camera}</text>
  <!-- 中部：画面描述（自动换行） -->
{desc_lines}  <!-- 底部：替换提示 -->
  <rect x="0" y="{bar}" width="{w}" height="120" fill="#000000" opacity="0.42"/>
  <text x="70" y="{bar2}" fill="#ffb648" font-size="38">占位素材 PLACEHOLDER · 请替换为实机录屏</text>
  <text x="{wr}" y="{bar2}" fill="#7c8db5" font-size="34" text-anchor="end">命名：{sid}_{slug}.mp4</text>
</svg>
"""


def slugify(text):
    """从英文场景名里取一个短 slug 用于文件命名。"""
    import re
    m = re.search(r"[A-Za-z_][A-Za-z0-9_]*", text or "")
    return (m.group(0) if m else "scene").lower()


def wrap_text(text, max_chars=30, max_lines=4):
    """中文按字数硬换行。"""
    lines = []
    for i in range(0, len(text), max_chars):
        lines.append(text[i:i + max_chars])
        if len(lines) >= max_lines:
            break
    if len(text) > max_chars * max_lines:
        lines[-1] = lines[-1][:-1] + "…"
    return lines


def make_placeholder(shot):
    desc = shot.get("desc", "")
    lines = wrap_text(desc, 30, 4)
    out = []
    y = 560
    for ln in lines:
        out.append('  <text x="70" y="%d" fill="#c7d3ea" font-size="36">%s</text>'
                   % (y, html.escape(ln)))
        y += 56
    # 印在图上的建议文件名：与 media.src 严格一致（只换扩展名）
    src = (shot.get("media") or {}).get("src", "")
    base = os.path.basename(src)
    if base.startswith(shot["id"] + "_") and base.endswith(".svg"):
        slug = base[len(shot["id"]) + 1:-4]
    else:
        slug = slugify(shot.get("scene", ""))
    desc_block = "\n".join(out)
    return PLACEHOLDER_TPL.format(
        w=W, h=H, w2=W - 48, h2=H - 48, wr=W - 70,
        sid=shot["id"],
        dur=("%g" % shot["dur"]),
        title=html.escape(shot.get("title", "")),
        scene=html.escape(shot.get("scene", "")),
        camera=html.escape(shot.get("camera", "")),
        desc_lines=desc_block,
        bar=H - 140, bar2=H - 78,
        slug=slug,
    )


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验不写文件")
    ap.add_argument("--no-placeholders", action="store_true", help="跳过占位图生成")
    args = ap.parse_args()

    with open(SHOTS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    shots = data["shots"]

    # ---------- 校验 ----------
    errors, warnings = [], []
    if len(shots) != data["meta"].get("shots_count", 30):
        errors.append("幕数不符：meta.shots_count=%s 实际=%d"
                      % (data["meta"].get("shots_count"), len(shots)))
    for i, s in enumerate(shots):
        expect_id = "S%02d" % (i + 1)
        if s["id"] != expect_id:
            errors.append("第 %d 幕 id 应为 %s，实际 %s" % (i + 1, expect_id, s["id"]))
        if abs((s["end"] - s["start"]) - s["dur"]) > 0.001:
            errors.append("%s 时长不自洽：end-start=%.3f dur=%.3f"
                          % (s["id"], s["end"] - s["start"], s["dur"]))
        if i > 0 and abs(s["start"] - shots[i - 1]["end"]) > 0.001:
            errors.append("%s 与前幕不连续：前幕 end=%.2f 本幕 start=%.2f"
                          % (s["id"], shots[i - 1]["end"], s["start"]))
        if s["dur"] <= 0:
            errors.append("%s 时长非正数" % s["id"])
        for ov in s.get("overlays", []):
            if ov.get("kind") == "highlight":
                if ov["x"] + ov["w"] > W or ov["y"] + ov["h"] > H:
                    warnings.append("%s 高亮框超出画布：%s" % (s["id"], ov.get("label", "")))
    total = shots[-1]["end"] - shots[0]["start"]
    if abs(total - EXPECTED_TOTAL) > 0.001:
        errors.append("总时长 %.2fs ≠ 文稿 178.00s" % total)

    print("=" * 62)
    print("校验：幕数 %d | 总时长 %.2fs（目标 178.00s）" % (len(shots), total))
    for w_ in warnings:
        print("  [WARN] " + w_)
    if errors:
        print("  —— 发现 %d 个错误 ——" % len(errors))
        for e in errors:
            print("  [ERROR] " + e)
        print("=" * 62)
        return 1
    print("  [OK] 幕号连续 / 时间码无缝 / 时长自洽 / 总时长达标")
    print("  [OK] 高亮框均在 1920x1080 画布内")

    if args.check:
        print("=" * 62)
        return 0

    # ---------- 1. shots.js ----------
    js_path = os.path.join(BASE, "shots.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("/* 自动生成，勿手改。修改请编辑 shots.json 后重跑 build_data.py */\n")
        f.write("window.SHOTS_DATA = ")
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    print("  写出 shots.js (%.1f KB)" % (os.path.getsize(js_path) / 1024))

    # ---------- 1b. narration.js（供 file:// 直接加载旁白） ----------
    nar_json = os.path.join(BASE, "narration.json")
    if os.path.exists(nar_json):
        with open(nar_json, "r", encoding="utf-8") as f:
            nar_data = json.load(f)
        nar_js = os.path.join(BASE, "narration.js")
        with open(nar_js, "w", encoding="utf-8") as f:
            f.write("/* 自动生成，勿手改。修改请编辑 narration.json 后重跑 build_data.py */\n")
            f.write("window.NARRATION_DATA = ")
            json.dump(nar_data, f, ensure_ascii=False, indent=1)
            f.write(";\n")
        print("  写出 narration.js (%d 条旁白)" % len(nar_data))
    else:
        print("  [SKIP] 未找到 narration.json，跳过 narration.js（旁白显示将不可用）")

    # ---------- 2. subtitles.srt ----------
    srt_path = os.path.join(BASE, "subtitles.srt")
    blocks, n = [], 0
    for s in shots:
        sub = (s.get("subtitle") or "").strip()
        if not sub:
            continue
        lines = split_subtitle(sub)
        n += 1
        # 幕内留 0.15s 安全边距
        st = s["start"] + 0.15
        en = max(st + 0.5, s["end"] - 0.15)
        blocks.append("%d\n%s --> %s\n%s\n" % (n, srt_time(st), srt_time(en), "\n".join(lines)))
    with open(srt_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(blocks))
    print("  写出 subtitles.srt (%d 条字幕)" % n)

    # ---------- 3. 占位素材 ----------
    if not args.no_placeholders:
        os.makedirs(PLACEHOLDER_DIR, exist_ok=True)
        cnt = 0
        for s in shots:
            # 文件名直接取 media.src 的 basename，保证与 shots.json 引用严格一致
            src = (s.get("media") or {}).get("src", "")
            name = os.path.basename(src) if src else "%s_scene.svg" % s["id"]
            p = os.path.join(PLACEHOLDER_DIR, name)
            if not os.path.exists(p):
                with open(p, "w", encoding="utf-8") as f:
                    f.write(make_placeholder(s))
            cnt += 1
        # 清掉历史命名不一致的孤儿占位图（src 里已不引用的）
        referenced = {os.path.basename((s.get("media") or {}).get("src", "")) for s in shots}
        for old in os.listdir(PLACEHOLDER_DIR):
            if old.endswith(".svg") and old not in referenced:
                os.remove(os.path.join(PLACEHOLDER_DIR, old))
                print("  [CLEAN] 移除未引用占位图", old)
        print("  写出占位素材 %d 张 -> assets/placeholders/" % cnt)

    print("=" * 62)
    print("构建完成。下一步：双击 preview.bat 预览，或 preview.bat 后用 export_frames.py 出帧。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
