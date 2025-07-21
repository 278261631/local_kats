#!/usr/bin/env python3
"""
测试增强的diff功能
验证首次刷新、简化流程和配置化输出目录
"""

import os
import tempfile
import shutil
import numpy as np
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import sys

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fits_viewer import FitsImageViewer
from config_manager import ConfigManager
from astropy.io import fits


def create_test_environment():
    """创建测试环境"""
    # 创建各种测试目录
    download_root = tempfile.mkdtemp(prefix="enhanced_diff_download_")
    template_root = tempfile.mkdtemp(prefix="enhanced_diff_template_")
    diff_output_root = tempfile.mkdtemp(prefix="enhanced_diff_output_")
    
    print(f"创建测试环境:")
    print(f"  下载目录: {download_root}")
    print(f"  模板目录: {template_root}")
    print(f"  diff输出目录: {diff_output_root}")
    
    # 创建下载文件
    download_structures = [
        ("GY5", "20250721", "K096"),
        ("GY1", "20250720", "K001"),
    ]
    
    download_files = []
    for tel, date, k_num in download_structures:
        dir_path = os.path.join(download_root, tel, date, k_num)
        os.makedirs(dir_path, exist_ok=True)
        
        # 创建观测文件
        filename = f"enhanced_test_{tel}_{date}_{k_num}_001.fits"
        file_path = os.path.join(dir_path, filename)
        
        # 创建包含新亮点的观测数据
        data = np.random.normal(1000, 100, (300, 300))
        # 添加新亮点
        data[100:105, 100:105] += 2000
        data[200:205, 150:155] += 1500
        data[50:55, 250:255] += 1800
        
        hdu = fits.PrimaryHDU(data)
        hdu.header['OBJECT'] = f'Enhanced Test {tel} {date} {k_num}'
        hdu.header['TELESCOP'] = tel
        hdu.writeto(file_path, overwrite=True)
        
        download_files.append(file_path)
        print(f"  创建下载文件: {filename}")
    
    # 创建模板文件
    template_structures = [
        ("GY5", "K096", "reference"),
        ("GY1", "K001", "standard"),
    ]
    
    template_files = []
    for tel, k_num, type_name in template_structures:
        dir_path = os.path.join(template_root, type_name)
        os.makedirs(dir_path, exist_ok=True)
        
        filename = f"enhanced_template_{tel}_{k_num}_{type_name}.fits"
        file_path = os.path.join(dir_path, filename)
        
        # 创建基础模板数据（无新亮点）
        data = np.random.normal(1000, 100, (300, 300))
        
        hdu = fits.PrimaryHDU(data)
        hdu.header['OBJECT'] = f'Enhanced Template {tel} {k_num}'
        hdu.header['TELESCOP'] = tel
        hdu.writeto(file_path, overwrite=True)
        
        template_files.append(file_path)
        print(f"  创建模板文件: {filename}")
    
    return download_root, template_root, diff_output_root, download_files, template_files


def test_enhanced_diff_functionality():
    """测试增强的diff功能"""
    print("=" * 60)
    print("增强diff功能测试")
    print("=" * 60)
    
    # 创建测试环境
    download_root, template_root, diff_output_root, download_files, template_files = create_test_environment()
    
    try:
        # 创建GUI测试界面
        root = tk.Tk()
        root.title("增强diff功能测试")
        root.geometry("1400x900")
        
        # 创建配置管理器并设置测试配置
        config = ConfigManager("test_enhanced_diff_config.json")
        config.update_last_selected(
            download_directory=download_root,
            template_directory=template_root,
            diff_output_directory=diff_output_root
        )
        
        # 模拟回调函数
        def get_download_dir():
            return download_root
        
        def get_template_dir():
            return template_root
        
        def get_diff_output_dir():
            return diff_output_root
        
        def get_url_selections():
            return {
                'telescope_name': 'GY5',
                'date': '20250721',
                'k_number': 'K096'
            }
        
        # 创建增强版FITS查看器
        fits_viewer = FitsImageViewer(
            root,
            get_download_dir_callback=get_download_dir,
            get_template_dir_callback=get_template_dir,
            get_diff_output_dir_callback=get_diff_output_dir,
            get_url_selections_callback=get_url_selections
        )
        
        # 添加测试信息显示
        info_frame = ttk.Frame(root)
        info_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
        
        info_text = tk.Text(info_frame, height=10, width=120)
        info_scroll = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=info_text.yview)
        info_text.configure(yscrollcommand=info_scroll.set)
        
        info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 添加测试说明
        test_instructions = [
            "增强diff功能测试说明：",
            "",
            "🔄 首次刷新测试:",
            "  - 打开时应自动刷新目录树",
            "  - 左侧目录树应显示下载目录和模板目录",
            "",
            "📁 配置化输出目录测试:",
            f"  - diff输出根目录: {diff_output_root}",
            "  - 执行diff时会在根目录下创建 YYYYMMDD/文件名_时间戳/ 结构",
            "",
            "⚡ 简化流程测试:",
            "  - 选择下载目录中的FITS文件",
            "  - 点击'执行Diff'按钮",
            "  - 操作完成后不会询问是否查看结果",
            "  - 自动显示差异图像并打开结果目录",
            "",
            "📊 测试步骤:",
            "1. 确认目录树已自动刷新并显示文件",
            "2. 选择下载目录中的FITS文件",
            "3. 点击'执行Diff'按钮",
            "4. 观察是否自动显示结果并打开目录",
            "5. 检查输出目录结构是否正确",
            "",
            f"📂 测试目录:",
            f"  下载: {download_root}",
            f"  模板: {template_root}",
            f"  输出: {diff_output_root}",
        ]
        
        for instruction in test_instructions:
            info_text.insert(tk.END, instruction + "\n")
        
        info_text.config(state=tk.DISABLED)
        
        # 添加测试控制按钮
        control_frame = ttk.Frame(root)
        control_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
        
        def check_output_structure():
            """检查输出目录结构"""
            print(f"\n检查输出目录结构: {diff_output_root}")
            if os.path.exists(diff_output_root):
                for root_dir, dirs, files in os.walk(diff_output_root):
                    level = root_dir.replace(diff_output_root, '').count(os.sep)
                    indent = '  ' * level
                    rel_path = os.path.relpath(root_dir, diff_output_root)
                    if rel_path == '.':
                        print(f"{indent}[输出根目录]")
                    else:
                        print(f"{indent}{rel_path}/")
                    
                    subindent = '  ' * (level + 1)
                    for file in files:
                        print(f"{subindent}{file}")
            else:
                print("  输出目录不存在")
        
        def manual_refresh():
            """手动刷新目录树"""
            fits_viewer._refresh_directory_tree()
            print("手动刷新目录树完成")
        
        def show_config():
            """显示当前配置"""
            print(f"\n当前配置:")
            print(f"  下载目录: {get_download_dir()}")
            print(f"  模板目录: {get_template_dir()}")
            print(f"  diff输出目录: {get_diff_output_dir()}")
        
        ttk.Button(control_frame, text="检查输出结构", command=check_output_structure).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="手动刷新", command=manual_refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="显示配置", command=show_config).pack(side=tk.LEFT, padx=5)
        
        def on_closing():
            """关闭时清理"""
            try:
                # 清理测试目录
                shutil.rmtree(download_root)
                shutil.rmtree(template_root)
                shutil.rmtree(diff_output_root)
                print(f"\n已清理测试目录")
            except Exception as e:
                print(f"清理测试目录失败: {e}")
            
            try:
                # 清理配置文件
                if os.path.exists("test_enhanced_diff_config.json"):
                    os.remove("test_enhanced_diff_config.json")
            except:
                pass
            
            root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        print("\n增强diff功能测试GUI已启动")
        print("请按照说明进行测试，关注以下要点:")
        print("- 首次打开时目录树是否自动刷新")
        print("- diff操作是否使用配置的输出目录")
        print("- 操作完成后是否自动显示结果")
        print("- 输出目录结构是否按日期和文件名组织")
        
        root.mainloop()
    
    except Exception as e:
        print(f"测试过程中出错: {e}")
        # 清理
        try:
            shutil.rmtree(download_root)
            shutil.rmtree(template_root) 
            shutil.rmtree(diff_output_root)
        except:
            pass


if __name__ == "__main__":
    test_enhanced_diff_functionality()
