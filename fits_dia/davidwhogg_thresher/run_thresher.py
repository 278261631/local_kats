#!/usr/bin/env python3
"""
David Hogg TheThresher 命令行接口
用于处理 /fits_dia/test_data 目录下的差异图像文件

Usage:
    python run_thresher.py --input aligned_comparison_20250715_175203_difference.fits
    python run_thresher.py --auto  # 自动处理test_data目录
"""

import os
import sys
import argparse
import glob
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from thresher import DavidHoggThresher


def find_difference_fits_files(directory):
    """
    在目录中查找差异FITS文件
    
    Args:
        directory (str): 目录路径
        
    Returns:
        list: 差异FITS文件列表
    """
    patterns = ['*difference*.fits', '*diff*.fits', '*.fits']
    fits_files = []
    
    for pattern in patterns:
        files = glob.glob(os.path.join(directory, pattern))
        fits_files.extend(files)
        
    # 去重并排序
    fits_files = sorted(list(set(fits_files)))
    return fits_files


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='David Hogg TheThresher - 统计建模图像处理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 处理指定的差异图像文件
  python run_thresher.py --input aligned_comparison_20250715_175203_difference.fits
  
  # 自动处理test_data目录中的差异图像
  python run_thresher.py --auto
  
  # 指定输出目录和参数
  python run_thresher.py --input diff.fits --output results --threshold 2.5 --bayesian
  
  # 使用简单统计模型
  python run_thresher.py --auto --no-bayesian --threshold 3.0
        """
    )
    
    # 输入文件参数
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--input', type=str, help='输入差异图像FITS文件路径')
    input_group.add_argument('--auto', action='store_true', help='自动处理test_data目录')
    
    # 其他参数
    parser.add_argument('--output', type=str, help='输出目录路径')
    parser.add_argument('--threshold', type=float, default=3.0, help='统计显著性阈值（默认3.0）')
    parser.add_argument('--bayesian', action='store_true', help='使用贝叶斯推理（默认启用）')
    parser.add_argument('--no-bayesian', action='store_true', help='禁用贝叶斯推理，使用简单模型')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 处理互斥参数
    if args.bayesian and args.no_bayesian:
        parser.error("--bayesian 和 --no-bayesian 不能同时使用")
        
    use_bayesian = not args.no_bayesian  # 默认使用贝叶斯推理
    
    # 确定输入文件
    input_fits = None
    
    if args.input:
        # 直接指定文件
        if not os.path.exists(args.input):
            print(f"错误: 输入文件不存在: {args.input}")
            return 1
        input_fits = args.input
        
    elif args.auto:
        # 自动处理test_data目录
        test_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_data')
        
        if not os.path.exists(test_data_dir):
            print(f"错误: test_data目录不存在: {test_data_dir}")
            return 1
            
        fits_files = find_difference_fits_files(test_data_dir)
        if not fits_files:
            print(f"错误: 在test_data目录中未找到FITS文件: {test_data_dir}")
            return 1
            
        # 优先选择包含"difference"的文件
        difference_files = [f for f in fits_files if 'difference' in os.path.basename(f).lower()]
        if difference_files:
            input_fits = difference_files[0]
            print(f"自动选择差异图像: {os.path.basename(input_fits)}")
        else:
            input_fits = fits_files[0]
            print(f"自动选择FITS文件: {os.path.basename(input_fits)}")
            
    if input_fits is None:
        print("错误: 无法确定输入文件")
        return 1
        
    # 设置输出目录
    if args.output:
        output_dir = args.output
    else:
        output_dir = os.path.dirname(input_fits)
        
    # 创建TheThresher处理器
    thresher = DavidHoggThresher(
        significance_threshold=args.threshold,
        use_bayesian_inference=use_bayesian
    )
    
    # 执行TheThresher处理
    print(f"\n开始TheThresher处理...")
    print(f"输入文件: {input_fits}")
    print(f"输出目录: {output_dir}")
    print(f"显著性阈值: {args.threshold}")
    print(f"贝叶斯推理: {'启用' if use_bayesian else '禁用'}")
    
    result = thresher.process_difference_image(input_fits, output_dir)
    
    if result and result['success']:
        print(f"\n✓ TheThresher处理成功完成!")
        print(f"检测到显著源: {result['sources_detected']} 个")
        
        if result['sources']:
            print(f"\n最显著的5个源:")
            for i, source in enumerate(result['sources'][:5]):
                print(f"  {i+1}: 位置=({source['x']:.1f}, {source['y']:.1f}), "
                      f"最大显著性={source['max_significance']:.2f}, "
                      f"面积={source['area']} 像素")
        
        print(f"\n输出文件:")
        print(f"  处理图像: {os.path.basename(result['processed_fits'])}")
        print(f"  显著性图像: {os.path.basename(result['significance_fits'])}")
        print(f"  源目录: {os.path.basename(result['catalog_file'])}")
        print(f"  可视化: {os.path.basename(result['visualization'])}")
        
        # 显示统计信息
        bg_stats = result['background_stats']
        model_params = result['model_params']
        
        print(f"\n背景统计:")
        print(f"  均值: {bg_stats['mean']:.6f}")
        print(f"  标准差: {bg_stats['std']:.6f}")
        print(f"  背景水平: {bg_stats['background_level']:.6f}")
        
        print(f"\n模型参数:")
        print(f"  模型类型: {model_params['type']}")
        if model_params['type'] == 'bayesian':
            print(f"  伽马形状: {model_params['gamma_shape']:.3f}")
            print(f"  伽马尺度: {model_params['gamma_scale']:.3f}")
            print(f"  泊松率: {model_params['poisson_rate']:.3f}")
        else:
            print(f"  阈值: {model_params['threshold']:.6f}")
            
        return 0
    else:
        print(f"\n✗ TheThresher处理失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
