#!/usr/bin/env python3
"""
FITS图像对齐和差异检测系统使用示例
演示如何使用系统进行图像比较分析
"""

import os
from fits_alignment_comparison import FITSAlignmentComparison

def example_basic_usage():
    """基本使用示例"""
    print("=" * 60)
    print("基本使用示例")
    print("=" * 60)
    
    # 创建比较系统
    comparator = FITSAlignmentComparison(
        use_central_region=True,  # 使用中央区域优化
        central_region_size=200   # 200x200像素区域
    )
    
    # 设置文件路径
    fits_dir = r"E:\fix_data\align-compare"
    fits1 = os.path.join(fits_dir, "GY5_K053-1_No Filter_60S_Bin2_UTC20250622_182433_-14.9C_.fit")
    fits2 = os.path.join(fits_dir, "GY5_K053-1_No Filter_60S_Bin2_UTC20250628_193509_-14.9C_.fit")
    
    # 执行比较
    result = comparator.process_fits_comparison(
        fits1, 
        fits2, 
        output_dir="example_results",
        show_visualization=True
    )
    
    if result:
        print(f"\n处理成功！检测到 {result['new_bright_spots']} 个新亮点")
        return result
    else:
        print("处理失败！")
        return None

def example_high_precision():
    """高精度处理示例（使用完整图像）"""
    print("=" * 60)
    print("高精度处理示例")
    print("=" * 60)
    
    # 创建比较系统（不使用中央区域优化）
    comparator = FITSAlignmentComparison(
        use_central_region=False  # 使用完整图像
    )
    
    # 调整差异检测参数
    comparator.diff_params['diff_threshold'] = 0.05  # 更敏感的阈值
    comparator.diff_params['gaussian_sigma'] = 0.5   # 更少的模糊
    
    # 设置文件路径
    fits_dir = r"E:\fix_data\align-compare"
    fits1 = os.path.join(fits_dir, "GY5_K053-1_No Filter_60S_Bin2_UTC20250622_182433_-14.9C_.fit")
    fits2 = os.path.join(fits_dir, "GY5_K053-1_No Filter_60S_Bin2_UTC20250628_193509_-14.9C_.fit")
    
    # 执行比较
    result = comparator.process_fits_comparison(
        fits1, 
        fits2, 
        output_dir="high_precision_results",
        show_visualization=False  # 不显示可视化以节省时间
    )
    
    if result:
        print(f"\n高精度处理完成！检测到 {result['new_bright_spots']} 个新亮点")
        return result
    else:
        print("高精度处理失败！")
        return None

def example_batch_processing():
    """批处理示例"""
    print("=" * 60)
    print("批处理示例")
    print("=" * 60)
    
    # 创建比较系统
    comparator = FITSAlignmentComparison(
        use_central_region=True,
        central_region_size=200
    )
    
    # 设置文件路径
    fits_dir = r"E:\fix_data\align-compare"
    fits1 = os.path.join(fits_dir, "GY5_K053-1_No Filter_60S_Bin2_UTC20250622_182433_-14.9C_.fit")
    fits2 = os.path.join(fits_dir, "GY5_K053-1_No Filter_60S_Bin2_UTC20250628_193509_-14.9C_.fit")
    
    # 批处理多个参数组合
    parameter_sets = [
        {'diff_threshold': 0.05, 'gaussian_sigma': 0.5, 'name': 'sensitive'},
        {'diff_threshold': 0.1, 'gaussian_sigma': 1.0, 'name': 'normal'},
        {'diff_threshold': 0.2, 'gaussian_sigma': 1.5, 'name': 'conservative'}
    ]
    
    results = []
    for params in parameter_sets:
        print(f"\n处理参数组: {params['name']}")
        
        # 更新参数
        comparator.diff_params['diff_threshold'] = params['diff_threshold']
        comparator.diff_params['gaussian_sigma'] = params['gaussian_sigma']
        
        # 执行比较
        result = comparator.process_fits_comparison(
            fits1, 
            fits2, 
            output_dir=f"batch_results_{params['name']}",
            show_visualization=False
        )
        
        if result:
            results.append({
                'params': params,
                'bright_spots': result['new_bright_spots'],
                'alignment_success': result['alignment_success']
            })
            print(f"  检测到 {result['new_bright_spots']} 个新亮点")
    
    # 总结结果
    print("\n" + "=" * 60)
    print("批处理结果总结")
    print("=" * 60)
    for result in results:
        print(f"{result['params']['name']:12s}: {result['bright_spots']:2d} 个亮点, "
              f"对齐{'成功' if result['alignment_success'] else '失败'}")
    
    return results

def main():
    """主函数"""
    print("FITS图像对齐和差异检测系统 - 使用示例")
    print("=" * 60)
    
    # 检查文件是否存在
    fits_dir = r"E:\fix_data\align-compare"
    if not os.path.exists(fits_dir):
        print(f"错误: 目录不存在 - {fits_dir}")
        return
    
    try:
        # 示例1: 基本使用
        print("\n1. 基本使用示例")
        basic_result = example_basic_usage()
        
        # 示例2: 高精度处理
        print("\n2. 高精度处理示例")
        precision_result = example_high_precision()
        
        # 示例3: 批处理
        print("\n3. 批处理示例")
        batch_results = example_batch_processing()
        
        print("\n" + "=" * 60)
        print("所有示例执行完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"执行示例时出错: {str(e)}")

if __name__ == "__main__":
    main()
