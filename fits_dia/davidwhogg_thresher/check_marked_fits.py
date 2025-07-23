#!/usr/bin/env python3
"""
检查David Hogg TheThresher标记FITS文件的圆圈标记功能
验证圆圈大小是否根据源的AREA正确调整
"""

import os
import glob
import numpy as np
from astropy.io import fits


def check_marked_fits():
    """检查最新的标记FITS文件"""
    
    # 查找最新的标记FITS文件
    test_data_dir = "../test_data"
    marked_files = glob.glob(os.path.join(test_data_dir, "davidhogg_thresher_*_marked.fits"))
    
    if not marked_files:
        print("未找到TheThresher标记FITS文件")
        return
        
    # 使用最新的文件
    latest_file = sorted(marked_files)[-1]
    
    print("=" * 60)
    print("David Hogg TheThresher 标记FITS文件检查")
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
            
            print(f"\nTheThresher处理信息:")
            if 'THRESHER' in header:
                print(f"  处理软件: {header['THRESHER']}")
            if 'THRVERS' in header:
                print(f"  版本: {header['THRVERS']}")
            if 'MARKED' in header:
                print(f"  已标记: {header['MARKED']}")
            if 'NSOURCES' in header:
                print(f"  源数量: {header['NSOURCES']}")
                
            print(f"\n标记参数:")
            if 'MINAREA' in header and 'MAXAREA' in header:
                print(f"  面积范围: {header['MINAREA']} - {header['MAXAREA']} 像素")
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
    marked_files = glob.glob(os.path.join(test_data_dir, "davidhogg_thresher_*_marked.fits"))
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
            print(f"  最小减少值: {np.min(diff):.6f}")
            
            # 分析圆圈标记的分布
            high_diff = np.sum(diff > 0.1)  # 高亮圆圈
            low_diff = np.sum(diff < -0.1)  # 暗色圆圈
            
            print(f"\n圆圈标记分析:")
            print(f"  高亮圆圈像素: {high_diff:,} 个")
            print(f"  暗色圆圈像素: {low_diff:,} 个")
            print(f"  总圆圈像素: {high_diff + low_diff:,} 个")
            
        else:
            print(f"\n⚠ 图像尺寸不匹配，无法比较")
            
    except Exception as e:
        print(f"比较图像时出错: {e}")


def analyze_source_area_distribution():
    """分析源面积分布与圆圈大小的对应关系"""
    
    test_data_dir = "../test_data"
    
    # 查找最新的源目录文件
    source_files = glob.glob(os.path.join(test_data_dir, "davidhogg_thresher_*_sources.txt"))
    if not source_files:
        print("未找到源目录文件")
        return
        
    latest_source_file = sorted(source_files)[-1]
    
    print(f"\n" + "=" * 60)
    print("源面积分布与圆圈大小分析")
    print("=" * 60)
    print(f"源目录文件: {os.path.basename(latest_source_file)}")
    
    try:
        # 读取源数据
        sources = []
        with open(latest_source_file, 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.strip().split()
                if len(parts) >= 7:
                    source = {
                        'id': int(parts[0]),
                        'x': float(parts[1]),
                        'y': float(parts[2]),
                        'max_sig': float(parts[3]),
                        'mean_sig': float(parts[4]),
                        'total_sig': float(parts[5]),
                        'area': int(parts[6])
                    }
                    sources.append(source)
        
        if not sources:
            print("未找到有效的源数据")
            return
        
        # 分析面积分布
        areas = [s['area'] for s in sources]
        min_area = min(areas)
        max_area = max(areas)
        
        print(f"\n面积统计:")
        print(f"  源数量: {len(sources)}")
        print(f"  面积范围: {min_area} - {max_area} 像素")
        print(f"  平均面积: {np.mean(areas):.1f} 像素")
        print(f"  中位数面积: {np.median(areas):.1f} 像素")
        
        # 计算对应的圆圈半径
        min_radius = 3
        max_radius = 20
        
        print(f"\n圆圈半径映射:")
        print(f"  最小半径: {min_radius} 像素 (面积 {min_area})")
        print(f"  最大半径: {max_radius} 像素 (面积 {max_area})")
        
        # 显示几个典型源的映射关系
        print(f"\n典型源的面积-半径映射:")
        for i, source in enumerate(sorted(sources, key=lambda s: s['area'], reverse=True)[:10]):
            area = source['area']
            if max_area > min_area:
                normalized_area = (area - min_area) / (max_area - min_area)
            else:
                normalized_area = 0.5
            radius = int(min_radius + normalized_area * (max_radius - min_radius))
            
            print(f"  源{source['id']:2d}: 面积={area:4d} 像素 → 半径={radius:2d} 像素 "
                  f"(显著性={source['max_sig']:.2f}σ)")
        
        # 面积分布统计
        small_area = len([s for s in sources if s['area'] < 20])
        medium_area = len([s for s in sources if 20 <= s['area'] <= 100])
        large_area = len([s for s in sources if s['area'] > 100])
        
        print(f"\n面积分布:")
        print(f"  小面积源 (<20像素): {small_area} 个 → 小圆圈 (3-6像素半径)")
        print(f"  中面积源 (20-100像素): {medium_area} 个 → 中圆圈 (6-15像素半径)")
        print(f"  大面积源 (>100像素): {large_area} 个 → 大圆圈 (15-20像素半径)")
        
    except Exception as e:
        print(f"分析源面积分布失败: {e}")


if __name__ == '__main__':
    check_marked_fits()
    compare_original_and_marked()
    analyze_source_area_distribution()
    
    print(f"\n" + "=" * 60)
    print("标记FITS文件检查完成!")
    print("=" * 60)
