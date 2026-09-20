"""主菜单使用等宽分栏，右侧地图保持比例并垂直居中。"""

import unittest

import main


class MainMenuSplitLayoutTests(unittest.TestCase):
    def setUp(self):
        self.menu = main.MainMenu()
        self.root = self.menu.children[0]
        self.left, self.right = list(reversed(self.root.children))

    def test_left_and_right_columns_each_take_half(self):
        self.assertEqual(self.left.size_hint_x, 0.5)
        self.assertEqual(self.right.size_hint_x, 0.5)

    def test_right_column_contains_only_the_world_map(self):
        self.assertEqual(self.right.children, [self.menu.sil_map])

    def test_world_map_is_two_to_one_and_vertically_centered(self):
        self.right.pos = (640, 0)
        self.right.size = (640, 720)

        self.assertAlmostEqual(self.menu.sil_map.width, 640)
        self.assertAlmostEqual(self.menu.sil_map.height, 320)
        self.assertAlmostEqual(self.menu.sil_map.x, self.right.x)
        self.assertAlmostEqual(self.menu.sil_map.center_y, self.right.center_y)


if __name__ == '__main__':
    unittest.main()
