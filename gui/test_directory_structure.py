#!/usr/bin/env python3
"""
测试新的目录结构功能
验证文件是否按照 根目录/tel_name/YYYYMMDD/K0?? 的结构保存
"""

import os
import tempfile
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

# 添加当前目录到路径
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from url_builder import URLBuilderFrame


def create_test_directory_structure():
    """创建测试目录结构"""
    # 创建临时根目录
    temp_root = tempfile.mkdtemp(prefix="fits_download_test_")
    
    # 创建一些测试目录结构
    test_structures = [
        ("GY1", "20250715", "K001"),
        ("GY1", "20250715", "K002"),
        ("GY1", "20250716", "K001"),
        ("GY2", "20250715", "K001"),
        ("GY5", "20250718", "K096"),
    ]
    
    # 创建目录并添加一些测试文件
    for tel, date, k_num in test_structures:
        dir_path = os.path.join(temp_root, tel, date, k_num)
        os.makedirs(dir_path, exist_ok=True)
        
        # 创建一些测试FITS文件
        test_files = [
            f"test_{tel}_{date}_{k_num}_001.fits",
            f"test_{tel}_{date}_{k_num}_002.fits"
        ]
        
        for filename in test_files:
            file_path = os.path.join(dir_path, filename)
            with open(file_path, 'w') as f:
                f.write(f"# Test FITS file\n# Tel: {tel}, Date: {date}, K: {k_num}\n")
    
    return temp_root


def test_directory_structure_gui():
    """测试目录结构的GUI"""
    
    # 创建测试目录结构
    test_root = create_test_directory_structure()
    
    print("=" * 60)
    print("目录结构测试")
    print("=" * 60)
    print(f"测试根目录: {test_root}")
    print("已创建以下测试目录结构:")
    
    # 显示创建的目录结构
    for root, dirs, files in os.walk(test_root):
        level = root.replace(test_root, '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            print(f"{subindent}{file}")
    
    print("=" * 60)
    
    # 创建GUI测试界面
    root = tk.Tk()
    root.title("目录结构测试")
    root.geometry("900x600")
    
    # 状态显示区域
    status_frame = ttk.LabelFrame(root, text="测试状态", padding=10)
    status_frame.pack(fill=tk.BOTH, expand=True, pady=10)
    
    status_text = tk.Text(status_frame, height=15, width=80)
    scrollbar = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=status_text.yview)
    status_text.configure(yscrollcommand=scrollbar.set)
    
    status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def log_message(message):
        """添加日志消息"""
        status_text.insert(tk.END, f"{message}\n")
        status_text.see(tk.END)
        print(message)
    
    # 创建配置管理器
    config = ConfigManager("test_dir_structure_config.json")
    
    # 设置测试根目录
    config.update_last_selected(download_directory=test_root)
    
    def on_url_change(url):
        log_message(f"URL已更新: {url}")
    
    # 创建URL构建器
    url_builder = URLBuilderFrame(root, config, on_url_change)
    
    # 测试按钮区域
    test_frame = ttk.LabelFrame(root, text="测试操作", padding=10)
    test_frame.pack(fill=tk.X, pady=(0, 10))
    
    def test_directory_creation():
        """测试目录创建逻辑"""
        selections = url_builder.get_current_selections()
        tel_name = selections.get('telescope_name', 'Unknown')
        date = selections.get('date', 'Unknown')
        k_number = selections.get('k_number', 'Unknown')
        
        # 模拟下载目录创建
        actual_download_dir = os.path.join(test_root, tel_name, date, k_number)
        
        log_message(f"当前选择: {tel_name}/{date}/{k_number}")
        log_message(f"预期下载目录: {actual_download_dir}")
        
        if os.path.exists(actual_download_dir):
            log_message("✓ 目录已存在")
            files = list(Path(actual_download_dir).glob("*.fits"))
            log_message(f"✓ 找到 {len(files)} 个FITS文件")
            for file in files:
                log_message(f"  - {file.name}")
        else:
            log_message("⚠ 目录不存在，将在下载时创建")
            os.makedirs(actual_download_dir, exist_ok=True)
            log_message(f"✓ 已创建目录: {actual_download_dir}")
    
    def test_file_search():
        """测试文件搜索逻辑"""
        log_message("开始搜索FITS文件...")
        
        # 搜索所有FITS文件
        all_fits_files = []
        for root_dir, dirs, files in os.walk(test_root):
            for file in files:
                if file.endswith(('.fits', '.fit', '.fts')):
                    rel_path = os.path.relpath(root_dir, test_root)
                    all_fits_files.append((rel_path, os.path.join(root_dir, file)))
        
        log_message(f"✓ 找到 {len(all_fits_files)} 个FITS文件:")
        for path_desc, file_path in all_fits_files:
            filename = os.path.basename(file_path)
            log_message(f"  {path_desc}: {filename}")
    
    def show_directory_tree():
        """显示目录树"""
        log_message("目录结构:")
        for root_dir, dirs, files in os.walk(test_root):
            level = root_dir.replace(test_root, '').count(os.sep)
            indent = '  ' * level
            rel_path = os.path.relpath(root_dir, test_root)
            if rel_path == '.':
                log_message(f"{indent}[根目录]")
            else:
                log_message(f"{indent}{rel_path}/")
            
            subindent = '  ' * (level + 1)
            for file in files:
                log_message(f"{subindent}{file}")
    
    def clear_log():
        """清除日志"""
        status_text.delete(1.0, tk.END)
    
    # 测试按钮
    ttk.Button(test_frame, text="测试目录创建", command=test_directory_creation).pack(side=tk.LEFT, padx=5)
    ttk.Button(test_frame, text="测试文件搜索", command=test_file_search).pack(side=tk.LEFT, padx=5)
    ttk.Button(test_frame, text="显示目录树", command=show_directory_tree).pack(side=tk.LEFT, padx=5)
    ttk.Button(test_frame, text="清除日志", command=clear_log).pack(side=tk.LEFT, padx=5)
    
    # 说明标签
    instruction_frame = ttk.Frame(root)
    instruction_frame.pack(fill=tk.X, pady=5)
    
    instructions = [
        "目录结构测试说明：",
        "1. 使用URL构建器选择不同的望远镜、日期、天区",
        "2. 点击'测试目录创建'查看对应的目录路径",
        "3. 点击'测试文件搜索'查看所有可用的FITS文件",
        "4. 点击'显示目录树'查看完整的目录结构",
        f"5. 测试根目录: {test_root}"
    ]
    
    for i, instruction in enumerate(instructions):
        style = 'bold' if i == 0 else 'normal'
        label = ttk.Label(instruction_frame, text=instruction, font=('Arial', 9, style))
        label.pack(anchor='w')
    
    # 初始化显示
    log_message(f"测试环境已准备就绪")
    log_message(f"根目录: {test_root}")
    show_directory_tree()
    
    def on_closing():
        """关闭时清理"""
        try:
            # 清理测试目录
            shutil.rmtree(test_root)
            log_message(f"已清理测试目录: {test_root}")
        except:
            pass
        
        try:
            # 清理配置文件
            if os.path.exists("test_dir_structure_config.json"):
                os.remove("test_dir_structure_config.json")
        except:
            pass
        
        messagebox.showinfo("测试完成", "目录结构测试已完成，测试文件已清理")
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    print("测试GUI已启动，请按照说明进行测试")
    root.mainloop()


if __name__ == "__main__":
    test_directory_structure_gui()
