#!/usr/bin/env python3
"""
测试diff_orb集成功能
验证文件名解析、模板匹配和diff操作
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

from filename_parser import FITSFilenameParser
from diff_orb_integration import DiffOrbIntegration
from fits_viewer import FitsImageViewer
from astropy.io import fits


def create_test_fits_files():
    """创建测试FITS文件"""
    # 创建下载目录
    download_root = tempfile.mkdtemp(prefix="diff_test_download_")
    
    # 创建模板目录
    template_root = tempfile.mkdtemp(prefix="diff_test_template_")
    
    print(f"创建测试目录:")
    print(f"  下载目录: {download_root}")
    print(f"  模板目录: {template_root}")
    
    # 创建下载文件（模拟观测数据）
    download_files = []
    download_structures = [
        ("GY5", "20250718", "K096"),
        ("GY1", "20250715", "K001"),
    ]
    
    for tel, date, k_num in download_structures:
        dir_path = os.path.join(download_root, tel, date, k_num)
        os.makedirs(dir_path, exist_ok=True)
        
        # 创建观测数据文件
        filename = f"download_{tel}_{date}_{k_num}_001.fits"
        file_path = os.path.join(dir_path, filename)
        
        # 创建模拟观测数据（包含一些亮点）- 使用完整图像尺寸
        data = np.random.normal(1000, 100, (400, 400))

        # 添加一些"新"亮点（模拟新发现的天体）- 分布在整个图像中
        data[50:55, 50:55] += 2000    # 亮点1 - 左上区域
        data[350:355, 320:325] += 1500  # 亮点2 - 右下区域
        data[80:85, 300:305] += 1800   # 亮点3 - 右上区域
        data[300:305, 80:85] += 1600   # 亮点4 - 左下区域
        
        # 添加一些背景星点 - 分布在整个图像中
        for i in range(20):
            x, y = np.random.randint(20, 380, 2)
            data[x:x+3, y:y+3] += np.random.randint(300, 800)
        
        # 创建FITS文件
        hdu = fits.PrimaryHDU(data)
        hdu.header['OBJECT'] = f'Observation {tel} {date} {k_num}'
        hdu.header['TELESCOP'] = tel
        hdu.header['DATE-OBS'] = f'{date[:4]}-{date[4:6]}-{date[6:8]}'
        hdu.header['EXPTIME'] = 300.0
        hdu.writeto(file_path, overwrite=True)
        
        download_files.append(file_path)
        print(f"  创建下载文件: {filename}")
    
    # 创建模板文件（参考图像）
    template_files = []
    template_structures = [
        ("GY5", "K096", "reference"),
        ("GY1", "K001", "standard"),
    ]
    
    for tel, k_num, type_name in template_structures:
        dir_path = os.path.join(template_root, type_name)
        os.makedirs(dir_path, exist_ok=True)
        
        # 创建模板文件
        filename = f"template_{tel}_{k_num}_{type_name}.fits"
        file_path = os.path.join(dir_path, filename)
        
        # 创建模板数据（基础背景，没有新亮点）- 使用完整图像尺寸
        data = np.random.normal(1000, 100, (400, 400))

        # 只添加背景星点（与观测数据相同的背景）
        np.random.seed(42)  # 固定种子确保背景一致
        for i in range(20):
            x, y = np.random.randint(20, 380, 2)
            data[x:x+3, y:y+3] += np.random.randint(300, 800)
        
        # 创建FITS文件
        hdu = fits.PrimaryHDU(data)
        hdu.header['OBJECT'] = f'Template {tel} {k_num}'
        hdu.header['TELESCOP'] = tel
        hdu.header['TYPE'] = 'TEMPLATE'
        hdu.writeto(file_path, overwrite=True)
        
        template_files.append(file_path)
        print(f"  创建模板文件: {filename}")
    
    return download_root, template_root, download_files, template_files


def test_filename_parser():
    """测试文件名解析器"""
    print("\n" + "=" * 60)
    print("测试文件名解析器")
    print("=" * 60)
    
    parser = FITSFilenameParser()
    
    test_filenames = [
        "download_GY5_20250718_K096_001.fits",
        "download_GY1_20250715_K001_001.fits",
        "template_GY5_K096_reference.fits",
        "template_GY1_K001_standard.fits",
        "GY5_K053-1_No Filter_60S_Bin2_UTC20250622_182433_-14.9C_.fit",
    ]
    
    for filename in test_filenames:
        result = parser.parse_filename(filename)
        print(f"文件名: {filename}")
        if result:
            print(f"  望远镜: {result.get('tel_name', 'N/A')}")
            print(f"  K序号: {result.get('k_number', 'N/A')}")
            print(f"  完整K序号: {result.get('k_full', 'N/A')}")
        else:
            print("  解析失败")
        print()


def test_diff_integration():
    """测试diff集成功能"""
    print("\n" + "=" * 60)
    print("测试diff集成功能")
    print("=" * 60)
    
    # 创建测试文件
    download_root, template_root, download_files, template_files = create_test_fits_files()
    
    try:
        # 创建diff集成对象
        diff_integration = DiffOrbIntegration()
        
        print(f"diff_orb可用: {diff_integration.is_available()}")
        
        if not diff_integration.is_available():
            print("diff_orb模块不可用，跳过diff测试")
            return
        
        # 测试每个下载文件
        for download_file in download_files:
            print(f"\n测试文件: {os.path.basename(download_file)}")
            
            # 检查是否可以处理
            can_process, status = diff_integration.can_process_file(download_file, template_root)
            print(f"  可以处理: {can_process}")
            print(f"  状态: {status}")
            
            if can_process:
                # 查找模板文件
                template_file = diff_integration.find_template_file(download_file, template_root)
                print(f"  找到模板文件: {os.path.basename(template_file) if template_file else 'None'}")
                
                if template_file:
                    # 执行diff操作
                    print("  执行diff操作...")
                    result = diff_integration.process_diff(download_file, template_file)
                    
                    if result:
                        summary = diff_integration.get_diff_summary(result)
                        print(f"  结果摘要:\n{summary}")
                    else:
                        print("  diff操作失败")
    
    finally:
        # 清理测试目录
        try:
            shutil.rmtree(download_root)
            shutil.rmtree(template_root)
            print(f"\n已清理测试目录")
        except:
            pass


def test_gui_integration():
    """测试GUI集成"""
    print("\n" + "=" * 60)
    print("测试GUI集成")
    print("=" * 60)
    
    # 创建测试文件
    download_root, template_root, download_files, template_files = create_test_fits_files()
    
    # 创建GUI测试界面
    root = tk.Tk()
    root.title("Diff集成测试")
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
        "Diff集成功能测试说明：",
        "1. 左侧目录树显示下载目录和模板目录",
        "2. 选择下载目录中的FITS文件（不是模板目录）",
        "3. 如果找到匹配的模板文件，'执行Diff'按钮会变为可用",
        "4. 点击'执行Diff'按钮执行差异检测",
        "5. 操作完成后会显示结果摘要和询问是否查看结果",
        "6. diff操作会检测新的亮点并生成差异图像（处理完整图像）",
        f"7. 下载目录: {download_root}",
        f"8. 模板目录: {template_root}",
        "9. 测试文件包含分布在整个图像中的模拟新亮点",
        "10. 注意：只有下载目录中的文件才能执行diff操作",
        "11. 默认处理完整图像，不抽取中央区域"
    ]
    
    for instruction in test_instructions:
        info_text.insert(tk.END, instruction + "\n")
    
    info_text.config(state=tk.DISABLED)
    
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
    
    print("GUI测试已启动，请按照说明进行测试")
    print("功能测试要点:")
    print("- 选择下载目录中的FITS文件")
    print("- 检查'执行Diff'按钮是否可用")
    print("- 执行diff操作并查看结果")
    print("- 验证新亮点检测功能")
    
    root.mainloop()


def main():
    """主测试函数"""
    print("diff_orb集成功能测试")
    print("=" * 60)
    
    # 测试文件名解析器
    test_filename_parser()
    
    # 测试diff集成功能
    test_diff_integration()
    
    # 测试GUI集成
    test_gui_integration()


if __name__ == "__main__":
    main()
