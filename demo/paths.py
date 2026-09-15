"""运行时数据路径：统一处理源码运行与 PyInstaller 单文件打包。"""
import os
import shutil
import sys


def _user_data_dir():
    """持久化数据根目录。

    - 源码运行：本模块所在目录（demo/），与现有开发 / git 约定一致。
    - PyInstaller 单文件 exe（sys.frozen=True）：写到 ``%APPDATA%/AI-BieNao``。
      避免在 exe 同级目录（可能是桌面 / 下载 / 只读目录）生成
      ``settings.json``、``saves/``、``crash.log``。
    - 取不到 APPDATA 时回退到 exe 同级目录（可写性由调用方兜底）。
    """
    if getattr(sys, 'frozen', False):
        app = os.environ.get('APPDATA')
        if app:
            return os.path.join(app, 'AI-BieNao')
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _app_dir():
    """应用本体所在目录（仅冻结态有意义）。"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def migrate_legacy_data():
    """把 v0.4.0 及更早的 exe 同级数据迁移到 APPDATA。

    旧版本在单文件模式下把 settings.json / saves / crash.log 写到 exe 旁边。
    新版本统一写到 ``%APPDATA%/AI-BieNao``。启动时若 APPDATA 目标不存在、
    而 exe 旁存在旧数据，则复制过去，避免玩家升级后丢档 / 丢设置。

    复制而非移动：即使迁移中途失败，原位置数据仍在；迁移成功后旧文件
    可由外层按需清理（例如安装程序 / 启动器）。
    """
    if not getattr(sys, 'frozen', False):
        return
    src_dir = _app_dir()
    dst_dir = _user_data_dir()
    if src_dir == dst_dir:
        return

    def _copy_file(name: str) -> None:
        src = os.path.join(src_dir, name)
        dst = os.path.join(dst_dir, name)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copy2(src, dst)
            except Exception:
                pass

    def _copy_dir(name: str) -> None:
        src = os.path.join(src_dir, name)
        dst = os.path.join(dst_dir, name)
        if os.path.isdir(src) and not os.path.exists(dst):
            try:
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copytree(src, dst)
            except Exception:
                pass

    _copy_file('settings.json')
    _copy_dir('saves')
    _copy_file('crash.log')
