#!/usr/bin/env python3
"""
FITS监控系统启动脚本 - 解决编码问题
"""

import os
import sys
import locale

# 设置环境变量解决编码问题
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 设置控制台编码
if sys.platform.startswith('win'):
    try:
        # Windows下设置控制台编码为UTF-8
        os.system('chcp 65001 >nul')
        locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
    except:
        pass

# 导入主程序
from run_monitor import main

if __name__ == "__main__":
    try:
        main()
    except UnicodeEncodeError as e:
        print("编码错误，请使用UTF-8编码的终端运行程序")
        print(f"错误详情: {e}")
    except Exception as e:
        print(f"程序运行出错: {e}")
