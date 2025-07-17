"""
直接参数星点检测程序
所有检测参数都可以直接通过命令行传入
"""

import os
import glob
import time
import json
import argparse
from pathlib import Path
from star_detector import StarDetector
import logging

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='星点检测程序 - 直接参数模式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基本使用
  python detect_stars_direct.py --min-area 10 --max-area 500 --threshold-factor 3.0

  # 检测较少星点
  python detect_stars_direct.py --min-area 20 --threshold-factor 4.0 --min-circularity 0.6

  # 检测更多星点
  python detect_stars_direct.py --min-area 5 --threshold-factor 2.0 --adaptive-threshold

  # 暗星检测
  python detect_stars_direct.py --min-area 3 --threshold-factor 1.5 --dark-star-mode --adaptive-threshold
        """)
    
    # 必需参数
    parser.add_argument('--min-area', type=int, required=True,
                       help='最小星点面积（像素）')
    parser.add_argument('--max-area', type=int, default=1000,
                       help='最大星点面积（像素，默认: 1000）')
    parser.add_argument('--threshold-factor', type=float, required=True,
                       help='阈值因子（越大检测越严格）')
    
    # 可选参数
    parser.add_argument('--min-circularity', type=float, default=0.4,
                       help='最小圆度 (0-1，默认: 0.4)')
    parser.add_argument('--min-solidity', type=float, default=0.6,
                       help='最小实心度 (0-1，默认: 0.6)')
    parser.add_argument('--adaptive-threshold', action='store_true',
                       help='使用自适应阈值')
    parser.add_argument('--dark-star-mode', action='store_true',
                       help='启用暗星检测模式')

    # 可视化样式参数
    parser.add_argument('--circle-thickness', type=int, default=1,
                       help='圆圈线条粗细（像素，默认: 1）')
    parser.add_argument('--circle-size-factor', type=float, default=1.5,
                       help='圆圈大小倍数（默认: 1.5）')

    # 输入输出参数
    parser.add_argument('--input-dir', '-i', 
                       default=r"E:\fix_data\star-detect",
                       help='FITS文件输入目录')
    parser.add_argument('--output-dir', '-o',
                       default="output_images",
                       help='输出目录')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='显示详细信息')
    parser.add_argument('--save-marked-fits', action='store_true',
                       help='保存带有星点标记的FITS文件')
    
    args = parser.parse_args()
    
    # 参数验证
    if args.min_area <= 0:
        print("错误: min-area 必须大于 0")
        return
    if args.max_area <= args.min_area:
        print("错误: max-area 必须大于 min-area")
        return
    if not (0 < args.min_circularity <= 1):
        print("错误: min-circularity 必须在 0-1 之间")
        return
    if not (0 < args.min_solidity <= 1):
        print("错误: min-solidity 必须在 0-1 之间")
        return
    if args.threshold_factor <= 0:
        print("错误: threshold-factor 必须大于 0")
        return
    
    # 设置路径
    input_dir = args.input_dir
    output_dir = args.output_dir
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 设置日志
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('star_detection.log'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    
    # 显示检测参数
    logger.info("星点检测参数:")
    logger.info(f"  最小面积: {args.min_area} 像素")
    logger.info(f"  最大面积: {args.max_area} 像素")
    logger.info(f"  阈值因子: {args.threshold_factor}")
    logger.info(f"  最小圆度: {args.min_circularity}")
    logger.info(f"  最小实心度: {args.min_solidity}")
    logger.info(f"  自适应阈值: {'是' if args.adaptive_threshold else '否'}")
    logger.info(f"  暗星模式: {'是' if args.dark_star_mode else '否'}")
    logger.info(f"  圆圈粗细: {args.circle_thickness} 像素")
    logger.info(f"  圆圈大小倍数: {args.circle_size_factor}")

    # 初始化星点检测器
    detector = StarDetector(
        min_area=args.min_area,
        max_area=args.max_area,
        threshold_factor=args.threshold_factor,
        min_circularity=args.min_circularity,
        min_solidity=args.min_solidity,
        adaptive_threshold=args.adaptive_threshold,
        dark_star_mode=args.dark_star_mode,
        circle_thickness=args.circle_thickness,
        circle_size_factor=args.circle_size_factor
    )
    
    # 查找所有FITS文件
    fits_pattern = os.path.join(input_dir, "*.fits")
    fits_files = glob.glob(fits_pattern)
    
    if not fits_files:
        logger.error(f"在目录 {input_dir} 中未找到FITS文件")
        return
    
    logger.info(f"找到 {len(fits_files)} 个FITS文件")
    
    # 处理结果存储
    all_results = []
    
    # 处理每个FITS文件
    start_time = time.time()
    
    for i, fits_file in enumerate(fits_files, 1):
        logger.info(f"处理文件 {i}/{len(fits_files)}: {os.path.basename(fits_file)}")
        
        try:
            # 处理文件
            result = detector.process_fits_file(fits_file, output_dir, save_marked_fits=args.save_marked_fits)

            if result:
                all_results.append(result)
                logger.info(f"成功处理: 检测到 {result['num_stars']} 个星点")
                if args.save_marked_fits and result['output_fits']:
                    logger.info(f"标记FITS文件: {result['output_fits']}")
            else:
                logger.error(f"处理失败: {fits_file}")

        except Exception as e:
            logger.error(f"处理文件时出错 {fits_file}: {e}")
            continue
    
    # 计算总处理时间
    total_time = time.time() - start_time
    
    # 生成汇总报告
    generate_summary_report(all_results, output_dir, total_time, args)
    
    logger.info(f"处理完成! 总用时: {total_time:.2f}秒")
    logger.info(f"输出目录: {os.path.abspath(output_dir)}")

def generate_summary_report(results, output_dir, total_time, args):
    """生成汇总报告"""
    if not results:
        return
    
    # 统计信息
    total_files = len(results)
    total_stars = sum(r['num_stars'] for r in results)
    avg_stars = total_stars / total_files if total_files > 0 else 0
    
    # 创建汇总报告
    summary = {
        'detection_mode': 'custom',
        'detection_parameters': {
            'min_area': args.min_area,
            'max_area': args.max_area,
            'threshold_factor': args.threshold_factor,
            'min_circularity': args.min_circularity,
            'min_solidity': args.min_solidity,
            'adaptive_threshold': args.adaptive_threshold,
            'dark_star_mode': args.dark_star_mode
        },
        'processing_summary': {
            'total_files_processed': total_files,
            'total_stars_detected': total_stars,
            'average_stars_per_image': round(avg_stars, 2),
            'processing_time_seconds': round(total_time, 2)
        },
        'file_details': []
    }
    
    # 添加每个文件的详细信息
    for result in results:
        # 转换numpy类型为Python原生类型以支持JSON序列化
        image_stats = {
            'mean': float(result['image_stats']['mean']),
            'median': float(result['image_stats']['median']),
            'std': float(result['image_stats']['std'])
        }
        
        file_detail = {
            'fits_file': os.path.basename(result['fits_file']),
            'output_image': os.path.basename(result['output_image']),
            'num_stars': result['num_stars'],
            'image_stats': image_stats
        }
        summary['file_details'].append(file_detail)
    
    # 保存JSON报告
    report_path = os.path.join(output_dir, 'detection_summary_custom.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # 生成文本报告
    text_report_path = os.path.join(output_dir, 'detection_summary_custom.txt')
    with open(text_report_path, 'w', encoding='utf-8') as f:
        f.write("星点检测汇总报告 - 自定义参数模式\n")
        f.write("=" * 60 + "\n\n")
        
        f.write("检测参数:\n")
        f.write("-" * 20 + "\n")
        f.write(f"  最小面积: {args.min_area} 像素\n")
        f.write(f"  最大面积: {args.max_area} 像素\n")
        f.write(f"  阈值因子: {args.threshold_factor}\n")
        f.write(f"  最小圆度: {args.min_circularity}\n")
        f.write(f"  最小实心度: {args.min_solidity}\n")
        f.write(f"  自适应阈值: {'是' if args.adaptive_threshold else '否'}\n")
        f.write(f"  暗星模式: {'是' if args.dark_star_mode else '否'}\n\n")
        
        f.write(f"处理文件数量: {total_files}\n")
        f.write(f"检测星点总数: {total_stars}\n")
        f.write(f"平均每图星点数: {avg_stars:.2f}\n")
        f.write(f"总处理时间: {total_time:.2f}秒\n\n")
        
        f.write("详细结果:\n")
        f.write("-" * 30 + "\n")
        for result in results:
            f.write(f"文件: {os.path.basename(result['fits_file'])}\n")
            f.write(f"  输出图像: {os.path.basename(result['output_image'])}\n")
            f.write(f"  检测星点: {result['num_stars']}个\n")
            f.write(f"  图像统计: mean={result['image_stats']['mean']:.2f}, "
                   f"median={result['image_stats']['median']:.2f}, "
                   f"std={result['image_stats']['std']:.2f}\n\n")
    
    print(f"\n汇总报告已生成:")
    print(f"  JSON报告: {report_path}")
    print(f"  文本报告: {text_report_path}")

if __name__ == "__main__":
    main()
