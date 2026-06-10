"""顶层 ASGI 入口(契约约定的 app/main.py)。

实际应用工厂位于 app.api.main,本模块仅做再导出,既满足
"app.main:create_app / app.main:app" 的约定,又复用统一实现,
避免两处分叉。Makefile 约定的 app.api.main:app 同样可用。
"""

from __future__ import annotations

from app.api.main import app, create_app, main

__all__ = ["app", "create_app", "main"]


if __name__ == "__main__":
    main()
