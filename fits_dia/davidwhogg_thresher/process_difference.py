#!/usr/bin/env python3
"""
使用David Hogg TheThresher方法处理现有的差异图像文件
专门用于处理 aligned_comparison_20250715_175203_difference.fits
"""

import os
import sys
import numpy as np
from thresher import DavidHoggThresher


def process_existing_difference():
    """处理现有的差异图像文件"""
    
    # 差异图像文件路径
    difference_file = "../test_data/aligned_comparison_20250715_175203_difference.fits"
    
    if not os.path.exists(difference_file):
        print(f"错误: 差异图像文件不存在: {difference_file}")
        return False
    
    print("=" * 60)
    print("David Hogg TheThresher - 处理现有差异图像")
    print("=" * 60)
    print(f"输入文件: {os.path.basename(difference_file)}")
    
    # 创建TheThresher处理器
    thresher = DavidHoggThresher(
        significance_threshold=3.0,     # 使用3.0 sigma阈值
        use_bayesian_inference=True     # 启用贝叶斯推理
    )
    
    # 处理差异图像
    result = thresher.process_difference_image(difference_file)
    
    if result and result['success']:
        print(f"\n✓ 处理成功!")
        print(f"检测到显著源: {result['sources_detected']} 个")
        
        # 分析检测结果
        sources = result['sources']
        if sources:
            # 按显著性分类
            high_sig = [s for s in sources if s['max_significance'] > 10]
            medium_sig = [s for s in sources if 5 <= s['max_significance'] <= 10]
            low_sig = [s for s in sources if s['max_significance'] < 5]
            
            # 按面积分类
            large_area = [s for s in sources if s['area'] > 100]
            medium_area = [s for s in sources if 20 <= s['area'] <= 100]
            small_area = [s for s in sources if s['area'] < 20]
            
            print(f"\n检测统计:")
            print(f"  高显著性源 (>10σ): {len(high_sig)} 个")
            print(f"  中显著性源 (5-10σ): {len(medium_sig)} 个")
            print(f"  低显著性源 (<5σ): {len(low_sig)} 个")
            
            print(f"\n面积分布:")
            print(f"  大面积源 (>100像素): {len(large_area)} 个")
            print(f"  中面积源 (20-100像素): {len(medium_area)} 个")
            print(f"  小面积源 (<20像素): {len(small_area)} 个")
            
            # 显示最显著的源
            print(f"\n最显著的10个源:")
            for i, source in enumerate(sources[:10]):
                print(f"  {i+1:2d}: 位置=({source['x']:7.1f}, {source['y']:7.1f}), "
                      f"最大显著性={source['max_significance']:6.2f}, "
                      f"平均显著性={source['mean_significance']:6.2f}, "
                      f"面积={source['area']:4d} 像素")
        
        # 显示背景统计
        bg_stats = result['background_stats']
        print(f"\n背景统计分析:")
        print(f"  均值: {bg_stats['mean']:.6f}")
        print(f"  中位数: {bg_stats['median']:.6f}")
        print(f"  标准差: {bg_stats['std']:.6f}")
        print(f"  MAD标准差: {bg_stats['mad']:.6f}")
        print(f"  背景水平: {bg_stats['background_level']:.6f}")
        print(f"  偏度: {bg_stats['skewness']:.3f}")
        print(f"  峰度: {bg_stats['kurtosis']:.3f}")
        
        # 显示模型参数
        model_params = result['model_params']
        print(f"\n统计模型:")
        print(f"  模型类型: {model_params['type']}")
        if model_params['type'] == 'bayesian':
            print(f"  伽马形状参数: {model_params['gamma_shape']:.3f}")
            print(f"  伽马尺度参数: {model_params['gamma_scale']:.3f}")
            print(f"  泊松率参数: {model_params['poisson_rate']:.3f}")
            print(f"  对数似然: {model_params['log_likelihood']:.1f}")
        else:
            print(f"  检测阈值: {model_params['threshold']:.6f}")
        
        print(f"\n输出文件:")
        print(f"  处理图像: {os.path.basename(result['processed_fits'])}")
        print(f"  显著性图像: {os.path.basename(result['significance_fits'])}")
        print(f"  源目录: {os.path.basename(result['catalog_file'])}")
        print(f"  可视化: {os.path.basename(result['visualization'])}")
        
        # TheThresher特性说明
        print(f"\nTheThresher方法特性:")
        print(f"  统计建模: 泊松-伽马混合模型")
        print(f"  贝叶斯推理: {'启用' if thresher.use_bayesian_inference else '禁用'}")
        print(f"  自适应阈值: 基于统计显著性")
        print(f"  鲁棒估计: 对噪声和异常值鲁棒")
        print(f"  形态学处理: 去噪和区域连接")
        
        return True
        
    else:
        print(f"\n✗ 处理失败")
        return False


def analyze_catalog(catalog_file):
    """分析源目录文件"""
    if not os.path.exists(catalog_file):
        print(f"目录文件不存在: {catalog_file}")
        return
    
    print(f"\n分析源目录: {os.path.basename(catalog_file)}")
    print("-" * 40)
    
    sources = []
    with open(catalog_file, 'r') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) >= 7:
                source = {
                    'id': int(parts[0]),
                    'x': float(parts[1]),
                    'y': float(parts[2]),
                    'max_sig': float(parts[3]),
                    'mean_sig': float(parts[4]),
                    'total_sig': float(parts[5]),
                    'area': int(parts[6])
                }
                sources.append(source)
    
    if not sources:
        print("未找到有效的源数据")
        return
    
    # 统计分析
    max_sigs = [s['max_sig'] for s in sources]
    mean_sigs = [s['mean_sig'] for s in sources]
    areas = [s['area'] for s in sources]
    
    print(f"总源数: {len(sources)}")
    print(f"最大显著性范围: {min(max_sigs):.2f} 到 {max(max_sigs):.2f}")
    print(f"平均最大显著性: {np.mean(max_sigs):.2f}")
    print(f"面积范围: {min(areas)} 到 {max(areas)} 像素")
    print(f"平均面积: {np.mean(areas):.1f} 像素")
    
    # 显著性分布
    very_high = len([s for s in sources if s['max_sig'] > 12])
    high = len([s for s in sources if 8 <= s['max_sig'] <= 12])
    medium = len([s for s in sources if 5 <= s['max_sig'] < 8])
    low = len([s for s in sources if s['max_sig'] < 5])
    
    print(f"\n显著性分布:")
    print(f"  极高显著性 (>12σ): {very_high} 个 ({very_high/len(sources)*100:.1f}%)")
    print(f"  高显著性 (8-12σ): {high} 个 ({high/len(sources)*100:.1f}%)")
    print(f"  中显著性 (5-8σ): {medium} 个 ({medium/len(sources)*100:.1f}%)")
    print(f"  低显著性 (<5σ): {low} 个 ({low/len(sources)*100:.1f}%)")


def compare_with_other_methods():
    """与其他方法的结果进行比较"""
    print(f"\n" + "=" * 60)
    print("与其他DIA方法的比较")
    print("=" * 60)
    
    # 查找其他方法的结果文件
    test_data_dir = "../test_data"
    
    # Ryan Oelkers DIA结果
    ryan_files = [f for f in os.listdir(test_data_dir) if f.startswith("ryanoelkers_dia_diff_") and f.endswith("_transients.txt")]
    
    # TheThresher结果
    thresher_files = [f for f in os.listdir(test_data_dir) if f.startswith("davidhogg_thresher_") and f.endswith("_sources.txt")]
    
    if ryan_files and thresher_files:
        ryan_file = os.path.join(test_data_dir, sorted(ryan_files)[-1])
        thresher_file = os.path.join(test_data_dir, sorted(thresher_files)[-1])
        
        # 统计Ryan Oelkers结果
        ryan_count = 0
        with open(ryan_file, 'r') as f:
            for line in f:
                if not line.startswith('#') and line.strip():
                    ryan_count += 1
        
        # 统计TheThresher结果
        thresher_count = 0
        with open(thresher_file, 'r') as f:
            for line in f:
                if not line.startswith('#') and line.strip():
                    thresher_count += 1
        
        print(f"方法比较:")
        print(f"  Ryan Oelkers DIA: {ryan_count} 个瞬变源")
        print(f"  David Hogg TheThresher: {thresher_count} 个显著源")
        print(f"  检测比例: {thresher_count/ryan_count*100:.1f}% (TheThresher/Ryan)")
        
        print(f"\n方法特点:")
        print(f"  Ryan Oelkers DIA:")
        print(f"    - 基于信噪比检测")
        print(f"    - DAOStarFinder算法")
        print(f"    - 孔径测光")
        print(f"  David Hogg TheThresher:")
        print(f"    - 统计建模方法")
        print(f"    - 贝叶斯推理")
        print(f"    - 自适应阈值")


if __name__ == '__main__':
    print("David Hogg TheThresher - 处理现有差异图像")
    
    success = process_existing_difference()
    
    if success:
        # 查找最新的目录文件进行分析
        test_data_dir = "../test_data"
        catalog_files = [f for f in os.listdir(test_data_dir) 
                        if f.startswith("davidhogg_thresher_") and f.endswith("_sources.txt")]
        
        if catalog_files:
            latest_catalog = sorted(catalog_files)[-1]
            catalog_path = os.path.join(test_data_dir, latest_catalog)
            analyze_catalog(catalog_path)
            
        # 与其他方法比较
        compare_with_other_methods()
    
    print(f"\n" + "=" * 60)
    print("TheThresher处理完成!")
    print("=" * 60)
