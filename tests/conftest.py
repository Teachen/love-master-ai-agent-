"""pytest 全局配置：把会话记忆与 PDF 输出重定向到临时目录。

背景：FileChatMemory 默认写入 ./tmp/memory/，FileChatMemory 的池还带进程内缓存。
如果不重定向，测试会把 cli_test_* / memory_test_* 等会话文件写进用户的真实目录，
造成数据污染。这里在会话开始时统一改指临时目录，并清空记忆池。
"""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True, scope="session")
def _isolate_memory_dir():
    """整个测试会话期间，把记忆目录指向临时目录"""
    tmp_root = Path(tempfile.mkdtemp(prefix="love_master_test_"))
    import os

    old = os.environ.get("MEMORY_DIR")
    os.environ["MEMORY_DIR"] = str(tmp_root / "memory")

    from app.agent import reset_memory_pool

    reset_memory_pool()

    yield tmp_root

    reset_memory_pool()
    if old is None:
        os.environ.pop("MEMORY_DIR", None)
    else:
        os.environ["MEMORY_DIR"] = old
