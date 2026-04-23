import os
import sys
from pathlib import Path

# 确保测试时从项目根目录解析 config/
ROOT = Path(__file__).parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("NEUROPILOT_ENV", "test")
