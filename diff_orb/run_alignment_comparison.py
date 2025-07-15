#!/usr/bin/env python3
"""
FITS图像对齐和差异检测系统启动脚本
便于快速运行图像比较分析
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
import glob

# 设置matplotlib后端，确保图表在独立窗口显示
import matplotlib
matplotlib.use('TkAgg')  # 强制使用TkAgg后端，避免在PyCharm内嵌显示

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fits_alignment_comparison import FITSAlignmentComparison


def find_fits_files(directory):
    """
    在指定目录中查找FITS文件
    
    Args:
        directory (str): 目录路径
        
    Returns:
        list: FITS文件路径列表
    """
    fits_extensions = ['*.fits', '*.fit', '*.fts']
    fits_files = []
    
    for ext in fits_extensions:
        fits_files.extend(glob.glob(os.path.join(directory, ext)))
    
    return sorted(fits_files)


def auto_select_files(directory):
    """
    自动选择目录中的FITS文件

    Args:
        directory (str): 目录路径

    Returns:
        tuple: (文件1路径, 文件2路径) 或 (None, None)
    """
    fits_files = find_fits_files(directory)

    if len(fits_files) < 2:
        print(f"错误: 目录 {directory} 中的FITS文件少于2个")
        return None, None

    print(f"\n在目录 {directory} 中找到以下FITS文件:")
    print("=" * 60)
    for i, file_path in enumerate(fits_files):
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
        print(f"{i+1:2d}. {filename} ({file_size:.1f} MB)")

    if len(fits_files) == 2:
        # 如果只有两个文件，自动选择
        print(f"\n自动选择两个文件进行比较:")
        print(f"参考图像: {os.path.basename(fits_files[0])}")
        print(f"比较图像: {os.path.basename(fits_files[1])}")
        return fits_files[0], fits_files[1]
    else:
        # 如果有多个文件，提供交互式选择
        print(f"\n找到 {len(fits_files)} 个文件，请选择要比较的两个文件:")

        # 选择第一个文件
        while True:
            try:
                choice1 = int(input("选择参考图像 (输入序号): ")) - 1
                if 0 <= choice1 < len(fits_files):
                    break
                else:
                    print("无效选择，请重新输入")
            except ValueError:
                print("请输入有效的数字")

        # 选择第二个文件
        while True:
            try:
                choice2 = int(input("选择待比较图像 (输入序号): ")) - 1
                if 0 <= choice2 < len(fits_files) and choice2 != choice1:
                    break
                elif choice2 == choice1:
                    print("不能选择相同的文件，请重新选择")
                else:
                    print("无效选择，请重新输入")
            except ValueError:
                print("请输入有效的数字")

        return fits_files[choice1], fits_files[choice2]


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='FITS图像对齐和差异检测系统启动脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 使用默认参数（推荐）
  python run_alignment_comparison.py

  # 直接指定两个文件
  python run_alignment_comparison.py file1.fits file2.fits

  # 从目录中交互式选择文件
  python run_alignment_comparison.py --directory E:\\fix_data\\align-compare

  # 指定输出目录
  python run_alignment_comparison.py file1.fits file2.fits --output results

  # 使用完整图像（不使用中央区域优化）
  python run_alignment_comparison.py file1.fits file2.fits --no-central-region

  # 启用图表显示
  python run_alignment_comparison.py file1.fits file2.fits --show-visualization

默认参数:
  --directory "E:\\fix_data\\align-compare"
  --alignment-method rigid
  --no-central-region (使用完整图像)
  --output high_precision_results
  不显示图表，仅保存文件（使用 --show-visualization 启用图表显示）
        """
    )
    
    # 文件输入选项
    parser.add_argument('fits1', nargs='?', help='参考FITS文件路径')
    parser.add_argument('fits2', nargs='?', help='待比较FITS文件路径')
    parser.add_argument('--directory', '-d', default=r'E:\fix_data\align-compare',
                       help='包含FITS文件的目录（交互式选择）')

    # 输出选项
    parser.add_argument('--output', '-o', default='high_precision_results',
                       help='输出目录路径（默认: high_precision_results）')
    parser.add_argument('--show-visualization', action='store_true', help='显示可视化结果（默认不显示，仅保存文件）')

    # 处理选项
    parser.add_argument('--no-central-region', action='store_true', default=True,
                       help='不使用中央区域优化（使用完整图像）')
    parser.add_argument('--region-size', type=int, default=200, help='中央区域大小（默认200像素）')

    # 对齐方法选项
    parser.add_argument('--alignment-method', choices=['rigid', 'similarity', 'homography'],
                       default='rigid', help='图像对齐方法：rigid(刚体变换，推荐), similarity(相似变换), homography(单应性变换)')

    # 高级选项
    parser.add_argument('--gaussian-sigma', type=float, default=1.0, help='高斯模糊参数（默认1.0）')
    parser.add_argument('--diff-threshold', type=float, default=0.1, help='差异检测阈值（默认0.1）')
    parser.add_argument('--orb-features', type=int, default=1000, help='ORB特征点数量（默认1000）')
    parser.add_argument('--fast-threshold', type=int, default=20, help='FAST角点检测阈值（默认20）')
    
    args = parser.parse_args()

    # 确定是否显示可视化（默认不显示，除非明确指定 --show-visualization）
    show_visualization = args.show_visualization

    # 确定输入文件
    if args.directory:
        # 从目录中交互式选择
        if not os.path.exists(args.directory):
            print(f"错误: 目录不存在 - {args.directory}")
            sys.exit(1)
        
        fits1, fits2 = auto_select_files(args.directory)
        if not fits1 or not fits2:
            sys.exit(1)
    else:
        # 直接指定文件
        if not args.fits1 or not args.fits2:
            print("错误: 请指定两个FITS文件或使用 --directory 选项")
            parser.print_help()
            sys.exit(1)
        
        fits1, fits2 = args.fits1, args.fits2
        
        # 检查文件是否存在
        if not os.path.exists(fits1):
            print(f"错误: 文件不存在 - {fits1}")
            sys.exit(1)
        
        if not os.path.exists(fits2):
            print(f"错误: 文件不存在 - {fits2}")
            sys.exit(1)
    
    # 设置输出目录
    if not args.output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"alignment_results_{timestamp}"
    
    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)
    
    # 显示处理信息
    print("\n" + "=" * 60)
    print("FITS图像对齐和差异检测系统")
    print("=" * 60)
    print(f"参考图像: {os.path.basename(fits1)}")
    print(f"比较图像: {os.path.basename(fits2)}")
    print(f"输出目录: {args.output}")
    print(f"中央区域: {'禁用' if args.no_central_region else f'{args.region_size}x{args.region_size}像素'}")
    print(f"对齐方法: {args.alignment_method}")
    print(f"可视化: {'启用' if show_visualization else '禁用（默认）'}")
    print("=" * 60)
    
    # 创建比较系统
    comparator = FITSAlignmentComparison(
        use_central_region=not args.no_central_region,
        central_region_size=args.region_size,
        alignment_method=args.alignment_method
    )
    
    # 更新差异检测参数
    comparator.diff_params['gaussian_sigma'] = args.gaussian_sigma
    comparator.diff_params['diff_threshold'] = args.diff_threshold

    # 更新ORB参数
    comparator.orb_params['nfeatures'] = args.orb_features
    comparator.orb_params['fastThreshold'] = args.fast_threshold
    
    # 执行比较
    try:
        result = comparator.process_fits_comparison(
            fits1,
            fits2,
            output_dir=args.output,
            show_visualization=show_visualization
        )
        
        if result:
            print("\n" + "=" * 60)
            print("处理完成！")
            print("=" * 60)
            print(f"对齐成功: {'是' if result['alignment_success'] else '否'}")
            print(f"特征点检测: 图像1={result['features_detected']['image1']}, "
                  f"图像2={result['features_detected']['image2']}, "
                  f"匹配={result['features_detected']['matches']}")
            print(f"新亮点数量: {result['new_bright_spots']}")
            
            if result['bright_spots_details']:
                print("\n新亮点详情:")
                for i, spot in enumerate(result['bright_spots_details']):
                    print(f"  #{i+1}: 位置{spot['position']}, 面积{spot['area']:.1f}像素")
            
            print(f"\n所有结果已保存到: {args.output}")
            
        else:
            print("处理失败！请检查日志文件了解详细错误信息。")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n用户中断处理")
        sys.exit(1)
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
