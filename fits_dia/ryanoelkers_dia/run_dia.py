#!/usr/bin/env python3
"""
Ryan Oelkers DIA 命令行接口
用于处理 /fits_dia/test_data 目录下的FITS文件

Usage:
    python run_dia.py --reference ref.fits --science sci.fits
    python run_dia.py --auto  # 自动处理test_data目录
    python run_dia.py --directory /path/to/fits/files
"""

import os
import sys
import argparse
import glob
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ryanoelkers_dia import RyanOelkersDIA


def find_fits_files(directory):
    """
    在目录中查找FITS文件
    
    Args:
        directory (str): 目录路径
        
    Returns:
        list: FITS文件列表
    """
    fits_patterns = ['*.fits', '*.fit', '*.fts']
    fits_files = []
    
    for pattern in fits_patterns:
        fits_files.extend(glob.glob(os.path.join(directory, pattern)))
        
    return sorted(fits_files)


def auto_select_files(fits_files):
    """
    自动选择参考图像和科学图像
    
    Args:
        fits_files (list): FITS文件列表
        
    Returns:
        tuple: (参考图像路径, 科学图像路径)
    """
    if len(fits_files) < 2:
        print(f"错误: 需要至少2个FITS文件，但只找到 {len(fits_files)} 个")
        return None, None
        
    # 简单策略：使用第一个作为参考，第二个作为科学图像
    # 实际应用中可能需要更复杂的选择逻辑
    reference = fits_files[0]
    science = fits_files[1]
    
    print(f"自动选择:")
    print(f"  参考图像: {os.path.basename(reference)}")
    print(f"  科学图像: {os.path.basename(science)}")
    
    return reference, science


def interactive_select_files(fits_files):
    """
    交互式选择FITS文件
    
    Args:
        fits_files (list): FITS文件列表
        
    Returns:
        tuple: (参考图像路径, 科学图像路径)
    """
    if len(fits_files) < 2:
        print(f"错误: 需要至少2个FITS文件，但只找到 {len(fits_files)} 个")
        return None, None
        
    print("\n可用的FITS文件:")
    for i, fits_file in enumerate(fits_files):
        print(f"  {i+1}: {os.path.basename(fits_file)}")
        
    try:
        # 选择参考图像
        while True:
            ref_idx = input(f"\n请选择参考图像 (1-{len(fits_files)}): ").strip()
            try:
                ref_idx = int(ref_idx) - 1
                if 0 <= ref_idx < len(fits_files):
                    break
                else:
                    print("无效选择，请重试")
            except ValueError:
                print("请输入数字")
                
        # 选择科学图像
        while True:
            sci_idx = input(f"请选择科学图像 (1-{len(fits_files)}): ").strip()
            try:
                sci_idx = int(sci_idx) - 1
                if 0 <= sci_idx < len(fits_files):
                    if sci_idx != ref_idx:
                        break
                    else:
                        print("科学图像不能与参考图像相同，请重新选择")
                else:
                    print("无效选择，请重试")
            except ValueError:
                print("请输入数字")
                
        reference = fits_files[ref_idx]
        science = fits_files[sci_idx]
        
        print(f"\n已选择:")
        print(f"  参考图像: {os.path.basename(reference)}")
        print(f"  科学图像: {os.path.basename(science)}")
        
        return reference, science
        
    except KeyboardInterrupt:
        print("\n\n用户取消操作")
        return None, None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Ryan Oelkers DIA - 差异图像分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 指定参考和科学图像
  python run_dia.py --reference template.fits --science new_image.fits

  # 直接处理差异图像
  python run_dia.py --difference aligned_comparison_20250715_175203_difference.fits

  # 自动处理test_data目录
  python run_dia.py --auto

  # 交互式选择目录中的文件
  python run_dia.py --directory /path/to/fits/files --interactive

  # 指定输出目录和检测阈值
  python run_dia.py --difference diff.fits --output results --threshold 3.0
        """
    )
    
    # 文件选择参数
    file_group = parser.add_mutually_exclusive_group(required=True)
    file_group.add_argument('--reference', type=str, help='参考图像FITS文件路径')
    file_group.add_argument('--auto', action='store_true', help='自动处理test_data目录')
    file_group.add_argument('--directory', type=str, help='包含FITS文件的目录路径')
    file_group.add_argument('--difference', type=str, help='直接处理差异图像FITS文件')
    
    # 其他参数
    parser.add_argument('--science', type=str, help='科学图像FITS文件路径（与--reference一起使用）')
    parser.add_argument('--output', type=str, help='输出目录路径')
    parser.add_argument('--interactive', action='store_true', help='交互式选择文件')
    parser.add_argument('--threshold', type=float, default=5.0, help='检测阈值（sigma倍数，默认5.0）')
    parser.add_argument('--no-psf-matching', action='store_true', help='禁用PSF匹配')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 验证参数
    if args.reference and not args.science:
        parser.error("使用--reference时必须同时指定--science")
        
    # 确定FITS文件
    reference_fits = None
    science_fits = None
    
    if args.reference and args.science:
        # 直接指定文件
        reference_fits = args.reference
        science_fits = args.science
        
        if not os.path.exists(reference_fits):
            print(f"错误: 参考图像文件不存在: {reference_fits}")
            return 1
            
        if not os.path.exists(science_fits):
            print(f"错误: 科学图像文件不存在: {science_fits}")
            return 1
            
    elif args.auto:
        # 自动处理test_data目录
        test_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_data')
        
        if not os.path.exists(test_data_dir):
            print(f"错误: test_data目录不存在: {test_data_dir}")
            return 1
            
        fits_files = find_fits_files(test_data_dir)
        if not fits_files:
            print(f"错误: 在test_data目录中未找到FITS文件: {test_data_dir}")
            return 1
            
        reference_fits, science_fits = auto_select_files(fits_files)
        
    elif args.directory:
        # 处理指定目录
        if not os.path.exists(args.directory):
            print(f"错误: 目录不存在: {args.directory}")
            return 1
            
        fits_files = find_fits_files(args.directory)
        if not fits_files:
            print(f"错误: 在目录中未找到FITS文件: {args.directory}")
            return 1
            
        if args.interactive:
            reference_fits, science_fits = interactive_select_files(fits_files)
        else:
            reference_fits, science_fits = auto_select_files(fits_files)

    elif args.difference:
        # 直接处理差异图像
        if not os.path.exists(args.difference):
            print(f"错误: 差异图像文件不存在: {args.difference}")
            return 1

        difference_fits = args.difference
        reference_fits = None
        science_fits = None

    if not args.difference and (reference_fits is None or science_fits is None):
        print("错误: 无法确定输入文件")
        return 1
        
    # 设置输出目录
    if args.output:
        output_dir = args.output
    else:
        if args.difference:
            output_dir = os.path.dirname(args.difference)
        else:
            output_dir = os.path.dirname(science_fits)
        
    # 创建DIA分析器
    dia = RyanOelkersDIA(
        detection_threshold=args.threshold,
        psf_matching=not args.no_psf_matching
    )
    
    # 执行DIA处理
    print(f"\n开始DIA处理...")

    if args.difference:
        print(f"差异图像: {args.difference}")
        print(f"输出目录: {output_dir}")
        print(f"检测阈值: {args.threshold} sigma")
        print(f"处理模式: 差异图像分析")

        result = dia.process_difference_fits(args.difference, output_dir)
    else:
        print(f"参考图像: {reference_fits}")
        print(f"科学图像: {science_fits}")
        print(f"输出目录: {output_dir}")
        print(f"检测阈值: {args.threshold} sigma")
        print(f"PSF匹配: {'启用' if not args.no_psf_matching else '禁用'}")

        result = dia.process_dia(reference_fits, science_fits, output_dir)
    
    if result and result['success']:
        print(f"\n✓ DIA处理成功完成!")
        print(f"检测到瞬变源: {result['transients_detected']} 个")
        print(f"输出文件:")
        if result.get('processing_mode') == 'difference_only':
            print(f"  输入差异图像: {result['difference_fits']}")
        else:
            print(f"  差异图像: {result['difference_fits']}")
        print(f"  标记FITS文件: {result['marked_fits']}")
        print(f"  源目录: {result['catalog_file']}")
        print(f"  可视化: {result['visualization']}")
        return 0
    else:
        print(f"\n✗ DIA处理失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
