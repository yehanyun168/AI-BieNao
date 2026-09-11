# legacy/ —— 早期离线预览工具（已废弃，保留仅供追溯）

这两个脚本是**设计早期**用 matplotlib 手绘的「离线 mockup」，不是程序真实截图：

| 文件 | 说明 |
|---|---|
| `render_map_preview.py` | 用多边形的国别主色填充重绘世界地图（bbox 会盖住国旗，图中的国旗是辅助画上去的） |
| `render_pixel_ui_preview.py` | 离线手绘整屏 UI 稿，数值/文案全部写死 |

## 为什么废弃

现在的**单一数据源**是：

1. `tools/gen_pixel_map.py` —— 从 Natural Earth 110m 真实海岸线栅格化出 120×60 像素地图 + 20 面像素国旗，产出 `design/pixel_map_assets.json` + `demo/pixel_assets.py`；
2. `tools/build_design_doc.py` —— 由上面那份资源生成 `design/ui_design_v0.3.html` 设计稿；
3. `demo/make_screenshots.py` —— 跑真机 Kivy 渲染并截图（`screenshot_*.png`）。

上面这三条链路才是权威。legacy 里的手绘稿与它们**必然不一致**，看图请认准 `design/ui_design_v0.3.html` 和 `screenshot_*.png`。

## 运行（需要额外装 matplotlib，Kivy 环境默认没有）

```bash
py -3.12 -m pip install matplotlib
cd demo/legacy
py -3.12 render_map_preview.py
py -3.12 render_pixel_ui_preview.py
```
