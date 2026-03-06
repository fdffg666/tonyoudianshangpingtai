#!/usr/bin/env python
"""
综合测试脚本：运行项目所有主要测试，并汇总结果。
用法：
    python run_all_tests.py                # 运行常规测试（不含并发）
    python run_all_tests.py --include-concurrent   # 包含并发压测（并发数默认10）
    python run_all_tests.py --help          # 显示帮助
"""

import subprocess
import sys
import os
import argparse
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 定义测试文件及其运行方式
# 每个条目：(文件路径, 是否使用pytest, 额外命令行参数列表)
TEST_FILES = [
    ("tests/test_auth.py", True, []),           # pytest 测试
    #("tests/test_cart.py", False, []),
    #("tests/test_customer_payment.py", False, []),
    #("tests/test_inventory.py", False, []),
    #("tests/test_order.py", False, []),
    #("tests/test_order_advanced.py", False, []),
    #("tests/test_payment.py", False, []),
    #("tests/test_permissions.py", False, []),
    # ("test_product.py", False, []),            # 内容和权限重复，已跳过
]

# 并发测试文件（默认不运行，需显式指定）
CONCURRENT_TEST = ("test_concurrent_advanced.py", False, [
    "--concurrent", "10",        # 并发线程数（可调）
    "--total", "100",            # 总库存
    "--skus", "5",               # SKU数量
    "--lock-num", "1"
])

def run_test(file_path, use_pytest=False, extra_args=None):
    """运行单个测试文件，返回是否成功"""
    print(f"\n{'='*60}")
    print(f"▶ 正在运行: {file_path}")
    print('='*60)
    sys.stdout.flush()

    if use_pytest:
        cmd = [sys.executable, "-m", "pytest", file_path, "-v"]
    else:
        cmd = [sys.executable, file_path]
    if extra_args:
        cmd.extend(extra_args)

    # 设置环境变量（可选，确保项目根目录在 PYTHONPATH 中）
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(os.path.abspath(__file__))


    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=300  # 单个测试最长运行5分钟
        )
    except subprocess.TimeoutExpired:
        print(f"❌ {file_path} 运行超时")
        return False

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    if result.returncode != 0:
        print(f"❌ {file_path} 失败 (退出码 {result.returncode})")
        return False
    else:
        print(f"✅ {file_path} 通过")
        return True

def parse_args():
    parser = argparse.ArgumentParser(description="运行项目所有测试")
    parser.add_argument("--include-concurrent", action="store_true",
                        help="包含并发压测（默认不运行）")
    return parser.parse_args()

def main():
    args = parse_args()
    tests = TEST_FILES.copy()
    if args.include_concurrent:
        tests.append(CONCURRENT_TEST)
        print("⚠️  并发测试已启用，请确保 Redis 和 MySQL 可承受负载")

    passed = 0
    failed = 0
    for file_path, use_pytest, extra_args in tests:
        ok = run_test(file_path, use_pytest, extra_args)
        if ok:
            passed += 1
        else:
            failed += 1

    print("\n" + "="*60)
    print(f"📊 测试汇总：通过 {passed} 项，失败 {failed} 项")
    print("="*60)
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())