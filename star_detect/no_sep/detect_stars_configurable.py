"""
可配置的星点检测主程序
支持多种检测模式，用户可以根据需要选择
"""

import os
import glob
import time
import json
import argparse
from pathlib import Path
from detection_modes import create_detector, get_detector_config, print_all_modes
import logging

def main():
    """主函数"""
    # 命令行参数解析
    parser = argparse.ArgumentParser(description='星点检测程序')

    # 预设模式参数
    parser.add_argument('--mode', '-m',
                       choices=['minimal', 'selective', 'balanced', 'sensitive', 'maximum'],
                       help='检测模式 (与自定义参数互斥)')
    parser.add_argument('--list-modes', '-l', action='store_true',
                       help='显示所有可用的检测模式')

    # 直接检测参数
    parser.add_argument('--min-area', type=int, help='最小星点面积（像素）')
    parser.add_argument('--max-area', type=int, help='最大星点面积（像素）')
    parser.add_argument('--threshold-factor', type=float, help='阈值因子（越大检测越严格）')
    parser.add_argument('--min-circularity', type=float, help='最小圆度 (0-1)')
    parser.add_argument('--min-solidity', type=float, help='最小实心度 (0-1)')
    parser.add_argument('--adaptive-threshold', action='store_true', help='使用自适应阈值')
    parser.add_argument('--dark-star-mode', action='store_true', help='启用暗星检测模式')

    # 可视化样式参数
    parser.add_argument('--circle-thickness', type=int, default=1, help='圆圈线条粗细（像素）')
    parser.add_argument('--circle-size-factor', type=float, default=1.5, help='圆圈大小倍数')

    # 输入输出参数
    parser.add_argument('--input-dir', '-i',
                       default=r"E:\fix_data\star-detect",
                       help='FITS文件输入目录')
    parser.add_argument('--output-dir', '-o',
                       default="output_images",
                       help='输出目录')
    parser.add_argument('--save-marked-fits', action='store_true',
                       help='保存带有星点标记的FITS文件')

    args = parser.parse_args()
    
    # 如果用户要求列出模式，显示后退出
    if args.list_modes:
        print_all_modes()
        return

    # 检查参数冲突
    custom_params = [args.min_area, args.max_area, args.threshold_factor,
                    args.min_circularity, args.min_solidity]
    has_custom_params = any(param is not None for param in custom_params)

    if args.mode and has_custom_params:
        print("错误: 不能同时使用预设模式和自定义参数")
        return

    if not args.mode and not has_custom_params:
        print("错误: 必须指定预设模式或自定义参数")
        print("使用 --help 查看帮助信息")
        return

    # 设置路径
    input_dir = args.input_dir
    output_dir = args.output_dir

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('star_detection.log'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)

    # 初始化星点检测器
    if args.mode:
        # 使用预设模式
        config = get_detector_config(args.mode)
        logger.info(f"使用检测模式: {args.mode.upper()}")
        logger.info(f"模式描述: {config['description']}")
        detector = create_detector(args.mode)
        mode_name = args.mode
    else:
        # 使用自定义参数
        detector_params = {
            'min_area': args.min_area or 5,
            'max_area': args.max_area or 1000,
            'threshold_factor': args.threshold_factor or 3.0,
            'min_circularity': args.min_circularity or 0.4,
            'min_solidity': args.min_solidity or 0.6,
            'adaptive_threshold': args.adaptive_threshold,
            'dark_star_mode': args.dark_star_mode,
            'circle_thickness': args.circle_thickness,
            'circle_size_factor': args.circle_size_factor
        }

        logger.info("使用自定义检测参数:")
        for key, value in detector_params.items():
            logger.info(f"  {key}: {value}")

        from star_detector import StarDetector
        detector = StarDetector(**detector_params)
        mode_name = "custom"
        config = {
            'description': '自定义参数模式',
            **detector_params
        }
    
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
    generate_summary_report(all_results, output_dir, total_time, mode_name, config)
    
    logger.info(f"处理完成! 总用时: {total_time:.2f}秒")
    logger.info(f"输出目录: {os.path.abspath(output_dir)}")

def generate_summary_report(results, output_dir, total_time, mode, config):
    """生成汇总报告"""
    if not results:
        return
    
    # 统计信息
    total_files = len(results)
    total_stars = sum(r['num_stars'] for r in results)
    avg_stars = total_stars / total_files if total_files > 0 else 0
    
    # 创建汇总报告
    summary = {
        'detection_mode': mode,
        'mode_description': config['description'],
        'processing_summary': {
            'total_files_processed': total_files,
            'total_stars_detected': total_stars,
            'average_stars_per_image': round(avg_stars, 2),
            'processing_time_seconds': round(total_time, 2)
        },
        'detection_parameters': {k: v for k, v in config.items() if k != 'description'},
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
    report_path = os.path.join(output_dir, f'detection_summary_{mode}.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # 生成文本报告
    text_report_path = os.path.join(output_dir, f'detection_summary_{mode}.txt')
    with open(text_report_path, 'w', encoding='utf-8') as f:
        f.write(f"星点检测汇总报告 - {mode.upper()} 模式\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"检测模式: {mode.upper()}\n")
        f.write(f"模式描述: {config['description']}\n\n")
        f.write(f"处理文件数量: {total_files}\n")
        f.write(f"检测星点总数: {total_stars}\n")
        f.write(f"平均每图星点数: {avg_stars:.2f}\n")
        f.write(f"总处理时间: {total_time:.2f}秒\n\n")
        
        f.write("检测参数:\n")
        f.write("-" * 20 + "\n")
        params = {k: v for k, v in config.items() if k != 'description'}
        for key, value in params.items():
            f.write(f"  {key}: {value}\n")
        f.write("\n")
        
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
