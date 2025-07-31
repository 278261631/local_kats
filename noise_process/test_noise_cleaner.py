#!/usr/bin/env python3
"""
测试孤立噪点清理工具
"""

import os
import sys
from pathlib import Path
from isolated_noise_cleaner import IsolatedNoiseCleaner

def test_noise_cleaner():
    """测试噪点清理工具"""
    
    # 测试文件路径
    test_file = r"E:\fix_data\align-compare\GY5_K053-1_No Filter_60S_Bin2_UTC20250628_193509_-14.9C_.fit"
    
    print("=" * 60)
    print("孤立噪点清理工具测试")
    print("=" * 60)
    print(f"测试文件: {test_file}")
    
    # 检查测试文件是否存在
    if not os.path.exists(test_file):
        print(f"错误: 测试文件不存在: {test_file}")
        return False
    
    # 创建清理器
    cleaner = IsolatedNoiseCleaner()
    
    # 设置参数（针对天文图像优化）
    cleaner.clean_params.update({
        'zscore_threshold': 5.0,        # 提高Z-score阈值，减少误检
        'isolation_radius': 2,          # 减小孤立性检测半径
        'min_neighbors': 1,             # 降低最小邻居数量
        'morphology_kernel_size': 1,    # 减小形态学核大小，保留更多小噪点
        'cleaning_method': 'median',    # 清理方法
        'median_kernel_size': 3,        # 减小中值滤波核大小
        'save_visualization': True,     # 保存可视化结果
        'save_mask': True,             # 保存噪点掩码
    })
    
    print("\n参数设置:")
    for key, value in cleaner.clean_params.items():
        print(f"  {key}: {value}")
    
    print("\n" + "-" * 60)
    print("开始处理...")
    
    # 处理文件
    result = cleaner.process_fits_file(test_file)
    
    if result['success']:
        stats = result['statistics']
        print("\n" + "=" * 60)
        print("处理完成!")
        print("=" * 60)
        print(f"检测到噪点: {stats['noise_count']} 个 ({stats['noise_ratio']:.3f}%)")
        print(f"总像素数: {stats['total_pixels']:,}")
        
        print(f"\n原始图像统计:")
        print(f"  均值: {stats['original_stats']['mean']:.6f}")
        print(f"  中位数: {stats['original_stats']['median']:.6f}")
        print(f"  标准差: {stats['original_stats']['std']:.6f}")
        
        print(f"\n清理后图像统计:")
        print(f"  均值: {stats['cleaned_stats']['mean']:.6f}")
        print(f"  中位数: {stats['cleaned_stats']['median']:.6f}")
        print(f"  标准差: {stats['cleaned_stats']['std']:.6f}")
        
        print(f"\n变化统计:")
        print(f"  最大变化: {stats['changes']['max_change']:.6f}")
        print(f"  平均变化: {stats['changes']['mean_change']:.6f}")
        print(f"  噪点区域平均变化: {stats['changes']['noise_region_change']:.6f}")
        
        print(f"\n输出文件:")
        print(f"  清理后FITS: {result['cleaned_fits_file']}")
        if result['mask_fits_file']:
            print(f"  噪点掩码: {result['mask_fits_file']}")
        if result['visualization_file']:
            print(f"  可视化图: {result['visualization_file']}")
        
        return True
    else:
        print(f"\n处理失败: {result.get('error', '未知错误')}")
        return False

def test_different_methods():
    """测试不同的清理方法"""
    
    test_file = r"E:\fix_data\align-compare\GY5_K053-1_No Filter_60S_Bin2_UTC20250628_193509_-14.9C_.fit"
    
    if not os.path.exists(test_file):
        print(f"错误: 测试文件不存在: {test_file}")
        return
    
    methods = ['median', 'gaussian', 'mean']
    
    print("=" * 60)
    print("测试不同清理方法")
    print("=" * 60)
    
    for method in methods:
        print(f"\n测试方法: {method}")
        print("-" * 40)
        
        cleaner = IsolatedNoiseCleaner()
        cleaner.clean_params['cleaning_method'] = method
        cleaner.clean_params['save_visualization'] = True
        
        # 为不同方法创建不同的输出目录（在程序目录下）
        program_dir = Path(__file__).parent
        test_file_name = Path(test_file).stem
        output_dir = program_dir / f"noise_cleaning_{method}_{test_file_name}"
        
        result = cleaner.process_fits_file(test_file, str(output_dir))
        
        if result['success']:
            stats = result['statistics']
            print(f"  ✓ 成功处理")
            print(f"  检测噪点: {stats['noise_count']} 个")
            print(f"  平均变化: {stats['changes']['mean_change']:.6f}")
            print(f"  输出目录: {output_dir}")
        else:
            print(f"  ✗ 处理失败: {result.get('error', '未知错误')}")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--methods':
        test_different_methods()
    else:
        success = test_noise_cleaner()
        if not success:
            sys.exit(1)
