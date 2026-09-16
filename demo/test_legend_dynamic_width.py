"""地图图例应按文本真实宽度伸展，并保持单行。"""

import unittest

import main  # 注册字体并完成 Kivy 配置
from kivy.clock import Clock
from ui_hud import LegendBar


class LegendDynamicWidthTests(unittest.TestCase):
    def test_legend_expands_for_long_single_line_labels(self):
        legend = LegendBar()
        legend.set_texts({
            'on': 'Unlocked countries 20',
            'sel': 'Currently selected 1',
            'blk': 'Blocking in progress 8',
            'lk': 'Countries still locked 9',
        })
        Clock.tick()

        expected = (sum(chip.width for chip in legend.items.values())
                    + legend.box.spacing * 3)
        self.assertAlmostEqual(legend._content_w,
                               expected + legend.PAD * 2)
        self.assertGreater(legend._content_w, 442)
        for chip in legend.items.values():
            self.assertNotIn('\n', chip.label.text)
            self.assertLessEqual(chip.label.texture_size[0],
                                 chip.label.width + 1)


if __name__ == '__main__':
    unittest.main()
