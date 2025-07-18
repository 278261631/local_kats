#!/usr/bin/env python3
"""
测试模板目录功能和延迟显示功能
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


def create_test_directories():
    """创建测试目录结构"""
    # 创建下载目录
    download_root = tempfile.mkdtemp(prefix="download_test_")
    
    # 创建模板目录
    template_root = tempfile.mkdtemp(prefix="template_test_")
    
    # 创建下载目录结构
    download_structures = [
        ("GY1", "20250715", "K001"),
        ("GY5", "20250718", "K096"),
    ]
    
    for tel, date, k_num in download_structures:
        dir_path = os.path.join(download_root, tel, date, k_num)
        os.makedirs(dir_path, exist_ok=True)
        
        # 创建测试FITS文件
        for i in range(2):
            filename = f"download_{tel}_{date}_{k_num}_{i+1:03d}.fits"
            file_path = os.path.join(dir_path, filename)
            
            # 创建测试数据
            data = np.random.normal(1000, 100, (100, 100))
            data[30:70, 30:70] += 300  # 添加一个亮区域
            
            # 创建FITS文件
            hdu = fits.PrimaryHDU(data)
            hdu.header['OBJECT'] = f'Download {tel} {date} {k_num}'
            hdu.header['TELESCOP'] = tel
            hdu.header['DATE-OBS'] = f'{date[:4]}-{date[4:6]}-{date[6:8]}'
            hdu.writeto(file_path, overwrite=True)
    
    # 创建模板目录结构
    template_structures = [
        "calibration",
        "reference",
        "templates/standard",
        "templates/custom"
    ]
    
    for structure in template_structures:
        dir_path = os.path.join(template_root, structure)
        os.makedirs(dir_path, exist_ok=True)
        
        # 创建测试FITS文件
        for i in range(3):
            filename = f"template_{structure.replace('/', '_')}_{i+1:03d}.fits"
            file_path = os.path.join(dir_path, filename)
            
            # 创建测试数据
            data = np.random.normal(500, 50, (80, 80))
            data[20:60, 20:60] += 200  # 添加一个亮区域
            
            # 创建FITS文件
            hdu = fits.PrimaryHDU(data)
            hdu.header['OBJECT'] = f'Template {structure}'
            hdu.header['TYPE'] = 'TEMPLATE'
            hdu.writeto(file_path, overwrite=True)
    
    return download_root, template_root


def test_template_directory_functionality():
    """测试模板目录功能"""
    
    # 创建测试数据
    download_root, template_root = create_test_directories()
    
    print("=" * 60)
    print("模板目录和延迟显示功能测试")
    print("=" * 60)
    print(f"下载目录: {download_root}")
    print(f"模板目录: {template_root}")
    
    # 显示目录结构
    print("\n下载目录结构:")
    for root, dirs, files in os.walk(download_root):
        level = root.replace(download_root, '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            print(f"{subindent}{file}")
    
    print("\n模板目录结构:")
    for root, dirs, files in os.walk(template_root):
        level = root.replace(template_root, '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            print(f"{subindent}{file}")
    
    print("=" * 60)
    
    # 创建GUI测试界面
    root = tk.Tk()
    root.title("模板目录和延迟显示测试")
    root.geometry("1400x900")
    
    # 模拟回调函数
    def get_download_dir():
        return download_root
    
    def get_template_dir():
        return template_root
    
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
        get_template_dir_callback=get_template_dir,
        get_url_selections_callback=get_url_selections
    )
    
    # 添加测试信息显示
    info_frame = ttk.Frame(root)
    info_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
    
    info_text = tk.Text(info_frame, height=8, width=120)
    info_scroll = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=info_text.yview)
    info_text.configure(yscrollcommand=info_scroll.set)
    
    info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    info_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    
    # 添加测试说明
    test_instructions = [
        "模板目录和延迟显示功能测试说明：",
        "1. 左侧目录树现在显示两个根节点：📁 下载目录 和 📋 模板目录",
        "2. 下载目录按照望远镜/日期/天区层次组织",
        "3. 模板目录按照实际文件夹结构组织",
        "4. 点击FITS文件节点只会选择文件，不会立即显示",
        "5. 选择文件后，点击'显示图像'按钮才会加载和显示图像",
        "6. 这样可以提高程序响应速度，特别是处理大文件时",
        "7. 双击目录节点可以在文件管理器中打开该目录",
        f"8. 下载目录: {download_root}",
        f"9. 模板目录: {template_root}",
        "10. 测试要点：选择文件 → 点击显示按钮 → 查看图像加载"
    ]
    
    for instruction in test_instructions:
        info_text.insert(tk.END, instruction + "\n")
    
    info_text.config(state=tk.DISABLED)
    
    # 添加测试控制按钮
    control_frame = ttk.Frame(root)
    control_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
    
    def refresh_trees():
        """刷新目录树"""
        fits_viewer._refresh_directory_tree()
        print("目录树已刷新")
    
    def expand_all():
        """展开所有节点"""
        fits_viewer._expand_all()
        print("已展开所有节点")
    
    def collapse_all():
        """折叠所有节点"""
        fits_viewer._collapse_all()
        print("已折叠所有节点")
    
    ttk.Button(control_frame, text="刷新目录树", command=refresh_trees).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text="展开全部", command=expand_all).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text="折叠全部", command=collapse_all).pack(side=tk.LEFT, padx=5)
    
    def on_closing():
        """关闭时清理"""
        try:
            # 清理测试目录
            shutil.rmtree(download_root)
            shutil.rmtree(template_root)
            print(f"已清理测试目录")
        except Exception as e:
            print(f"清理测试目录失败: {e}")
        
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    print("测试GUI已启动，请按照说明进行测试")
    print("功能测试要点:")
    print("- 目录树是否显示下载目录和模板目录两个根节点")
    print("- 点击FITS文件是否只选择而不立即显示")
    print("- 选择文件后'显示图像'按钮是否可用")
    print("- 点击'显示图像'按钮是否正确加载和显示")
    print("- 双击目录是否能打开文件管理器")
    
    root.mainloop()


if __name__ == "__main__":
    test_template_directory_functionality()
