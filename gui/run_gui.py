#!/usr/bin/env python3
"""
FITS文件网页下载器GUI启动脚本
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox

def check_dependencies():
    """检查依赖包是否安装"""
    required_packages = [
        'numpy',
        'matplotlib',
        'astropy',
        'requests',
        'bs4',  # beautifulsoup4
        'scipy'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        error_msg = f"缺少以下依赖包:\n{', '.join(missing_packages)}\n\n"
        error_msg += "请运行以下命令安装:\n"
        error_msg += "pip install -r requirements.txt"
        
        # 创建一个简单的错误对话框
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        messagebox.showerror("依赖包缺失", error_msg)
        root.destroy()
        
        print(error_msg)
        return False
    
    return True

def main():
    """主函数"""
    print("=" * 60)
    print("FITS文件网页下载器GUI")
    print("=" * 60)
    
    # 检查依赖
    print("检查依赖包...")
    if not check_dependencies():
        print("依赖检查失败，程序退出")
        sys.exit(1)
    
    print("依赖检查通过")
    
    # 导入并启动GUI
    try:
        from fits_web_downloader import FitsWebDownloaderGUI
        
        print("启动GUI应用程序...")
        app = FitsWebDownloaderGUI()
        app.run()
        
    except ImportError as e:
        error_msg = f"导入模块失败: {str(e)}"
        print(error_msg)
        
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("导入错误", error_msg)
        root.destroy()
        
        sys.exit(1)
        
    except Exception as e:
        error_msg = f"程序运行出错: {str(e)}"
        print(error_msg)
        
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("运行错误", error_msg)
        root.destroy()
        
        sys.exit(1)

if __name__ == "__main__":
    main()
