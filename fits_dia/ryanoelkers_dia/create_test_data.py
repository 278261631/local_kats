#!/usr/bin/env python3
"""
创建测试FITS文件用于DIA测试
"""

import os
import numpy as np
from astropy.io import fits


def create_test_fits_pair(output_dir="../test_data"):
    """
    创建一对测试FITS文件用于DIA分析
    
    Args:
        output_dir (str): 输出目录
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 图像尺寸
    height, width = 300, 300
    
    # 创建参考图像（模板）
    print("创建参考图像...")
    np.random.seed(42)  # 固定随机种子确保可重复性
    
    # 基础背景
    reference_data = np.random.normal(1000, 50, (height, width))
    
    # 添加一些背景星点
    star_positions = [
        (50, 50), (100, 80), (150, 120), (200, 180), (250, 220),
        (80, 150), (120, 200), (180, 250), (220, 100), (160, 60)
    ]
    
    for x, y in star_positions:
        # 创建高斯星点
        y_grid, x_grid = np.ogrid[:height, :width]
        star_profile = 800 * np.exp(-((x_grid - x)**2 + (y_grid - y)**2) / (2 * 3**2))
        reference_data += star_profile
    
    # 保存参考图像
    ref_path = os.path.join(output_dir, "reference_template.fits")
    hdu = fits.PrimaryHDU(reference_data.astype(np.float32))
    hdu.header['OBJECT'] = 'Reference Template'
    hdu.header['TELESCOP'] = 'TEST'
    hdu.header['EXPTIME'] = 300.0
    hdu.header['DATE-OBS'] = '2025-07-23'
    hdu.writeto(ref_path, overwrite=True)
    print(f"参考图像已保存: {ref_path}")
    
    # 创建科学图像（包含新的瞬变源）
    print("创建科学图像...")
    np.random.seed(43)  # 不同的随机种子模拟不同的噪声
    
    # 基础背景（与参考图像相似但有噪声差异）
    science_data = np.random.normal(1000, 50, (height, width))
    
    # 添加相同的背景星点（稍有位置偏移模拟观测误差）
    for x, y in star_positions:
        # 添加小的随机偏移
        x_offset = np.random.normal(0, 0.5)
        y_offset = np.random.normal(0, 0.5)
        x_new = x + x_offset
        y_new = y + y_offset
        
        # 创建高斯星点（亮度稍有变化）
        brightness_factor = np.random.uniform(0.9, 1.1)
        y_grid, x_grid = np.ogrid[:height, :width]
        star_profile = 800 * brightness_factor * np.exp(-((x_grid - x_new)**2 + (y_grid - y_new)**2) / (2 * 3**2))
        science_data += star_profile
    
    # 添加新的瞬变源
    transient_positions = [
        (75, 125, 1200),   # (x, y, brightness)
        (175, 75, 800),
        (225, 175, 1500),
        (125, 225, 600)
    ]
    
    print(f"添加 {len(transient_positions)} 个瞬变源...")
    for x, y, brightness in transient_positions:
        # 创建瞬变源（稍微更宽的PSF）
        y_grid, x_grid = np.ogrid[:height, :width]
        transient_profile = brightness * np.exp(-((x_grid - x)**2 + (y_grid - y)**2) / (2 * 4**2))
        science_data += transient_profile
        print(f"  瞬变源: ({x}, {y}), 亮度: {brightness}")
    
    # 保存科学图像
    sci_path = os.path.join(output_dir, "science_observation.fits")
    hdu = fits.PrimaryHDU(science_data.astype(np.float32))
    hdu.header['OBJECT'] = 'Science Observation'
    hdu.header['TELESCOP'] = 'TEST'
    hdu.header['EXPTIME'] = 300.0
    hdu.header['DATE-OBS'] = '2025-07-23'
    hdu.writeto(sci_path, overwrite=True)
    print(f"科学图像已保存: {sci_path}")
    
    # 输出统计信息
    print(f"\n图像统计:")
    print(f"参考图像: 均值={np.mean(reference_data):.1f}, 标准差={np.std(reference_data):.1f}")
    print(f"科学图像: 均值={np.mean(science_data):.1f}, 标准差={np.std(science_data):.1f}")
    print(f"预期差异: 应该检测到 {len(transient_positions)} 个瞬变源")
    
    return ref_path, sci_path


if __name__ == '__main__':
    print("创建DIA测试数据...")
    ref_file, sci_file = create_test_fits_pair()
    print(f"\n✓ 测试数据创建完成!")
    print(f"参考文件: {ref_file}")
    print(f"科学文件: {sci_file}")
    print(f"\n现在可以运行DIA测试:")
    print(f"python run_dia.py --reference {ref_file} --science {sci_file}")
