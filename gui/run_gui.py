#!/usr/bin/env python3
"""
FITS文件网页下载器GUI启动脚本
"""

import os
import sys
import argparse
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
        'scipy',
        'cv2'   # opencv-python
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

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='FITS文件网页下载器GUI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  # 无参数启动（正常GUI模式）
  python run_gui.py

  # 只有日期 - 执行"全天全系统diff"操作
  python run_gui.py --date 20241031

  # 有日期和望远镜系统名 - 执行"全天下载diff"操作
  python run_gui.py --date 20241031 --telescope GY1

  # 有日期、望远镜系统名和天区名 - 执行"扫描fits文件" + "全选" + "批量下载并diff"
  python run_gui.py --date 20241031 --telescope GY1 --region K019
        '''
    )

    parser.add_argument(
        '--date',
        type=str,
        help='日期，格式为YYYYMMDD（如：20241031）。如果为空，则以无参数启动，其他参数也无效'
    )

    parser.add_argument(
        '--telescope',
        type=str,
        help='望远镜系统名（如：GY1）。可选参数'
    )

    parser.add_argument(
        '--region',
        type=str,
        help='天区名（如：K019）。可选参数'
    )

    return parser.parse_args()

def main():
    """主函数"""
    print("=" * 60)
    print("FITS文件网页下载器GUI")
    print("=" * 60)

    # 解析命令行参数
    args = parse_arguments()

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

        # 根据参数决定启动模式
        if args.date:
            print(f"启动参数: 日期={args.date}, 望远镜={args.telescope}, 天区={args.region}")
            app = FitsWebDownloaderGUI(
                auto_date=args.date,
                auto_telescope=args.telescope,
                auto_region=args.region
            )
        else:
            print("正常GUI模式启动")
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
