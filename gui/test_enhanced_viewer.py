#!/usr/bin/env python3
"""
测试增强版FITS图像查看器
验证目录树和打开目录功能
"""

import os
import tempfile
import shutil
import numpy as np
from pathlib import Path
import tkinter as tk
from tkinter import ttk

# 添加当前目录到路径
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fits_viewer import FitsImageViewer
from astropy.io import fits


def create_test_fits_files():
    """创建测试FITS文件和目录结构"""
    # 创建临时根目录
    temp_root = tempfile.mkdtemp(prefix="fits_viewer_test_")
    
    # 创建测试目录结构
    test_structures = [
        ("GY1", "20250715", "K001"),
        ("GY1", "20250715", "K002"),
        ("GY1", "20250716", "K001"),
        ("GY2", "20250715", "K001"),
        ("GY5", "20250718", "K096"),
    ]
    
    # 创建目录并添加测试FITS文件
    for tel, date, k_num in test_structures:
        dir_path = os.path.join(temp_root, tel, date, k_num)
        os.makedirs(dir_path, exist_ok=True)
        
        # 创建测试FITS文件
        for i in range(2):
            filename = f"test_{tel}_{date}_{k_num}_{i+1:03d}.fits"
            file_path = os.path.join(dir_path, filename)
            
            # 创建简单的测试数据
            data = np.random.normal(1000, 100, (100, 100))
            data[40:60, 40:60] += 500  # 添加一个亮区域
            
            # 创建FITS文件
            hdu = fits.PrimaryHDU(data)
            hdu.header['OBJECT'] = f'Test {tel} {date} {k_num}'
            hdu.header['TELESCOP'] = tel
            hdu.header['DATE-OBS'] = f'{date[:4]}-{date[4:6]}-{date[6:8]}'
            hdu.header['EXPTIME'] = 60.0
            hdu.writeto(file_path, overwrite=True)
    
    return temp_root


def test_enhanced_fits_viewer():
    """测试增强版FITS查看器"""
    
    # 创建测试数据
    test_root = create_test_fits_files()
    
    print("=" * 60)
    print("增强版FITS图像查看器测试")
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
    root.title("增强版FITS查看器测试")
    root.geometry("1200x800")
    
    # 模拟回调函数
    def get_download_dir():
        return test_root
    
    def get_url_selections():
        return {
            'telescope_name': 'GY5',
            'date': '20250718',
            'k_number': 'K096'
        }
    
    # 创建增强版FITS查看器
    fits_viewer = FitsImageViewer(
        root,
        get_download_dir_callback=get_download_dir,
        get_url_selections_callback=get_url_selections
    )
    
    # 添加测试信息显示
    info_frame = ttk.Frame(root)
    info_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
    
    info_text = tk.Text(info_frame, height=6, width=100)
    info_scroll = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=info_text.yview)
    info_text.configure(yscrollcommand=info_scroll.set)
    
    info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    info_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    
    # 添加测试说明
    test_instructions = [
        "增强版FITS查看器测试说明：",
        "1. 左侧显示目录树，包含所有望远镜、日期、天区的层次结构",
        "2. 点击FITS文件节点可以在右侧显示图像",
        "3. 双击目录节点可以在文件管理器中打开该目录",
        "4. 点击'打开下载目录'按钮可以打开当前选择对应的目录",
        "5. 使用'刷新目录'、'展开全部'、'折叠全部'按钮控制目录树",
        f"6. 测试根目录: {test_root}",
        "7. 当前模拟选择: GY5/20250718/K096"
    ]
    
    for instruction in test_instructions:
        info_text.insert(tk.END, instruction + "\n")
    
    info_text.config(state=tk.DISABLED)
    
    def on_closing():
        """关闭时清理"""
        try:
            # 清理测试目录
            shutil.rmtree(test_root)
            print(f"已清理测试目录: {test_root}")
        except Exception as e:
            print(f"清理测试目录失败: {e}")
        
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    print("测试GUI已启动，请按照说明进行测试")
    print("功能测试要点:")
    print("- 目录树是否正确显示层次结构")
    print("- 点击FITS文件是否能正确加载和显示")
    print("- 双击目录是否能打开文件管理器")
    print("- 打开下载目录按钮是否工作正常")
    print("- 目录树控制按钮是否正常工作")
    
    root.mainloop()


if __name__ == "__main__":
    test_enhanced_fits_viewer()
