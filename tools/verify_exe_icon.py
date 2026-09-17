"""verify_exe_icon.py —— 证明「打包 exe 内嵌的图标 == AI别闹.ico 的封面图标」。

为什么需要这个：**Windows 任务栏按钮取的是「进程 exe 的内嵌图标」，不看窗口图标**
（2026-09-17 实测：把窗口 ICON_BIG 换成封面 ico 后任务栏仍显示宿主 python.exe 的图标）。
所以「任务栏是封面图标」这件事的**唯一可判定依据**就是 exe 的 RT_ICON 资源。

抓屏看任务栏只能算旁证（机器上可能同时跑着别的发行版 exe，按钮归属会含混）；
本脚本直接读 PE 资源，是确定性的。

做法（纯标准库，不依赖 pefile）：
  1. 解析 AI别闹.ico 的 ICONDIR，取出每帧的原始字节；
  2. 解析 exe 的 PE 资源目录，取出所有 RT_ICON 的原始字节；
  3. 两个集合必须**逐字节**相等 —— ICO 落盘格式与 RT_ICON 资源格式同源，
     所以是集合相等而不是「相似」。

用法（项目根目录下）：
    python tools/verify_exe_icon.py [exe路径] [ico路径]
默认：dist/AI别闹.exe + AI别闹.ico
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------
# ICO 解析
# --------------------------------------------------------------------------
def parse_ico(path):
    """返回 [(宽, 高, 位深, 原始字节), ...]。"""
    with open(path, 'rb') as f:
        data = f.read()
    reserved, itype, count = struct.unpack_from('<HHH', data, 0)
    if reserved != 0 or itype != 1:
        raise SystemExit('[ico] 不是合法 ICO：%s' % path)
    out = []
    for i in range(count):
        off = 6 + i * 16
        (w, h, colors, _r, planes, bpp,
         nbytes, imgoff) = struct.unpack_from('<BBBBHHII', data, off)
        out.append((w or 256, h or 256, bpp, data[imgoff:imgoff + nbytes]))
    return out


# --------------------------------------------------------------------------
# PE 资源解析
# --------------------------------------------------------------------------
def _rva_to_off(sections, rva):
    for va, vsize, rawptr, rawsize in sections:
        if va <= rva < va + max(vsize, rawsize):
            return rva - va + rawptr
    raise SystemExit('[pe] RVA 0x%X 不在任何节内' % rva)


def parse_rt_icons(path):
    """返回 exe 内所有 RT_ICON 资源的原始字节列表（按资源 id 排序）。"""
    with open(path, 'rb') as f:
        data = f.read()
    if data[:2] != b'MZ':
        raise SystemExit('[pe] 不是 PE 文件：%s' % path)
    e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b'PE\0\0':
        raise SystemExit('[pe] 缺 PE 签名')
    coff = e_lfanew + 4
    machine, nsec, _ts, _sym, _nsym, optsize, _chars = struct.unpack_from(
        '<HHIIIHH', data, coff)
    opt = coff + 20
    magic = struct.unpack_from('<H', data, opt)[0]
    # DataDirectory 起始偏移：PE32=96 / PE32+=112
    dd = opt + (96 if magic == 0x10B else 112)
    res_rva, res_size = struct.unpack_from('<II', data, dd + 2 * 8)  # 索引 2 = 资源表
    if res_rva == 0:
        raise SystemExit('[pe] 该 exe 没有资源表（未嵌入图标？）')

    sections = []
    sc = opt + optsize
    for i in range(nsec):
        base = sc + i * 40
        vsize, va, rawsize, rawptr = struct.unpack_from('<IIII', data, base + 8)
        sections.append((va, vsize, rawptr, rawsize))

    rs = _rva_to_off(sections, res_rva)

    def dir_entries(dir_off):
        """读一个资源目录层，返回 [(id, child, is_named), ...]。

        child 的最高位 = 1 表示「指向下一层目录」，= 0 表示「指向数据条目」。
        """
        n_named, n_id = struct.unpack_from('<HH', data, rs + dir_off + 12)
        out = []
        for i in range(n_named + n_id):
            e = rs + dir_off + 16 + i * 8
            name_id, child = struct.unpack_from('<II', data, e)
            out.append((name_id, child, i < n_named))
        return out

    def data_entry(off):
        """off = 数据条目相对资源段的偏移；返回 (data_rva, size)。"""
        return struct.unpack_from('<II', data, rs + off)

    def descend(child):
        """child 若指向子目录则返回目录偏移，否则返回 None（即已是数据条目）。"""
        return (child & 0x7FFFFFFF) if (child & 0x80000000) else None

    RT_ICON = 3
    icons = []
    for type_id, type_child, _named in dir_entries(0):
        if type_id != RT_ICON:
            continue
        icon_dir = descend(type_child)
        if icon_dir is None:
            continue
        for icon_id, child, _n in dir_entries(icon_dir):
            lang_dir = descend(child)
            if lang_dir is None:
                leaf_off = child
            else:
                entries = dir_entries(lang_dir)
                if not entries:
                    continue
                leaf_off = entries[0][1]      # 取第一个语言项
                if descend(leaf_off) is not None:
                    # 理论上不会发生（数据条目没有子层）；防御性跳过
                    continue
            data_rva, size = data_entry(leaf_off)
            if data_rva == 0 or size == 0:
                continue
            off = _rva_to_off(sections, data_rva)
            icons.append((icon_id, data[off:off + size]))
    icons.sort(key=lambda t: t[0])
    if not icons:
        raise SystemExit('[pe] 没找到 RT_ICON 资源')
    return icons


# --------------------------------------------------------------------------
def main():
    exe = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'dist', 'AI别闹.exe')
    ico = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'AI别闹.ico')
    for p in (exe, ico):
        if not os.path.exists(p):
            sys.exit('[verify] 找不到文件：%s' % p)

    frames = parse_ico(ico)
    icons = parse_rt_icons(exe)
    print('[ico ] %s -> %d 帧' % (os.path.basename(ico), len(frames)))
    print('[exe ] %s -> %d 个 RT_ICON' % (os.path.basename(exe), len(icons)))

    ico_set = {b for _w, _h, _bpp, b in frames}
    exe_set = {b for _id, b in icons}
    for i, (w, h, bpp, blob) in enumerate(frames):
        print('   ico 帧 %d: %dx%d %dbpp %d 字节' % (i + 1, w, h, bpp, len(blob)))
    for icon_id, blob in icons:
        print('   RT_ICON %d: %d 字节' % (icon_id, len(blob)))

    only_ico = ico_set - exe_set
    only_exe = exe_set - ico_set
    if not only_ico and not only_exe:
        print('\n[OK] exe 内嵌图标与 %s 逐字节一致（%d/%d 帧全部命中）'
              % (os.path.basename(ico), len(ico_set), len(frames)))
        print('     结论：打包态任务栏图标 = 封面图标')
        return 0
    print('\n[FAIL] 不一致：')
    print('   只在 ico 里（exe 缺）：%d 帧，字节数 %s'
          % (len(only_ico), sorted(len(b) for b in only_ico)))
    print('   只在 exe 里（ico 缺）：%d 帧，字节数 %s'
          % (len(only_exe), sorted(len(b) for b in only_exe)))
    return 1


if __name__ == '__main__':
    sys.exit(main())
