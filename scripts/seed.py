"""种子脚本命令行入口(Makefile `make seed` 调用)。

将项目根加入 sys.path 后转调 app.db.seed.main(),避免重复实现种子逻辑。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 确保以 `python scripts/seed.py` 直接运行时也能导入 app 包
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.db.seed import main  # noqa: E402

if __name__ == "__main__":
    asyncio.run(main())
