#!/usr/bin/env python3
"""
测试差异FITS文件清理工具
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from astropy.io import fits
from clean_difference_fits import DifferenceFITSCleaner

def test_cleaning_with_different_parameters():
    """测试不同参数的清理效果"""
    
    # 测试文件路径
    test_file = r"E:\github\local_kats\diff_orb\aligned_diff_results_20250715_175200\aligned_comparison_20250715_175203_difference.fits"
    
    if not os.path.exists(test_file):
        print(f"测试文件不存在: {test_file}")
        return
    
    # 加载原始数据
    with fits.open(test_file) as hdul:
        original_data = hdul[0].data.astype(np.float64)
    
    print(f"原始数据统计:")
    print(f"  形状: {original_data.shape}")
    print(f"  非零像素数: {np.sum(original_data > 0):,}")
    print(f"  最大值: {np.max(original_data):.6f}")
    print(f"  平均值: {np.mean(original_data[original_data > 0]):.6f}")
    
    # 测试不同的参数组合
    test_configs = [
        {
            'name': 'minimal',
            'params': {
                'noise_percentile': 40,
                'noise_multiplier': 1.5,
                'min_component_size': 1,
                'intensity_threshold': 0.005,
                'morphology_kernel_size': 3,
                'gaussian_sigma': 0.3,
                'median_filter_size': 1
            }
        },
        {
            'name': 'ultra_gentle',
            'params': {
                'noise_percentile': 30,
                'noise_multiplier': 2.0,
                'min_component_size': 3,
                'intensity_threshold': 0.01,
                'morphology_kernel_size': 3,
                'gaussian_sigma': 0.5
            }
        },
        {
            'name': 'gentle',
            'params': {
                'noise_percentile': 20,
                'noise_multiplier': 3.0,
                'min_component_size': 5,
                'intensity_threshold': 0.03
            }
        },
        {
            'name': 'default',
            'params': {}
        },
        {
            'name': 'strict',
            'params': {
                'noise_percentile': 10,
                'noise_multiplier': 5.0,
                'min_component_size': 20,
                'intensity_threshold': 0.08
            }
        }
    ]
    
    results = []
    
    for config in test_configs:
        print(f"\n测试配置: {config['name']}")
        print("-" * 40)
        
        # 创建清理器
        cleaner = DifferenceFITSCleaner()
        
        # 更新参数
        for key, value in config['params'].items():
            cleaner.clean_params[key] = value
        
        # 执行清理
        cleaned_data = cleaner.advanced_clean_difference(original_data)
        
        # 统计结果
        original_nonzero = np.sum(original_data > 0)
        cleaned_nonzero = np.sum(cleaned_data > 0)
        reduction_ratio = (original_nonzero - cleaned_nonzero) / original_nonzero if original_nonzero > 0 else 0
        
        result = {
            'name': config['name'],
            'params': config['params'],
            'original_nonzero': original_nonzero,
            'cleaned_nonzero': cleaned_nonzero,
            'reduction_ratio': reduction_ratio,
            'original_max': np.max(original_data),
            'cleaned_max': np.max(cleaned_data),
            'cleaned_data': cleaned_data
        }
        
        results.append(result)
        
        print(f"  原始非零像素: {original_nonzero:,}")
        print(f"  清理后非零像素: {cleaned_nonzero:,}")
        print(f"  减少比例: {reduction_ratio:.2%}")
        print(f"  最大强度变化: {np.max(original_data):.6f} -> {np.max(cleaned_data):.6f}")
    
    # 创建对比图
    create_comparison_plot(original_data, results)
    
    return results

def create_comparison_plot(original_data, results):
    """创建对比图"""
    
    n_configs = len(results)
    fig, axes = plt.subplots(2, n_configs + 1, figsize=(4 * (n_configs + 1), 8))
    
    if n_configs == 0:
        return
    
    # 原始图像
    im0 = axes[0, 0].imshow(original_data, cmap='hot', origin='lower')
    axes[0, 0].set_title('原始差异图像')
    axes[0, 0].set_xlabel('X像素')
    axes[0, 0].set_ylabel('Y像素')
    plt.colorbar(im0, ax=axes[0, 0], label='强度')
    
    # 原始图像的直方图
    nonzero_data = original_data[original_data > 0]
    axes[1, 0].hist(nonzero_data, bins=50, alpha=0.7, color='blue')
    axes[1, 0].set_title('原始数据直方图')
    axes[1, 0].set_xlabel('强度')
    axes[1, 0].set_ylabel('频次')
    axes[1, 0].set_yscale('log')
    
    # 各种清理结果
    for i, result in enumerate(results):
        col = i + 1
        cleaned_data = result['cleaned_data']
        
        # 清理后的图像
        im = axes[0, col].imshow(cleaned_data, cmap='hot', origin='lower')
        axes[0, col].set_title(f"{result['name']}\n({result['cleaned_nonzero']:,} 像素)")
        axes[0, col].set_xlabel('X像素')
        axes[0, col].set_ylabel('Y像素')
        plt.colorbar(im, ax=axes[0, col], label='强度')
        
        # 清理后数据的直方图
        if result['cleaned_nonzero'] > 0:
            cleaned_nonzero_data = cleaned_data[cleaned_data > 0]
            axes[1, col].hist(cleaned_nonzero_data, bins=30, alpha=0.7, color='red')
            axes[1, col].set_title(f"清理后直方图\n减少{result['reduction_ratio']:.1%}")
        else:
            axes[1, col].text(0.5, 0.5, '无数据', ha='center', va='center', transform=axes[1, col].transAxes)
            axes[1, col].set_title("清理后直方图\n减少100%")
        
        axes[1, col].set_xlabel('强度')
        axes[1, col].set_ylabel('频次')
        axes[1, col].set_yscale('log')
    
    plt.tight_layout()
    
    # 保存图像
    output_path = "difference_cleaning_comparison.jpg"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n对比图已保存: {output_path}")
    plt.show()

def main():
    """主函数"""
    print("=" * 60)
    print("差异FITS文件清理效果测试")
    print("=" * 60)
    
    try:
        results = test_cleaning_with_different_parameters()
        
        if results:
            print("\n" + "=" * 60)
            print("测试总结")
            print("=" * 60)
            
            for result in results:
                print(f"{result['name']}:")
                print(f"  保留像素: {result['cleaned_nonzero']:,} ({100-result['reduction_ratio']*100:.2f}%)")
                print(f"  最大强度: {result['cleaned_max']:.6f}")
                print()
            
            # 推荐最佳配置
            # 寻找保留像素数在合理范围内的配置
            reasonable_results = [r for r in results if 100 <= r['cleaned_nonzero'] <= 10000]
            
            if reasonable_results:
                best_result = min(reasonable_results, key=lambda x: abs(x['cleaned_nonzero'] - 1000))
                print(f"推荐配置: {best_result['name']}")
                print(f"  保留像素数: {best_result['cleaned_nonzero']:,}")
                print(f"  减少比例: {best_result['reduction_ratio']:.2%}")
            else:
                print("所有配置的结果都不在理想范围内，建议调整参数")
        
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
