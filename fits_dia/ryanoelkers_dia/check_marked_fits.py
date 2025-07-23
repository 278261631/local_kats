#!/usr/bin/env python3
"""
检查标记FITS文件的头信息和统计
"""

import os
import glob
import numpy as np
from astropy.io import fits


def check_marked_fits():
    """检查最新的标记FITS文件"""
    
    # 查找最新的标记FITS文件
    test_data_dir = "../test_data"
    marked_files = glob.glob(os.path.join(test_data_dir, "*_marked.fits"))
    
    if not marked_files:
        print("未找到标记FITS文件")
        return
        
    # 使用最新的文件
    latest_file = sorted(marked_files)[-1]
    
    print("=" * 60)
    print("标记FITS文件检查")
    print("=" * 60)
    print(f"文件: {os.path.basename(latest_file)}")
    
    try:
        with fits.open(latest_file) as hdul:
            header = hdul[0].header
            data = hdul[0].data
            
            print(f"\n基本信息:")
            print(f"  图像尺寸: {data.shape}")
            print(f"  数据类型: {data.dtype}")
            print(f"  数据范围: {np.min(data):.6f} 到 {np.max(data):.6f}")
            
            print(f"\nDIA处理信息:")
            if 'DIASOFT' in header:
                print(f"  处理软件: {header['DIASOFT']}")
            if 'DIAVERS' in header:
                print(f"  版本: {header['DIAVERS']}")
            if 'MARKED' in header:
                print(f"  已标记: {header['MARKED']}")
            if 'NSOURCES' in header:
                print(f"  源数量: {header['NSOURCES']}")
                
            print(f"\n标记参数:")
            if 'MINSNR' in header and 'MAXSNR' in header:
                print(f"  SNR范围: {header['MINSNR']:.1f} - {header['MAXSNR']:.1f}")
            if 'MINRAD' in header and 'MAXRAD' in header:
                print(f"  圆圈半径范围: {header['MINRAD']} - {header['MAXRAD']} 像素")
                
            print(f"\n头信息注释:")
            for key in header:
                if key == 'COMMENT':
                    for comment in header.comments[key]:
                        if comment.strip():
                            print(f"  {comment}")
                            
            print(f"\n处理历史:")
            for key in header:
                if key == 'HISTORY':
                    for history in header.comments[key]:
                        if history.strip():
                            print(f"  {history}")
                            
            # 统计分析
            print(f"\n数据统计:")
            print(f"  均值: {np.mean(data):.6f}")
            print(f"  标准差: {np.std(data):.6f}")
            print(f"  中位数: {np.median(data):.6f}")
            
            # 检查是否有标记的圆圈
            unique_values = len(np.unique(data))
            print(f"  唯一值数量: {unique_values}")
            
            if unique_values > 1000:  # 如果有很多唯一值，说明有圆圈标记
                print(f"  ✓ 检测到圆圈标记")
            else:
                print(f"  ⚠ 可能没有圆圈标记")
                
    except Exception as e:
        print(f"读取FITS文件时出错: {e}")


def compare_original_and_marked():
    """比较原始差异图像和标记图像"""
    
    test_data_dir = "../test_data"
    original_file = os.path.join(test_data_dir, "aligned_comparison_20250715_175203_difference.fits")
    
    # 查找最新的标记文件
    marked_files = glob.glob(os.path.join(test_data_dir, "*_marked.fits"))
    if not marked_files:
        print("未找到标记FITS文件")
        return
        
    marked_file = sorted(marked_files)[-1]
    
    print(f"\n" + "=" * 60)
    print("原始图像 vs 标记图像对比")
    print("=" * 60)
    
    try:
        # 读取原始图像
        with fits.open(original_file) as hdul:
            original_data = hdul[0].data
            
        # 读取标记图像
        with fits.open(marked_file) as hdul:
            marked_data = hdul[0].data
            
        print(f"原始图像:")
        print(f"  尺寸: {original_data.shape}")
        print(f"  数据范围: {np.min(original_data):.6f} 到 {np.max(original_data):.6f}")
        print(f"  唯一值数量: {len(np.unique(original_data))}")
        
        print(f"\n标记图像:")
        print(f"  尺寸: {marked_data.shape}")
        print(f"  数据范围: {np.min(marked_data):.6f} 到 {np.max(marked_data):.6f}")
        print(f"  唯一值数量: {len(np.unique(marked_data))}")
        
        # 计算差异
        if original_data.shape == marked_data.shape:
            diff = marked_data - original_data
            modified_pixels = np.sum(diff != 0)
            total_pixels = original_data.size
            
            print(f"\n标记效果:")
            print(f"  修改的像素: {modified_pixels:,} 个")
            print(f"  修改比例: {modified_pixels/total_pixels*100:.4f}%")
            print(f"  最大增加值: {np.max(diff):.6f}")
            print(f"  最大减少值: {np.min(diff):.6f}")
        else:
            print(f"\n⚠ 图像尺寸不匹配，无法比较")
            
    except Exception as e:
        print(f"比较图像时出错: {e}")


if __name__ == '__main__':
    check_marked_fits()
    compare_original_and_marked()
    
    print(f"\n" + "=" * 60)
    print("检查完成!")
    print("=" * 60)
