#!/usr/bin/env python3
"""
FITS监控系统验证脚本
验证所有核心功能是否正常工作
"""

import os
import sys
import subprocess
import time

def run_command(cmd, timeout=10):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "命令超时"
    except Exception as e:
        return False, "", str(e)

def test_imports():
    """测试核心模块导入"""
    print("🔍 测试模块导入...")
    
    modules = [
        "fits_monitor",
        "plot_viewer", 
        "config_loader",
        "watchdog"
    ]
    
    for module in modules:
        success, stdout, stderr = run_command(f'python -c "import {module}; print(\'OK\')"')
        if success:
            print(f"  ✅ {module} - 导入成功")
        else:
            print(f"  ❌ {module} - 导入失败: {stderr}")
            return False
    
    return True

def test_help_commands():
    """测试帮助命令"""
    print("\n📋 测试帮助命令...")
    
    commands = [
        "python run_monitor.py --help",
        "python plot_viewer.py --help",
        "python test_runner.py --help"
    ]
    
    for cmd in commands:
        success, stdout, stderr = run_command(cmd)
        if success:
            print(f"  ✅ {cmd.split()[1]} - 帮助信息正常")
        else:
            print(f"  ❌ {cmd.split()[1]} - 帮助信息失败: {stderr}")
            return False
    
    return True

def test_config_loading():
    """测试配置加载"""
    print("\n⚙️ 测试配置加载...")
    
    success, stdout, stderr = run_command(
        'python -c "from config_loader import get_config; c=get_config(); print(\'Config loaded\')"'
    )
    
    if success:
        print("  ✅ 配置文件加载成功")
        return True
    else:
        print(f"  ❌ 配置文件加载失败: {stderr}")
        return False

def test_fits_monitor_creation():
    """测试FITS监控器创建"""
    print("\n🔧 测试FITS监控器创建...")
    
    test_code = '''
from fits_monitor import FITSFileMonitor
import tempfile
import os

with tempfile.TemporaryDirectory() as temp_dir:
    monitor = FITSFileMonitor(temp_dir, enable_recording=False)
    print("Monitor created successfully")
'''
    
    success, stdout, stderr = run_command(f'python -c "{test_code}"')
    
    if success:
        print("  ✅ FITS监控器创建成功")
        return True
    else:
        print(f"  ❌ FITS监控器创建失败: {stderr}")
        return False

def test_watchdog_functionality():
    """测试watchdog功能"""
    print("\n👁️ 测试watchdog基本功能...")

    test_code = '''
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 测试基本类创建
handler = FileSystemEventHandler()
observer = Observer()
print("Watchdog components created successfully")
'''

    success, stdout, stderr = run_command(f'python -c "{test_code}"')

    if success and "successfully" in stdout:
        print("  ✅ Watchdog基本功能正常")
        return True
    else:
        print(f"  ❌ Watchdog基本功能失败: {stderr}")
        return False

def check_required_files():
    """检查必需文件是否存在"""
    print("\n📁 检查必需文件...")
    
    required_files = [
        "fits_monitor.py",
        "plot_viewer.py", 
        "run_monitor.py",
        "test_runner.py",
        "config_loader.py",
        "config.json",
        "requirements.txt",
        "README.md"
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} - 文件不存在")
            all_exist = False
    
    return all_exist

def main():
    """主验证函数"""
    print("=" * 60)
    print("🚀 FITS监控系统验证")
    print("=" * 60)
    
    tests = [
        ("文件检查", check_required_files),
        ("模块导入", test_imports),
        ("帮助命令", test_help_commands),
        ("配置加载", test_config_loading),
        ("监控器创建", test_fits_monitor_creation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"\n❌ {test_name} 测试失败")
        except Exception as e:
            print(f"\n❌ {test_name} 测试异常: {str(e)}")
    
    print("\n" + "=" * 60)
    print(f"📊 验证结果: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！系统运行正常。")
        print("\n🚀 可以开始使用:")
        print("   python run_monitor.py")
        print("   python plot_viewer.py")
        print("   python test_runner.py")
        return True
    else:
        print("⚠️ 部分测试失败，请检查系统配置。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
