from tests import support

import os
import unittest

from PySide6.QtGui import QIcon, QImage

from core.constants import ICON_PATH, PROJECT_ROOT, default_data_dir


class TestPackaging(unittest.TestCase):
    def test_saves_go_to_appdata_only_in_the_packaged_game(self):
        self.assertEqual(default_data_dir(False), os.path.join(PROJECT_ROOT, "data"))
        packaged = default_data_dir(True)
        self.assertEqual(os.path.basename(packaged), "Graphiti")
        self.assertNotIn(PROJECT_ROOT, packaged)

    def test_icon_files_exist_in_every_size(self):
        support.qapp()
        self.assertEqual(QImage(ICON_PATH).size().width(), 256)
        icon = QIcon(os.path.join(os.path.dirname(ICON_PATH), "graphiti.ico"))
        sizes = {size.width() for size in icon.availableSizes()}
        self.assertTrue({16, 32, 48, 256} <= sizes)

    def test_build_script_bundles_assets_and_icon(self):
        with open(os.path.join(PROJECT_ROOT, "build_exe.py"), encoding="utf-8") as f:
            script = f.read()
        for flag in ("--onefile", "--windowed", "--icon", "--add-data"):
            self.assertIn(flag, script)


if __name__ == "__main__":
    unittest.main()
