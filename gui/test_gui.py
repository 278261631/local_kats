#!/usr/bin/env python3
"""
GUI测试脚本
用于验证GUI组件是否能正常工作
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox

def test_imports():
    """测试所有必要的导入"""
    print("测试导入...")
    
    try:
        import numpy
        print("✓ numpy")
        
        import matplotlib
        print("✓ matplotlib")
        
        import astropy
        print("✓ astropy")
        
        import requests
        print("✓ requests")
        
        import bs4
        print("✓ beautifulsoup4")
        
        import scipy
        print("✓ scipy")
        
        # 测试本地模块
        from web_scanner import WebFitsScanner, DirectoryScanner
        print("✓ web_scanner")
        
        from fits_viewer import FitsImageViewer
        print("✓ fits_viewer")
        
        # 测试数据收集模块
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from data_collect.data_02_download import FitsDownloader
        print("✓ data_collect.data_02_download")
        
        print("所有导入测试通过！")
        return True
        
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return False

def test_web_scanner():
    """测试网页扫描器"""
    print("\n测试网页扫描器...")

    try:
        from web_scanner import WebFitsScanner, DirectoryScanner

        scanner = WebFitsScanner()
        print("✓ WebFitsScanner 创建成功")

        directory_scanner = DirectoryScanner()
        print("✓ DirectoryScanner 创建成功")

        # 测试格式化文件大小
        size_str = scanner.format_file_size(1024*1024)
        print(f"✓ 文件大小格式化测试: {size_str}")

        return True

    except Exception as e:
        print(f"✗ 网页扫描器测试失败: {e}")
        return False

def test_fits_viewer():
    """测试FITS查看器"""
    print("\n测试FITS查看器...")

    try:
        from fits_viewer import FitsImageViewer

        # 创建临时窗口
        root = tk.Tk()
        root.withdraw()  # 隐藏窗口

        frame = tk.Frame(root)
        viewer = FitsImageViewer(frame)
        print("✓ FitsImageViewer 创建成功")

        root.destroy()
        return True

    except Exception as e:
        print(f"✗ FITS查看器测试失败: {e}")
        return False

def test_gui_creation():
    """测试GUI创建"""
    print("\n测试GUI创建...")
    
    try:
        from fits_web_downloader import FitsWebDownloaderGUI
        
        # 创建GUI但不显示
        root = tk.Tk()
        root.withdraw()
        
        # 模拟GUI创建过程
        app = FitsWebDownloaderGUI()
        print("✓ FitsWebDownloaderGUI 创建成功")
        
        # 立即销毁以避免显示
        app.root.destroy()
        
        return True
        
    except Exception as e:
        print(f"✗ GUI创建测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("FITS文件网页下载器GUI - 组件测试")
    print("=" * 60)
    
    tests = [
        ("导入测试", test_imports),
        ("网页扫描器测试", test_web_scanner),
        ("FITS查看器测试", test_fits_viewer),
        ("GUI创建测试", test_gui_creation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"测试失败: {test_name}")
        except Exception as e:
            print(f"测试异常: {test_name} - {e}")
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("✓ 所有测试通过！GUI应该可以正常运行。")
        print("\n启动GUI:")
        print("python fits_web_downloader.py")
        print("或")
        print("python run_gui.py")
    else:
        print("✗ 部分测试失败，请检查错误信息。")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
