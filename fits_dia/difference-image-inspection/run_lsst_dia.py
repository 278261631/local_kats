#!/usr/bin/env python3
"""
LSST DESC Difference-Image-Inspection 命令行接口
用于处理 /fits_dia/test_data 目录下的差异图像文件

Usage:
    python run_lsst_dia.py --input aligned_comparison_20250715_175203_difference.fits
    python run_lsst_dia.py --auto  # 自动处理test_data目录
"""

import os
import sys
import argparse
import glob
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lsst_dia import LSSTDifferenceImageInspection


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
        description='LSST DESC Difference-Image-Inspection - 多尺度差异图像分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 处理指定的差异图像文件
  python run_lsst_dia.py --input aligned_comparison_20250715_175203_difference.fits
  
  # 自动处理test_data目录中的差异图像
  python run_lsst_dia.py --auto
  
  # 指定输出目录和参数
  python run_lsst_dia.py --input diff.fits --output results --threshold 4.0
  
  # 禁用质量评估以加快处理速度
  python run_lsst_dia.py --auto --no-quality --threshold 3.0
        """
    )
    
    # 输入文件参数
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--input', type=str, help='输入差异图像FITS文件路径')
    input_group.add_argument('--auto', action='store_true', help='自动处理test_data目录')
    
    # 其他参数
    parser.add_argument('--output', type=str, help='输出目录路径')
    parser.add_argument('--threshold', type=float, default=5.0, help='检测阈值（默认5.0）')
    parser.add_argument('--no-quality', action='store_true', help='禁用质量评估')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
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
        
    # 创建LSST DIA处理器
    lsst_dia = LSSTDifferenceImageInspection(
        detection_threshold=args.threshold,
        quality_assessment=not args.no_quality
    )
    
    # 执行LSST DIA处理
    print(f"\n开始LSST DESC差异图像检查...")
    print(f"输入文件: {input_fits}")
    print(f"输出目录: {output_dir}")
    print(f"检测阈值: {args.threshold}")
    print(f"质量评估: {'启用' if not args.no_quality else '禁用'}")
    
    result = lsst_dia.process_difference_image(input_fits, output_dir)
    
    if result and result['success']:
        print(f"\n✓ LSST DIA处理成功完成!")
        print(f"检测到源: {result['sources_detected']} 个")
        
        # 显示质量评估结果
        quality_metrics = result['quality_metrics']
        print(f"图像质量评分: {quality_metrics.get('overall_quality', 0):.1f}/100")
        
        # 显示统计验证结果
        validation_results = result['validation_results']
        print(f"统计验证: {'通过' if validation_results.get('validation_passed', False) else '失败'}")
        
        if validation_results.get('warnings'):
            print(f"验证警告: {len(validation_results['warnings'])} 个")
        
        # 显示分类统计
        class_dist = validation_results.get('class_distribution', {})
        if class_dist:
            print(f"\n源分类统计:")
            for class_name, count in sorted(class_dist.items(), key=lambda x: x[1], reverse=True):
                percentage = count / result['sources_detected'] * 100 if result['sources_detected'] > 0 else 0
                print(f"  {class_name:12s}: {count:4d} ({percentage:5.1f}%)")
        
        # 显示最可靠的源
        reliable_sources = [s for s in result['sources'] if s.get('reliability', 0) > 70]
        if reliable_sources:
            print(f"\n高可靠性源 (前5个):")
            for i, source in enumerate(reliable_sources[:5]):
                class_info = source.get('classification', {})
                print(f"  {i+1}: 位置=({source['x']:.1f}, {source['y']:.1f}), "
                      f"SNR={source.get('snr', 0):.1f}, "
                      f"类型={class_info.get('class', 'unknown')}, "
                      f"可靠性={source.get('reliability', 0):.1f}")
        
        print(f"\n输出文件:")
        print(f"  标记FITS文件: {os.path.basename(result['marked_fits'])}")
        print(f"  源目录: {os.path.basename(result['catalog_file'])}")
        print(f"  质量报告: {os.path.basename(result['quality_report'])}")
        print(f"  可视化: {os.path.basename(result['visualization'])}")
        
        # 显示处理摘要
        print(f"\n处理摘要:")
        print(f"  多尺度检测: {len(set(s['scale'] for s in result['sources']))} 个尺度")
        print(f"  聚类数量: {len(set(s.get('cluster_id', -1) for s in result['sources'] if s.get('cluster_id', -1) >= 0))}")
        print(f"  源密度: {validation_results.get('source_density', 0):.1f} 个/百万像素")
        
        return 0
    else:
        print(f"\n✗ LSST DIA处理失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
