# 便携版打包指南（方案 C：不需要 PyInstaller）

> 适用场景：PyInstaller 打包失败 / 杀软误报 / 想最快交付

## 核心思路

把 Python 解释器 + Kivy + demo 代码**全部塞进一个文件夹**，用户解压后**不需要装任何东西**就能玩。

## 步骤

### 1. 准备 Python 嵌入版

下载 [Python 3.12 嵌入版](https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip)（约 10 MB）解压到 `portable/python/`。

### 2. 安装 pip

嵌入版没有 pip，从 [get-pip.py](https://bootstrap.pypa.io/get-pip.py) 下载到 `portable/`：

```bash
cd portable
python get-pip.py
```

### 3. 安装 Kivy 到嵌入版

```bash
cd portable
python -m pip install kivy[base]
```

### 4. 复制 demo 代码

```bash
cp -r ../demo/* portable/
```

### 5. 创建启动脚本

`portable/AI别闹.bat`：
```batch
@echo off
cd /d "%~dp0"
python main.py
```

### 6. 测试

```bash
双击 portable/AI别闹.bat
```

### 7. 打包分发

把整个 `portable/` 文件夹打成 zip（约 80-120 MB）。

用户使用：
1. 解压 zip 到任意位置
2. 双击 `AI别闹.bat`
3. 看到游戏窗口

## 自动打包脚本（Python）

```python
# tools/build_portable.py
import shutil
import zipfile
import urllib.request
from pathlib import Path

PORTABLE_DIR = Path('portable')
PY_VERSION = '3.12.7'
PY_URL = f'https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip'

# 1. 下载嵌入版
PORTABLE_DIR.mkdir(exist_ok=True)
print(f'Downloading Python {PY_VERSION} embed...')
urllib.request.urlretrieve(PY_URL, 'python_embed.zip')
shutil.unpack_archive('python_embed.zip', PORTABLE_DIR)
python_embed.zip.unlink()

# 2. 装 pip
urllib.request.urlretrieve(
    'https://bootstrap.pypa.io/get-pip.py',
    PORTABLE_DIR / 'get-pip.py'
)
subprocess.run([str(PORTABLE_DIR / 'python.exe'), 'get-pip.py'])

# 3. 装 Kivy
subprocess.run([str(PORTABLE_DIR / 'python.exe'), '-m', 'pip', 'install', 'kivy[base]'])

# 4. 复制 demo
for f in Path('demo').glob('*.py'):
    shutil.copy(f, PORTABLE_DIR / f.name)

# 5. 创建启动 bat
with open(PORTABLE_DIR / 'AI别闹.bat', 'w') as f:
    f.write('@echo off\ncd /d %~dp0\npython.exe main.py\n')

# 6. 打包 zip
shutil.make_archive('AI别闹_portable', 'zip', PORTABLE_DIR)
print('Done: AI别闹_portable.zip (~100MB)')
```

## 体积对比

| 组件 | 大小 |
|------|------|
| Python 嵌入版 | ~10 MB |
| pip + setuptools | ~5 MB |
| Kivy + 依赖 | ~70 MB |
| demo 代码 | ~50 KB |
| **总计** | **~85 MB** |

## 优缺点

✅ **优点**：
- 不依赖 PyInstaller（更稳定）
- 体积比单 exe 小（85 vs 100+ MB）
- 杀软友好（都是官方 Python 文件）

❌ **缺点**：
- 仍是文件夹（不是单文件）
- 用户需要解压
- 首次启动需要解压（10 秒）

## 与 PyInstaller 对比

| | PyInstaller | 便携版 |
|---|-------------|--------|
| 用户体验 | 单 exe 双击 | 解压 → 双击 bat |
| 启动速度 | 慢（解压） | 快 |
| 体积 | 100-150 MB | 85 MB |
| 杀软 | 可能误报 | ✅ 友好 |
| 打包难度 | 中（spec 配置） | 低（脚本复制）|
| 兼容性 | ✅ 经过测试 | ✅ 纯官方 |