#!/usr/bin/env python3
"""
FITS文件网页下载器GUI演示脚本
展示如何使用各个组件
"""

import os
import sys
import tempfile
from pathlib import Path

def demo_web_scanner():
    """演示网页扫描功能"""
    print("=" * 60)
    print("演示：网页扫描功能")
    print("=" * 60)
    
    from web_scanner import WebFitsScanner, DirectoryScanner
    
    # 测试URL
    test_url = "https://****/GY5-DATA/20250701/K096/"
    
    print(f"扫描URL: {test_url}")
    print("使用DirectoryScanner...")
    
    try:
        scanner = DirectoryScanner()
        fits_files = scanner.scan_directory_listing(test_url)
        
        print(f"找到 {len(fits_files)} 个FITS文件:")
        for i, (filename, url, size) in enumerate(fits_files[:5]):  # 只显示前5个
            size_str = scanner.session.headers.get('User-Agent', 'Unknown')  # 简单的大小显示
            print(f"  {i+1}. {filename}")
            print(f"     URL: {url}")
            print(f"     大小: {size} 字节")
            print()
        
        if len(fits_files) > 5:
            print(f"  ... 还有 {len(fits_files) - 5} 个文件")
            
    except Exception as e:
        print(f"扫描失败: {e}")
        print("这可能是由于网络连接问题或URL不可访问")

def demo_fits_viewer():
    """演示FITS查看器功能"""
    print("\n" + "=" * 60)
    print("演示：FITS查看器功能")
    print("=" * 60)
    
    import tkinter as tk
    from fits_viewer import FitsImageViewer
    import numpy as np
    from astropy.io import fits
    
    # 创建一个示例FITS文件
    print("创建示例FITS文件...")
    
    # 生成示例数据
    data = np.random.normal(1000, 100, (100, 100))  # 100x100的随机数据
    data[40:60, 40:60] += 500  # 添加一个亮区域
    
    # 保存为临时FITS文件
    temp_dir = tempfile.mkdtemp()
    fits_path = os.path.join(temp_dir, "demo.fits")
    
    hdu = fits.PrimaryHDU(data)
    hdu.header['OBJECT'] = 'Demo Image'
    hdu.header['EXPTIME'] = 60.0
    hdu.writeto(fits_path, overwrite=True)
    
    print(f"示例FITS文件已创建: {fits_path}")
    
    # 创建GUI窗口演示查看器
    print("创建FITS查看器窗口...")
    
    root = tk.Tk()
    root.title("FITS查看器演示")
    root.geometry("800x600")
    
    viewer = FitsImageViewer(root)
    
    # 加载示例文件
    if viewer.load_fits_file(fits_path):
        print("✓ FITS文件加载成功")
        print("查看器窗口已打开，您可以:")
        print("  - 更改显示模式（线性、对数、平方根、反双曲正弦）")
        print("  - 更改颜色映射")
        print("  - 查看图像统计信息")
        print("  - 保存图像")
        print("\n关闭窗口继续演示...")
        
        root.mainloop()
    else:
        print("✗ FITS文件加载失败")
        root.destroy()
    
    # 清理临时文件
    try:
        os.remove(fits_path)
        os.rmdir(temp_dir)
    except:
        pass

def demo_full_gui():
    """演示完整GUI应用程序"""
    print("\n" + "=" * 60)
    print("演示：完整GUI应用程序")
    print("=" * 60)
    
    print("启动完整的FITS文件网页下载器GUI...")
    print("GUI包含以下功能:")
    print("  1. 扫描和下载标签页:")
    print("     - 输入URL并扫描FITS文件")
    print("     - 选择要下载的文件")
    print("     - 配置下载参数")
    print("     - 批量下载文件")
    print("  2. 图像查看标签页:")
    print("     - 加载和显示FITS文件")
    print("     - 多种显示模式和颜色映射")
    print("     - 图像统计信息")
    print("  3. 日志标签页:")
    print("     - 查看操作日志")
    print("     - 保存日志到文件")
    
    try:
        from fits_web_downloader import FitsWebDownloaderGUI
        
        print("\n正在启动GUI...")
        print("关闭GUI窗口以结束演示。")
        
        app = FitsWebDownloaderGUI()
        app.run()
        
    except Exception as e:
        print(f"GUI启动失败: {e}")

def show_usage_instructions():
    """显示使用说明"""
    print("\n" + "=" * 60)
    print("使用说明")
    print("=" * 60)
    
    print("1. 启动GUI应用程序:")
    print("   python fits_web_downloader.py")
    print("   或")
    print("   python run_gui.py")
    print()
    
    print("2. 使用步骤:")
    print("   a) 在'扫描和下载'标签页中输入URL")
    print("   b) 点击'扫描'按钮获取FITS文件列表")
    print("   c) 选择要下载的文件")
    print("   d) 设置下载目录和参数")
    print("   e) 点击'开始下载'")
    print("   f) 在'图像查看'标签页中查看下载的文件")
    print()
    
    print("3. 默认测试URL:")
    print("   https://****/GY5-DATA/20250701/K096/")
    print()
    
    print("4. 支持的文件格式:")
    print("   - .fits")
    print("   - .fit") 
    print("   - .fts")
    print()
    
    print("5. 注意事项:")
    print("   - 需要稳定的网络连接")
    print("   - FITS文件通常较大，确保有足够磁盘空间")
    print("   - 可以调整并发数以适应网络条件")

def main():
    """主演示函数"""
    print("FITS文件网页下载器GUI - 功能演示")
    print("=" * 60)
    
    demos = [
        ("网页扫描功能", demo_web_scanner),
        ("FITS查看器功能", demo_fits_viewer),
        ("完整GUI应用程序", demo_full_gui)
    ]
    
    print("可用的演示:")
    for i, (name, _) in enumerate(demos, 1):
        print(f"  {i}. {name}")
    print(f"  {len(demos)+1}. 显示使用说明")
    print(f"  0. 退出")
    
    while True:
        try:
            choice = input(f"\n请选择演示 (0-{len(demos)+1}): ").strip()
            
            if choice == '0':
                print("演示结束。")
                break
            elif choice == str(len(demos)+1):
                show_usage_instructions()
            elif choice.isdigit() and 1 <= int(choice) <= len(demos):
                _, demo_func = demos[int(choice)-1]
                demo_func()
            else:
                print("无效选择，请重试。")
                
        except KeyboardInterrupt:
            print("\n演示被中断。")
            break
        except Exception as e:
            print(f"演示出错: {e}")

if __name__ == "__main__":
    main()
