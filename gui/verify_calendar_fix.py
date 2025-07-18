#!/usr/bin/env python3
"""
验证日历选择后URL参数更新的修复
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from url_builder import URLBuilderFrame


def verify_calendar_fix():
    """验证日历修复"""
    
    print("=" * 60)
    print("验证日历选择后URL参数更新修复")
    print("=" * 60)
    
    # 创建主窗口
    root = tk.Tk()
    root.title("日历修复验证")
    root.geometry("900x500")
    
    # 状态变量
    url_updates = []
    
    def on_url_change(url):
        """URL变化回调"""
        url_updates.append(url)
        print(f"✓ URL已更新: {url}")
        status_text.insert(tk.END, f"URL更新: {url}\n")
        status_text.see(tk.END)
    
    # 创建配置管理器
    config = ConfigManager("verify_config.json")
    
    # 创建URL构建器
    url_builder = URLBuilderFrame(root, config, on_url_change)
    
    # 创建状态显示区域
    status_frame = ttk.LabelFrame(root, text="状态日志", padding=10)
    status_frame.pack(fill=tk.BOTH, expand=True, pady=10)
    
    status_text = tk.Text(status_frame, height=10, width=80)
    scrollbar = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=status_text.yview)
    status_text.configure(yscrollcommand=scrollbar.set)
    
    status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # 测试按钮区域
    test_frame = ttk.LabelFrame(root, text="测试操作", padding=10)
    test_frame.pack(fill=tk.X, pady=(0, 10))
    
    def test_today_button():
        """测试今天按钮"""
        initial_url = url_builder.get_current_url()
        url_builder._set_today()
        new_url = url_builder.get_current_url()
        
        if initial_url != new_url:
            status_text.insert(tk.END, f"✓ 今天按钮测试通过: {new_url}\n")
            print(f"✓ 今天按钮测试通过")
        else:
            status_text.insert(tk.END, f"⚠ 今天按钮可能没有改变日期\n")
        status_text.see(tk.END)
    
    def show_current_status():
        """显示当前状态"""
        url = url_builder.get_current_url()
        selections = url_builder.get_current_selections()
        
        status_text.insert(tk.END, f"当前URL: {url}\n")
        status_text.insert(tk.END, f"当前选择: {selections}\n")
        status_text.insert(tk.END, f"URL更新次数: {len(url_updates)}\n")
        status_text.insert(tk.END, "-" * 50 + "\n")
        status_text.see(tk.END)
    
    def clear_log():
        """清除日志"""
        status_text.delete(1.0, tk.END)
        url_updates.clear()
    
    # 测试按钮
    ttk.Button(test_frame, text="测试今天按钮", command=test_today_button).pack(side=tk.LEFT, padx=5)
    ttk.Button(test_frame, text="显示当前状态", command=show_current_status).pack(side=tk.LEFT, padx=5)
    ttk.Button(test_frame, text="清除日志", command=clear_log).pack(side=tk.LEFT, padx=5)
    
    # 说明标签
    instruction_frame = ttk.Frame(root)
    instruction_frame.pack(fill=tk.X, pady=5)
    
    instructions = [
        "验证步骤：",
        "1. 点击日历按钮（📅）打开日历选择器",
        "2. 选择不同的日期并点击确定",
        "3. 观察状态日志中的URL更新信息",
        "4. 使用测试按钮验证功能",
        "5. 如果看到URL更新日志，说明修复成功"
    ]
    
    for i, instruction in enumerate(instructions):
        style = 'bold' if i == 0 else 'normal'
        label = ttk.Label(instruction_frame, text=instruction, font=('Arial', 9, style))
        label.pack(anchor='w')
    
    # 初始状态
    initial_url = url_builder.get_current_url()
    status_text.insert(tk.END, f"初始URL: {initial_url}\n")
    status_text.insert(tk.END, "请点击日历按钮测试日期选择功能...\n")
    status_text.insert(tk.END, "-" * 50 + "\n")
    
    def on_closing():
        """关闭时清理"""
        try:
            if os.path.exists("verify_config.json"):
                os.remove("verify_config.json")
        except:
            pass
        
        # 显示测试结果
        if len(url_updates) > 1:  # 初始URL + 至少一次更新
            messagebox.showinfo("验证结果", 
                              f"✓ 日历修复验证成功！\n"
                              f"URL更新了 {len(url_updates)} 次\n"
                              f"最终URL: {url_updates[-1] if url_updates else '无'}")
        else:
            messagebox.showwarning("验证结果", 
                                 "⚠ 请测试日历选择功能后再关闭")
        
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    print("验证窗口已打开，请按照说明测试日历功能")
    print("关闭窗口时会显示验证结果")
    
    root.mainloop()


if __name__ == "__main__":
    verify_calendar_fix()
