#!/usr/bin/env python3
"""
使用LSST DESC Difference-Image-Inspection方法处理现有的差异图像文件
专门用于处理 aligned_comparison_20250715_175203_difference.fits
"""

import os
import sys
import numpy as np
from lsst_dia import LSSTDifferenceImageInspection


def process_existing_difference():
    """处理现有的差异图像文件"""
    
    # 差异图像文件路径
    difference_file = "../test_data/aligned_comparison_20250715_175203_difference.fits"
    
    if not os.path.exists(difference_file):
        print(f"错误: 差异图像文件不存在: {difference_file}")
        return False
    
    print("=" * 60)
    print("LSST DESC Difference-Image-Inspection - 处理现有差异图像")
    print("=" * 60)
    print(f"输入文件: {os.path.basename(difference_file)}")
    
    # 创建LSST DIA处理器
    lsst_dia = LSSTDifferenceImageInspection(
        detection_threshold=3.0,     # 使用3.0 sigma阈值
        quality_assessment=True      # 启用质量评估
    )
    
    # 处理差异图像
    result = lsst_dia.process_difference_image(difference_file)
    
    if result and result['success']:
        print(f"\n✓ 处理成功!")
        print(f"检测到源: {result['sources_detected']} 个")
        
        # 显示图像质量评估
        quality_metrics = result['quality_metrics']
        print(f"\n图像质量评估:")
        print(f"  综合质量评分: {quality_metrics.get('overall_quality', 0):.1f}/100")
        print(f"  信噪比: {quality_metrics.get('snr', 0):.2f}")
        print(f"  动态范围: {quality_metrics.get('dynamic_range', 0):.2f}")
        print(f"  对比度: {quality_metrics.get('contrast', 0):.4f}")
        print(f"  饱和像素比例: {quality_metrics.get('saturation_fraction', 0):.4f}")
        print(f"  坏像素比例: {quality_metrics.get('bad_pixel_fraction', 0):.4f}")
        print(f"  图像熵: {quality_metrics.get('entropy', 0):.2f}")
        
        # 显示统计验证结果
        validation_results = result['validation_results']
        print(f"\n统计验证:")
        print(f"  验证状态: {'通过' if validation_results.get('validation_passed', False) else '失败'}")
        print(f"  源密度: {validation_results.get('source_density', 0):.1f} 个/百万像素")
        
        warnings = validation_results.get('warnings', [])
        if warnings:
            print(f"  验证警告: {len(warnings)} 个")
            for warning in warnings:
                print(f"    - {warning}")
        
        # 显示分类分布
        class_dist = validation_results.get('class_distribution', {})
        if class_dist:
            print(f"\n源分类分布:")
            total_sources = sum(class_dist.values())
            for class_name, count in sorted(class_dist.items(), key=lambda x: x[1], reverse=True):
                percentage = count / total_sources * 100 if total_sources > 0 else 0
                print(f"  {class_name:12s}: {count:4d} ({percentage:5.1f}%)")
        
        # 显示最可靠的源
        reliable_sources = [s for s in result['sources'] if s.get('reliability', 0) > 50]
        if reliable_sources:
            print(f"\n高可靠性源 (前10个):")
            for i, source in enumerate(reliable_sources[:10]):
                class_info = source.get('classification', {})
                print(f"  {i+1:2d}: 位置=({source['x']:7.1f}, {source['y']:7.1f}), "
                      f"尺度={source['scale']:4.1f}, SNR={source.get('snr', 0):6.2f}, "
                      f"类型={class_info.get('class', 'unknown'):10s}, "
                      f"可靠性={source.get('reliability', 0):5.1f}")
        
        print(f"\n输出文件:")
        print(f"  标记FITS文件: {os.path.basename(result['marked_fits'])}")
        print(f"  源目录: {os.path.basename(result['catalog_file'])}")
        print(f"  质量报告: {os.path.basename(result['quality_report'])}")
        print(f"  可视化: {os.path.basename(result['visualization'])}")

        # 显示标记FITS文件的信息
        print(f"\n标记FITS文件特性:")
        print(f"  圆圈大小根据flux(60%)和SNR(40%)加权决定")
        print(f"  最小圆圈半径: 3 像素")
        print(f"  最大圆圈半径: 25 像素")
        print(f"  高可靠性瞬变源: 最亮圆圈")
        print(f"  正流量源: 高亮圆圈")
        print(f"  负流量源: 暗色圆圈")
        
        # LSST DIA特性说明
        print(f"\nLSST DIA方法特性:")
        print(f"  多尺度检测: 4个尺度 (1.0, 2.0, 4.0, 8.0 像素)")
        print(f"  智能分类: 6种源类型 (瞬变、恒星、星系、宇宙射线、人工制品、噪声)")
        print(f"  质量评估: 7项质量指标")
        print(f"  统计验证: 基于LSST经验的验证框架")
        print(f"  聚类分析: DBSCAN空间聚类")
        print(f"  机器学习: 基于形态学特征的分类")
        
        return True
        
    else:
        print(f"\n✗ 处理失败")
        return False


def analyze_quality_report(report_file):
    """分析质量评估报告"""
    if not os.path.exists(report_file):
        print(f"质量报告文件不存在: {report_file}")
        return
    
    print(f"\n分析质量报告: {os.path.basename(report_file)}")
    print("-" * 40)
    
    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 提取关键信息
        lines = content.split('\n')
        
        print("关键质量指标:")
        for line in lines:
            if any(keyword in line for keyword in ['Overall Quality Score', 'Signal-to-Noise Ratio', 
                                                  'Dynamic Range', 'Validation Status', 'Number of Sources']):
                print(f"  {line.strip()}")
                
        # 查找警告
        warning_section = False
        warnings = []
        for line in lines:
            if 'VALIDATION WARNINGS' in line:
                warning_section = True
                continue
            elif warning_section and line.startswith('- '):
                warnings.append(line.strip())
            elif warning_section and line.strip() == '':
                break
                
        if warnings:
            print(f"\n验证警告:")
            for warning in warnings:
                print(f"  {warning}")
                
    except Exception as e:
        print(f"分析质量报告失败: {e}")


def compare_with_other_methods():
    """与其他方法的结果进行比较"""
    print(f"\n" + "=" * 60)
    print("与其他DIA方法的比较")
    print("=" * 60)
    
    # 查找其他方法的结果文件
    test_data_dir = "../test_data"
    
    # Ryan Oelkers DIA结果
    ryan_files = [f for f in os.listdir(test_data_dir) if f.startswith("ryanoelkers_dia_diff_") and f.endswith("_transients.txt")]
    
    # David Hogg TheThresher结果
    thresher_files = [f for f in os.listdir(test_data_dir) if f.startswith("davidhogg_thresher_") and f.endswith("_sources.txt")]
    
    # LSST DIA结果
    lsst_files = [f for f in os.listdir(test_data_dir) if f.startswith("lsst_dia_") and f.endswith("_sources.txt")]
    
    methods_results = {}
    
    # 统计各方法结果
    if ryan_files:
        ryan_file = os.path.join(test_data_dir, sorted(ryan_files)[-1])
        ryan_count = sum(1 for line in open(ryan_file, 'r') if not line.startswith('#') and line.strip())
        methods_results['Ryan Oelkers DIA'] = ryan_count
    
    if thresher_files:
        thresher_file = os.path.join(test_data_dir, sorted(thresher_files)[-1])
        thresher_count = sum(1 for line in open(thresher_file, 'r') if not line.startswith('#') and line.strip())
        methods_results['David Hogg TheThresher'] = thresher_count
    
    if lsst_files:
        lsst_file = os.path.join(test_data_dir, sorted(lsst_files)[-1])
        lsst_count = sum(1 for line in open(lsst_file, 'r') if not line.startswith('#') and line.strip())
        methods_results['LSST DESC DIA'] = lsst_count
    
    if methods_results:
        print(f"方法比较 (检测源数量):")
        for method, count in methods_results.items():
            print(f"  {method:25s}: {count:6d} 个源")
        
        print(f"\n方法特点对比:")
        print(f"  Ryan Oelkers DIA:")
        print(f"    - 基于信噪比检测")
        print(f"    - DAOStarFinder算法")
        print(f"    - 孔径测光")
        print(f"    - 圆圈标记输出")
        
        print(f"  David Hogg TheThresher:")
        print(f"    - 统计建模方法")
        print(f"    - 贝叶斯推理")
        print(f"    - 自适应阈值")
        print(f"    - 鲁棒估计")
        
        print(f"  LSST DESC DIA:")
        print(f"    - 多尺度分析")
        print(f"    - 智能分类系统")
        print(f"    - 质量评估框架")
        print(f"    - 统计验证")
        print(f"    - 聚类分析")
        print(f"    - 机器学习特征")


if __name__ == '__main__':
    print("LSST DESC Difference-Image-Inspection - 处理现有差异图像")
    
    success = process_existing_difference()
    
    if success:
        # 查找最新的质量报告文件进行分析
        test_data_dir = "../test_data"
        report_files = [f for f in os.listdir(test_data_dir) 
                       if f.startswith("lsst_dia_") and f.endswith("_quality_report.txt")]
        
        if report_files:
            latest_report = sorted(report_files)[-1]
            report_path = os.path.join(test_data_dir, latest_report)
            analyze_quality_report(report_path)
            
        # 与其他方法比较
        compare_with_other_methods()
    
    print(f"\n" + "=" * 60)
    print("LSST DIA处理完成!")
    print("=" * 60)
