"""
星点检测主程序
处理E:\fix_data\star-detect目录下的所有FITS文件
"""

import os
import glob
import time
import json
from pathlib import Path
from star_detector import StarDetector
import logging

def main():
    """主函数"""
    # 设置路径
    input_dir = r"E:\fix_data\star-detect"
    output_dir = "output_images"
    
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
    
    # 初始化星点检测器 - 精选模式（只检测明显星点）
    detector = StarDetector(
        min_area=15,            # 较大的最小面积，只检测明显星点
        max_area=500,           # 适中的最大面积
        threshold_factor=3.5,   # 较高的阈值因子，只检测亮星
        min_circularity=0.5,    # 较高的圆度要求
        min_solidity=0.7,       # 较高的实心度要求
        adaptive_threshold=False, # 使用固定阈值
        dark_star_mode=False    # 关闭暗星模式
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
            result = detector.process_fits_file(fits_file, output_dir)
            
            if result:
                all_results.append(result)
                logger.info(f"成功处理: 检测到 {result['num_stars']} 个星点")
            else:
                logger.error(f"处理失败: {fits_file}")
                
        except Exception as e:
            logger.error(f"处理文件时出错 {fits_file}: {e}")
            continue
    
    # 计算总处理时间
    total_time = time.time() - start_time
    
    # 生成汇总报告
    generate_summary_report(all_results, output_dir, total_time)
    
    logger.info(f"处理完成! 总用时: {total_time:.2f}秒")
    logger.info(f"输出目录: {os.path.abspath(output_dir)}")

def generate_summary_report(results, output_dir, total_time):
    """生成汇总报告"""
    if not results:
        return
    
    # 统计信息
    total_files = len(results)
    total_stars = sum(r['num_stars'] for r in results)
    avg_stars = total_stars / total_files if total_files > 0 else 0
    
    # 创建汇总报告
    summary = {
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
    report_path = os.path.join(output_dir, 'detection_summary.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # 生成文本报告
    text_report_path = os.path.join(output_dir, 'detection_summary.txt')
    with open(text_report_path, 'w', encoding='utf-8') as f:
        f.write("星点检测汇总报告\n")
        f.write("=" * 50 + "\n\n")
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
