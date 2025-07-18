#!/usr/bin/env python3
"""
测试日历与URL构建器的集成
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from url_builder import URLBuilderFrame


def test_calendar_url_integration():
    """测试日历选择与URL更新的集成"""
    
    # 创建主窗口
    root = tk.Tk()
    root.title("日历URL集成测试")
    root.geometry("800x400")

    # 添加URL显示标签
    url_display = ttk.Label(root, text="当前URL: 未设置", wraplength=700)
    url_display.pack(pady=10)

    def on_url_change(url):
        print(f"URL已更新: {url}")
        url_display.config(text=f"当前URL: {url}")

    # 创建配置管理器
    config = ConfigManager("test_integration_config.json")

    # 创建URL构建器
    url_builder = URLBuilderFrame(root, config, on_url_change)
    
    # 添加测试按钮
    button_frame = ttk.Frame(root)
    button_frame.pack(pady=10)
    
    def get_current_url():
        url = url_builder.get_current_url()
        print(f"获取到的URL: {url}")
        url_display.config(text=f"获取到的URL: {url}")
    
    def get_selections():
        selections = url_builder.get_current_selections()
        print(f"当前选择: {selections}")
        info_text = f"望远镜: {selections['telescope_name']}, 日期: {selections['date']}, 天区: {selections['k_number']}"
        url_display.config(text=info_text)
    
    ttk.Button(button_frame, text="获取当前URL", command=get_current_url).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="获取当前选择", command=get_selections).pack(side=tk.LEFT, padx=5)
    
    # 添加说明
    instruction_label = ttk.Label(root, text="请点击日历按钮选择日期，观察URL是否自动更新", 
                                 font=('Arial', 12, 'bold'))
    instruction_label.pack(pady=20)
    
    # 初始化URL显示
    initial_url = url_builder.get_current_url()
    url_display.config(text=f"初始URL: {initial_url}")
    
    def on_closing():
        # 清理测试配置文件
        try:
            if os.path.exists("test_integration_config.json"):
                os.remove("test_integration_config.json")
        except:
            pass
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    print("=" * 60)
    print("日历URL集成测试")
    print("=" * 60)
    print("1. 点击日历按钮（📅）选择日期")
    print("2. 观察控制台输出和界面上的URL更新")
    print("3. 使用测试按钮验证URL和选择状态")
    print("4. 关闭窗口结束测试")
    print("=" * 60)
    
    root.mainloop()


if __name__ == "__main__":
    test_calendar_url_integration()
