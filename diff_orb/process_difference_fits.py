#!/usr/bin/env python3
"""
简化版差异FITS文件处理工具
专门用于处理compare_aligned_fits.py输出的_difference.fits文件
去除黑色坑和背景亮光，输出更干净的差异FITS文件
"""

import os
import sys
import glob
from clean_difference_fits import DifferenceFITSCleaner

def find_difference_fits_files(directory):
    """
    在指定目录中查找_difference.fits文件
    
    Args:
        directory (str): 目录路径
        
    Returns:
        list: 找到的_difference.fits文件列表
    """
    pattern = os.path.join(directory, "*_difference.fits")
    files = glob.glob(pattern)
    return files

def process_single_file(input_file, output_dir=None, config='default'):
    """
    处理单个差异FITS文件
    
    Args:
        input_file (str): 输入文件路径
        output_dir (str): 输出目录
        config (str): 配置类型 ('default', 'strict', 'gentle')
    """
    # 预设配置
    configs = {
        'default': {
            'noise_percentile': 15,
            'noise_multiplier': 4.0,
            'min_component_size': 10,
            'intensity_threshold': 0.05
        },
        'strict': {
            'noise_percentile': 10,
            'noise_multiplier': 5.0,
            'min_component_size': 20,
            'intensity_threshold': 0.08
        },
        'gentle': {
            'noise_percentile': 20,
            'noise_multiplier': 3.0,
            'min_component_size': 5,
            'intensity_threshold': 0.03
        },
        'ultra_gentle': {
            'noise_percentile': 30,
            'noise_multiplier': 2.0,
            'min_component_size': 3,
            'intensity_threshold': 0.01,
            'morphology_kernel_size': 3,
            'gaussian_sigma': 0.5
        },
        'minimal': {
            'noise_percentile': 40,
            'noise_multiplier': 1.5,
            'min_component_size': 1,
            'intensity_threshold': 0.005,
            'morphology_kernel_size': 3,
            'gaussian_sigma': 0.3,
            'median_filter_size': 1
        }
    }
    
    print(f"处理文件: {os.path.basename(input_file)}")
    print(f"使用配置: {config}")
    
    # 创建清理器
    cleaner = DifferenceFITSCleaner()
    
    # 应用配置
    if config in configs:
        for key, value in configs[config].items():
            cleaner.clean_params[key] = value
    
    # 处理文件
    result = cleaner.process_difference_fits(input_file, output_dir)
    
    if result and result['success']:
        stats = result['statistics']
        print(f"  ✓ 处理成功")
        print(f"  原始像素: {stats['original_nonzero_pixels']:,}")
        print(f"  清理后像素: {stats['cleaned_nonzero_pixels']:,}")
        print(f"  减少比例: {stats['reduction_ratio']:.2%}")
        print(f"  输出文件: {os.path.basename(result['cleaned_fits_file'])}")
        return result
    else:
        print(f"  ✗ 处理失败")
        return None

def process_directory(input_dir, output_dir=None, config='default'):
    """
    处理目录中的所有_difference.fits文件
    
    Args:
        input_dir (str): 输入目录
        output_dir (str): 输出目录
        config (str): 配置类型
    """
    # 查找差异文件
    diff_files = find_difference_fits_files(input_dir)
    
    if not diff_files:
        print(f"在目录 {input_dir} 中未找到 *_difference.fits 文件")
        return []
    
    print(f"找到 {len(diff_files)} 个差异FITS文件:")
    for file in diff_files:
        print(f"  - {os.path.basename(file)}")
    
    print("\n开始处理...")
    print("=" * 60)
    
    results = []
    for i, file in enumerate(diff_files, 1):
        print(f"\n[{i}/{len(diff_files)}] ", end="")
        result = process_single_file(file, output_dir, config)
        if result:
            results.append(result)
    
    return results

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='差异FITS文件批量处理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 处理单个文件（默认配置）
  python process_difference_fits.py --input difference.fits
  
  # 处理目录中的所有_difference.fits文件
  python process_difference_fits.py --input-dir results_folder
  
  # 使用严格清理配置
  python process_difference_fits.py --input difference.fits --config strict
  
  # 使用温和清理配置
  python process_difference_fits.py --input difference.fits --config gentle
  
配置说明:
  default      - 默认配置，平衡清理效果和保留信息
  strict       - 严格清理，去除更多噪声，保留更少像素
  gentle       - 温和清理，保留更多信息，去除较少噪声
  ultra_gentle - 超温和清理，最大程度保留原始信息
  minimal      - 最小清理，仅去除最明显的噪声
        """
    )
    
    # 输入选项（互斥）
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--input', '-i',
                           help='输入的_difference.fits文件路径')
    input_group.add_argument('--input-dir', '-d',
                           help='包含_difference.fits文件的输入目录')
    
    parser.add_argument('--output', '-o',
                       help='输出目录（默认在输入文件/目录下自动生成）')
    parser.add_argument('--config', '-c', choices=['default', 'strict', 'gentle', 'ultra_gentle', 'minimal'],
                       default='ultra_gentle',
                       help='清理配置类型（默认: ultra_gentle）')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("差异FITS文件批量处理工具")
    print("=" * 60)
    print(f"清理配置: {args.config}")
    
    try:
        results = []
        
        if args.input:
            # 处理单个文件
            if not os.path.exists(args.input):
                print(f"错误: 输入文件不存在 - {args.input}")
                sys.exit(1)
            
            print(f"输入文件: {args.input}")
            print(f"输出目录: {args.output or '自动生成'}")
            print("=" * 60)
            
            result = process_single_file(args.input, args.output, args.config)
            if result:
                results.append(result)
        
        elif args.input_dir:
            # 处理目录
            if not os.path.exists(args.input_dir):
                print(f"错误: 输入目录不存在 - {args.input_dir}")
                sys.exit(1)
            
            print(f"输入目录: {args.input_dir}")
            print(f"输出目录: {args.output or '自动生成'}")
            print("=" * 60)
            
            results = process_directory(args.input_dir, args.output, args.config)
        
        # 总结
        if results:
            print("\n" + "=" * 60)
            print("处理总结")
            print("=" * 60)
            print(f"成功处理: {len(results)} 个文件")
            
            total_original = sum(r['statistics']['original_nonzero_pixels'] for r in results)
            total_cleaned = sum(r['statistics']['cleaned_nonzero_pixels'] for r in results)
            overall_reduction = (total_original - total_cleaned) / total_original if total_original > 0 else 0
            
            print(f"总原始像素: {total_original:,}")
            print(f"总清理后像素: {total_cleaned:,}")
            print(f"总体减少比例: {overall_reduction:.2%}")
            
            print("\n输出文件:")
            for result in results:
                print(f"  - {os.path.basename(result['cleaned_fits_file'])}")
                print(f"    位置: {result['output_directory']}")
        else:
            print("\n没有成功处理任何文件")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
