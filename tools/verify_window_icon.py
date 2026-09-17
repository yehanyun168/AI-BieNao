"""verify_window_icon.py —— 真机验证「窗口标题栏 + 任务栏」图标是否为封面图标。

两种模式：
  源码跑：KIVY_NO_FILELOG=1 python tools/verify_window_icon.py
  验 exe：KIVY_NO_FILELOG=1 python tools/verify_window_icon.py --exe dist/AI别闹.exe

做法：启动游戏 → 定位顶层窗口（含边框的 GetWindowRect）→ 置顶 → gdigrab 抓整屏
一帧 → 裁出标题栏 / 图标特写 / 任务栏 → 退出游戏。

⚠️ onefile 的 exe 不能用「父进程 PID」找窗口：bootloader 的父进程只负责解压到临时
   目录，真正的游戏窗口属于它派生的**子进程**。故 exe 模式按「进程映像路径 == 目标
   exe」匹配（不依赖 psutil）。

用法（在项目根目录下）：
    KIVY_NO_FILELOG=1 python tools/verify_window_icon.py [--exe <exe路径>] [输出目录]

产出：
    win_titlebar.png    标题栏整条（看图标 + 标题文字）
    win_icon_zoom.png   图标区域放大 6x（便于肉眼比对是否为封面图标）
    win_taskbar.png     任务栏整条（+ _1/_2/_3 三块 3x 放大，图标在中块）
"""
import ctypes
import os
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, 'demo')
PY312 = r'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe'
FF = (r'C:\Users\tianm\AppData\Local\Microsoft\WinGet\Packages'
      r'\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe'
      r'\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe')

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass


def _image_path(pid):
    """进程映像全路径（拿不到返回 ''）。用于识别 onefile 派生的子进程。"""
    u32 = ctypes.windll.user32
    k32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ''
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return ''
    finally:
        k32.CloseHandle(h)


def find_window(pid, exe_path=None):
    """定位游戏窗口，返回 (hwnd, x, y, w, h) 或 None。

    exe_path 非空时按「进程映像路径相同」匹配（覆盖 onefile 的子进程）；
    否则按 pid 匹配（源码运行）。
    """
    u32 = ctypes.windll.user32
    hits = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _l):
        wpid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if not u32.IsWindowVisible(hwnd):
            return True
        own_pid = wpid.value
        matched = False
        if exe_path:
            matched = os.path.normcase(_image_path(own_pid)) == os.path.normcase(exe_path)
        else:
            matched = own_pid == pid
        if not matched:
            return True
        r = wintypes.RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        n = u32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(hwnd, buf, n + 1)
        # 无论大小都记下来，便于判断是否存在「控制台窗口」干扰任务栏
        print('[verify]   窗口 hwnd=%s pid=%d rect=(%d,%d,%d,%d) title=%r'
              % (hwnd, own_pid, r.left, r.top, w, h, buf.value))
        if w > 400 and h > 300:
            hits.append((w * h, hwnd, r.left, r.top, w, h))
        return True

    u32.EnumWindows(_cb, 0)
    if not hits:
        return None
    hits.sort(reverse=True)
    _area, hwnd, x, y, w, h = hits[0]
    return hwnd, x, y, w, h


def _kill_tree(pid):
    """整棵进程树杀掉。

    ⚠️ 不能只用 proc.terminate()：onefile 的父 bootloader 被杀后，它派生的
       子进程（真正的游戏）会变成孤儿继续跑，留着窗口和一份解压好的临时目录。
       实测踩过 —— 收尾后 tasklist 里 AI别闹.exe 仍在。
    """
    try:
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(pid)],
                       capture_output=True, timeout=15)
    except Exception:
        pass


def _parse_argv():
    """返回 (exe_path_or_None, out_dir)。"""
    args = sys.argv[1:]
    exe_path = None
    out_dir = None
    i = 0
    while i < len(args):
        if args[i] == '--exe':
            if i + 1 >= len(args):
                sys.exit('[verify] --exe 后面要给 exe 路径')
            exe_path = os.path.abspath(args[i + 1])
            i += 2
            continue
        out_dir = args[i]
        i += 1
    return exe_path, (out_dir or tempfile.gettempdir())


def main():
    exe_path, out_dir = _parse_argv()
    os.makedirs(out_dir, exist_ok=True)

    env = dict(os.environ, KIVY_NO_FILELOG='1', KIVY_NO_ARGS='1')
    if exe_path:
        if not os.path.exists(exe_path):
            sys.exit('[verify] 找不到 exe：%s' % exe_path)
        print('[verify] 目标 = 打包态 exe：%s' % exe_path)
        proc = subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path), env=env)
    else:
        print('[verify] 目标 = 源码态：%s' % os.path.join(DEMO, 'main.py'))
        proc = subprocess.Popen([PY312, 'main.py'], cwd=DEMO, env=env)
    print('[verify] 已启动 pid=%d，等待窗口…' % proc.pid)

    rect = None
    # 打包态启动要解压到临时目录，给足时间（onefile 常见 5-10 秒）
    for _ in range(160):
        time.sleep(0.5)
        rect = find_window(proc.pid, exe_path)
        if rect:
            break
    if not rect:
        _kill_tree(proc.pid)
        sys.exit('[verify] 未找到游戏窗口（超时 80 秒）')
    hwnd, x, y, w, h = rect
    print('[verify] 窗口 = x=%d y=%d w=%d h=%d' % (x, y, w, h))

    u32 = ctypes.windll.user32
    try:
        u32.SetForegroundWindow(hwnd)
        u32.BringWindowToTop(hwnd)
    except Exception:
        pass
    time.sleep(2.5)          # 等前几帧画完 + 标题栏/任务栏重绘

    full = os.path.join(out_dir, '_verify_desktop.png')
    subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-f', 'gdigrab',
                    '-framerate', '1', '-i', 'desktop', '-frames:v', '1',
                    '-y', full], check=True)
    _kill_tree(proc.pid)

    from PIL import Image
    img = Image.open(full)
    print('[verify] 桌面帧尺寸 =', img.size)
    # 标题栏（含边框）：窗口顶部往下 46px（DPI 1.5 下约 45px，取够）
    bar_h = min(46, h)
    bar = img.crop((x, y, x + min(w, 900), y + bar_h))
    p_bar = os.path.join(out_dir, 'win_titlebar.png')
    bar.save(p_bar)
    # 图标特写：标题栏最左 40x40 放大 6 倍
    icon_box = img.crop((x, y, x + 40, y + min(40, h)))
    p_zoom = os.path.join(out_dir, 'win_icon_zoom.png')
    icon_box.resize((icon_box.width * 6, icon_box.height * 6),
                    Image.NEAREST).save(p_zoom)
    print('[verify] 标题栏 -> %s' % p_bar)
    print('[verify] 图标特写 -> %s' % p_zoom)

    # 任务栏：先用 Shell_TrayWnd 拿真实位置，拿不到就按屏幕底部 80px 兜底
    tr = wintypes.RECT()
    got = u32.GetWindowRect(u32.FindWindowW('Shell_TrayWnd', None), ctypes.byref(tr))
    if got:
        tx, ty = tr.left, tr.top
        tw, th = tr.right - tr.left, tr.bottom - tr.top
    else:
        tw, th = img.width, 80
        tx, ty = 0, img.height - th
    task = img.crop((tx, ty, tx + tw, ty + th))
    p_task = os.path.join(out_dir, 'win_taskbar.png')
    task.save(p_task)
    # 任务栏按屏宽 1/3 分三块放大 3x —— 便于肉眼认图标
    seg = task.width // 3
    for i in range(3):
        piece = task.crop((i * seg, 0, (i + 1) * seg, task.height))
        piece.resize((piece.width * 3, piece.height * 3), Image.NEAREST).save(
            os.path.join(out_dir, 'win_taskbar_%d.png' % (i + 1)))
    print('[verify] 任务栏 -> %s（含 _1/_2/_3 三块 3x 放大）' % p_task)
    try:
        os.remove(full)
    except Exception:
        pass


if __name__ == '__main__':
    main()
