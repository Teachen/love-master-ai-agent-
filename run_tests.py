"""恋爱大师 - 一键测试入口

不装 pytest 也能跑（内置轻量runner）；装了 pytest 则优先用它，输出更详细。

用法：
    python run_tests.py              # 跑全部测试
    python run_tests.py -v           # 详细输出
    python run_tests.py memory       # 只跑名字含 memory 的测试
    python run_tests.py report       # 只跑报告相关测试
    python run_tests.py -s           # 用 pytest 并显示 print 输出（-s）
"""
import argparse
import importlib.util
import inspect
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

SEP = "=" * 62


def _has_pytest() -> bool:
    return importlib.util.find_spec("pytest") is not None


def run_with_pytest(keyword: str | None, verbose: bool, show_print: bool) -> int:
    import pytest

    args = [str(ROOT / "tests")]
    if keyword:
        args += ["-k", keyword]
    if verbose:
        args.append("-v")
    args.append("-s" if show_print else "-q")
    print(f"$ pytest {' '.join(args)}\n")
    return int(pytest.main(args))


def run_builtin(keyword: str | None, verbose: bool) -> int:
    """无 pytest 时的兜底 runner：直接导入 tests 目录下的 test_* 函数。"""
    test_dir = ROOT / "tests"
    passed, failed = 0, 0
    failures: list[tuple[str, str]] = []

    for path in sorted(test_dir.glob("test_*.py")):
        name = path.stem
        if keyword and keyword not in name:
            continue
        print(f"\n{SEP}\n  {name}\n{SEP}")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            failures.append((f"{name} (import)", traceback.format_exc()))
            print(f"  ✗ 导入失败：{exc}")
            continue

        for func_name, func in sorted(inspect.getmembers(module, inspect.isfunction)):
            if not func_name.startswith("test_"):
                continue
            if keyword and keyword not in func_name:
                continue
            try:
                sig = inspect.signature(func)
                kwargs = {}
                # 极简 fixture 支持：常见 pytest fixture 不传则跳过
                if any(p.default is inspect.Parameter.empty for p in sig.parameters.values()):
                    print(f"  ⏭ {func_name} —— 需要 fixture，跳过（建议安装 pytest）")
                    continue
                func(**kwargs)
                passed += 1
                print(f"  ✓ {func_name}")
            except Exception:  # noqa: BLE001
                failed += 1
                failures.append((f"{name}::{func_name}", traceback.format_exc()))
                print(f"  ✗ {func_name}")

    print(f"\n{SEP}")
    for title, tb in failures:
        print(f"\n【失败】{title}\n{tb}")
    print(f"{SEP}\n  结果：{passed} passed, {failed} failed\n{SEP}")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="恋爱大师 - 一键测试入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python run_tests.py                 # 跑全部\n"
            "  python run_tests.py -v              # 详细输出\n"
            "  python run_tests.py memory          # 只跑多轮记忆测试\n"
            "  python run_tests.py report -s       # 报告测试并显示 print\n"
        ),
    )
    parser.add_argument("keyword", nargs="?", default=None, help="按关键字过滤测试文件/用例名")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("-s", "--show-print", action="store_true", help="显示测试中的 print 输出")
    parser.add_argument("--no-pytest", action="store_true", help="强制使用内置 runner")
    args = parser.parse_args()

    if args.verbose:
        print(f"Python  : {sys.executable}")
        print(f"项目根  : {ROOT}\n")

    if not args.no_pytest and _has_pytest():
        return run_with_pytest(args.keyword, args.verbose, args.show_print)

    if not args.no_pytest:
        print("⚠ 未检测到 pytest，改用内置 runner（不支持 fixture，部分用例会跳过）")
        print("  安装：pip install pytest pytest-asyncio\n")
    return run_builtin(args.keyword, args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
