#!/usr/bin/env python3
"""
使用Ryan Oelkers DIA方法处理现有的差异图像文件
专门用于处理 aligned_comparison_20250715_175203_difference.fits
"""

import os
import sys
from ryanoelkers_dia import RyanOelkersDIA


def process_existing_difference():
    """处理现有的差异图像文件"""
    
    # 差异图像文件路径
    difference_file = "../test_data/aligned_comparison_20250715_175203_difference.fits"
    
    if not os.path.exists(difference_file):
        print(f"错误: 差异图像文件不存在: {difference_file}")
        return False
    
    print("=" * 60)
    print("Ryan Oelkers DIA - 处理现有差异图像")
    print("=" * 60)
    print(f"输入文件: {os.path.basename(difference_file)}")
    
    # 创建DIA分析器
    dia = RyanOelkersDIA(
        detection_threshold=3.0,  # 使用3.0 sigma阈值
        psf_matching=False        # 差异图像不需要PSF匹配
    )
    
    # 处理差异图像
    result = dia.process_difference_fits(difference_file)
    
    if result and result['success']:
        print(f"\n✓ 处理成功!")
        print(f"检测到瞬变源: {result['transients_detected']} 个")
        
        # 分析检测结果
        positive_flux = [t for t in result['transients'] if t['flux'] > 0]
        negative_flux = [t for t in result['transients'] if t['flux'] < 0]
        high_snr = [t for t in result['transients'] if t['snr'] > 10]
        
        print(f"\n检测统计:")
        print(f"  正流量源: {len(positive_flux)} 个")
        print(f"  负流量源: {len(negative_flux)} 个")
        print(f"  高信噪比源 (SNR>10): {len(high_snr)} 个")
        
        # 显示最亮的几个源
        sorted_sources = sorted(result['transients'], key=lambda x: abs(x['flux']), reverse=True)
        print(f"\n最亮的10个源:")
        for i, source in enumerate(sorted_sources[:10]):
            flux_sign = "+" if source['flux'] > 0 else "-"
            print(f"  {i+1:2d}: 位置=({source['x']:7.1f}, {source['y']:7.1f}), "
                  f"流量={flux_sign}{abs(source['flux']):.2e}, SNR={source['snr']:6.1f}")
        
        print(f"\n输出文件:")
        print(f"  标记FITS文件: {os.path.basename(result['marked_fits'])}")
        print(f"  源目录: {os.path.basename(result['catalog_file'])}")
        print(f"  可视化: {os.path.basename(result['visualization'])}")

        # 显示标记FITS文件的信息
        print(f"\n标记FITS文件特性:")
        print(f"  圆圈大小根据SNR调整")
        print(f"  最小圆圈半径: 3 像素")
        print(f"  最大圆圈半径: 15 像素")
        print(f"  正流量源: 高亮圆圈")
        print(f"  负流量源: 暗色圆圈")
        
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
            if len(parts) >= 8:
                source = {
                    'id': int(parts[0]),
                    'x': float(parts[1]),
                    'y': float(parts[2]),
                    'flux': float(parts[3]),
                    'snr': float(parts[4]),
                    'significance': float(parts[5]),
                    'aperture_flux': float(parts[6]),
                    'aperture_flux_err': float(parts[7])
                }
                sources.append(source)
    
    if not sources:
        print("未找到有效的源数据")
        return
    
    # 统计分析
    import numpy as np
    
    fluxes = [s['flux'] for s in sources]
    snrs = [s['snr'] for s in sources]
    
    print(f"总源数: {len(sources)}")
    print(f"流量范围: {min(fluxes):.3e} 到 {max(fluxes):.3e}")
    print(f"平均流量: {np.mean(fluxes):.3e}")
    print(f"SNR范围: {min(snrs):.1f} 到 {max(snrs):.1f}")
    print(f"平均SNR: {np.mean(snrs):.1f}")
    
    # 流量分布
    positive = [s for s in sources if s['flux'] > 0]
    negative = [s for s in sources if s['flux'] < 0]
    
    print(f"\n流量分布:")
    print(f"  正流量: {len(positive)} 个 ({len(positive)/len(sources)*100:.1f}%)")
    print(f"  负流量: {len(negative)} 个 ({len(negative)/len(sources)*100:.1f}%)")
    
    # SNR分布
    high_snr = [s for s in sources if s['snr'] > 10]
    medium_snr = [s for s in sources if 5 <= s['snr'] <= 10]
    low_snr = [s for s in sources if s['snr'] < 5]
    
    print(f"\nSNR分布:")
    print(f"  高SNR (>10): {len(high_snr)} 个 ({len(high_snr)/len(sources)*100:.1f}%)")
    print(f"  中SNR (5-10): {len(medium_snr)} 个 ({len(medium_snr)/len(sources)*100:.1f}%)")
    print(f"  低SNR (<5): {len(low_snr)} 个 ({len(low_snr)/len(sources)*100:.1f}%)")


if __name__ == '__main__':
    print("Ryan Oelkers DIA - 处理现有差异图像")
    
    success = process_existing_difference()
    
    if success:
        # 查找最新的目录文件进行分析
        test_data_dir = "../test_data"
        catalog_files = [f for f in os.listdir(test_data_dir) 
                        if f.startswith("ryanoelkers_dia_diff_") and f.endswith("_transients.txt")]
        
        if catalog_files:
            latest_catalog = sorted(catalog_files)[-1]
            catalog_path = os.path.join(test_data_dir, latest_catalog)
            analyze_catalog(catalog_path)
    
    print(f"\n" + "=" * 60)
    print("处理完成!")
    print("=" * 60)
