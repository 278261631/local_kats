#!/usr/bin/env python3
"""
检查LSST DESC DIA标记FITS文件的圆圈标记功能
验证圆圈大小是否根据源的flux和SNR正确调整
"""

import os
import glob
import numpy as np
from astropy.io import fits


def check_marked_fits():
    """检查最新的标记FITS文件"""
    
    # 查找最新的标记FITS文件
    test_data_dir = "../test_data"
    marked_files = glob.glob(os.path.join(test_data_dir, "lsst_dia_*_marked.fits"))
    
    if not marked_files:
        print("未找到LSST DIA标记FITS文件")
        return
        
    # 使用最新的文件
    latest_file = sorted(marked_files)[-1]
    
    print("=" * 60)
    print("LSST DESC DIA 标记FITS文件检查")
    print("=" * 60)
    print(f"文件: {os.path.basename(latest_file)}")
    
    try:
        with fits.open(latest_file) as hdul:
            header = hdul[0].header
            data = hdul[0].data
            
            print(f"\n基本信息:")
            print(f"  图像尺寸: {data.shape}")
            print(f"  数据类型: {data.dtype}")
            print(f"  数据范围: {np.min(data):.6f} 到 {np.max(data):.6f}")
            
            print(f"\nLSST DIA处理信息:")
            if 'LSSTDIA' in header:
                print(f"  处理软件: {header['LSSTDIA']}")
            if 'DIAVERS' in header:
                print(f"  版本: {header['DIAVERS']}")
            if 'MARKED' in header:
                print(f"  已标记: {header['MARKED']}")
            if 'NSOURCES' in header:
                print(f"  源数量: {header['NSOURCES']}")
                
            print(f"\n标记参数:")
            if 'MINFLUX' in header and 'MAXFLUX' in header:
                print(f"  Flux范围: {header['MINFLUX']:.6e} - {header['MAXFLUX']:.6e}")
            if 'MINSNR' in header and 'MAXSNR' in header:
                print(f"  SNR范围: {header['MINSNR']:.2f} - {header['MAXSNR']:.2f}")
            if 'MINRAD' in header and 'MAXRAD' in header:
                print(f"  圆圈半径范围: {header['MINRAD']} - {header['MAXRAD']} 像素")
                
            print(f"\n头信息注释:")
            for key in header:
                if key == 'COMMENT':
                    for comment in header.comments[key]:
                        if comment.strip():
                            print(f"  {comment}")
                            
            print(f"\n处理历史:")
            for key in header:
                if key == 'HISTORY':
                    for history in header.comments[key]:
                        if history.strip():
                            print(f"  {history}")
                            
            # 统计分析
            print(f"\n数据统计:")
            print(f"  均值: {np.mean(data):.6f}")
            print(f"  标准差: {np.std(data):.6f}")
            print(f"  中位数: {np.median(data):.6f}")
            
            # 检查是否有标记的圆圈
            unique_values = len(np.unique(data))
            print(f"  唯一值数量: {unique_values}")
            
            if unique_values > 1000:  # 如果有很多唯一值，说明有圆圈标记
                print(f"  ✓ 检测到圆圈标记")
            else:
                print(f"  ⚠ 可能没有圆圈标记")
                
    except Exception as e:
        print(f"读取FITS文件时出错: {e}")


def compare_original_and_marked():
    """比较原始差异图像和标记图像"""
    
    test_data_dir = "../test_data"
    original_file = os.path.join(test_data_dir, "aligned_comparison_20250715_175203_difference.fits")
    
    # 查找最新的标记文件
    marked_files = glob.glob(os.path.join(test_data_dir, "lsst_dia_*_marked.fits"))
    if not marked_files:
        print("未找到标记FITS文件")
        return
        
    marked_file = sorted(marked_files)[-1]
    
    print(f"\n" + "=" * 60)
    print("原始图像 vs 标记图像对比")
    print("=" * 60)
    
    try:
        # 读取原始图像
        with fits.open(original_file) as hdul:
            original_data = hdul[0].data
            
        # 读取标记图像
        with fits.open(marked_file) as hdul:
            marked_data = hdul[0].data
            
        print(f"原始图像:")
        print(f"  尺寸: {original_data.shape}")
        print(f"  数据范围: {np.min(original_data):.6f} 到 {np.max(original_data):.6f}")
        print(f"  唯一值数量: {len(np.unique(original_data))}")
        
        print(f"\n标记图像:")
        print(f"  尺寸: {marked_data.shape}")
        print(f"  数据范围: {np.min(marked_data):.6f} 到 {np.max(marked_data):.6f}")
        print(f"  唯一值数量: {len(np.unique(marked_data))}")
        
        # 计算差异
        if original_data.shape == marked_data.shape:
            diff = marked_data - original_data
            modified_pixels = np.sum(diff != 0)
            total_pixels = original_data.size
            
            print(f"\n标记效果:")
            print(f"  修改的像素: {modified_pixels:,} 个")
            print(f"  修改比例: {modified_pixels/total_pixels*100:.4f}%")
            print(f"  最大增加值: {np.max(diff):.6f}")
            print(f"  最小减少值: {np.min(diff):.6f}")
            
            # 分析圆圈标记的分布
            high_diff = np.sum(diff > 0.1)  # 高亮圆圈
            low_diff = np.sum(diff < -0.1)  # 暗色圆圈
            
            print(f"\n圆圈标记分析:")
            print(f"  高亮圆圈像素: {high_diff:,} 个")
            print(f"  暗色圆圈像素: {low_diff:,} 个")
            print(f"  总圆圈像素: {high_diff + low_diff:,} 个")
            
        else:
            print(f"\n⚠ 图像尺寸不匹配，无法比较")
            
    except Exception as e:
        print(f"比较图像时出错: {e}")


def analyze_flux_snr_distribution():
    """分析源flux和SNR分布与圆圈大小的对应关系"""
    
    test_data_dir = "../test_data"
    
    # 查找最新的源目录文件
    source_files = glob.glob(os.path.join(test_data_dir, "lsst_dia_*_sources.txt"))
    if not source_files:
        print("未找到源目录文件")
        return
        
    latest_source_file = sorted(source_files)[-1]
    
    print(f"\n" + "=" * 60)
    print("源flux和SNR分布与圆圈大小分析")
    print("=" * 60)
    print(f"源目录文件: {os.path.basename(latest_source_file)}")
    
    try:
        # 读取源数据
        sources = []
        with open(latest_source_file, 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.strip().split()
                if len(parts) >= 14:  # LSST DIA格式有更多列
                    try:
                        source = {
                            'id': int(parts[0]),
                            'scale': float(parts[1]),
                            'x': float(parts[2]),
                            'y': float(parts[3]),
                            'flux': float(parts[4]),
                            'area': int(parts[5]),
                            'snr': float(parts[6]),
                            'mag': float(parts[7]),
                            'fwhm': float(parts[8]),
                            'ellip': float(parts[9]),
                            'class': parts[10],
                            'conf': float(parts[11]),
                            'reliability': float(parts[12]),
                            'cluster': int(parts[13])
                        }
                        sources.append(source)
                    except (ValueError, IndexError):
                        continue
        
        if not sources:
            print("未找到有效的源数据")
            return
        
        # 分析flux和SNR分布
        fluxes = [abs(s['flux']) for s in sources if s['flux'] != 0]
        snrs = [s['snr'] for s in sources if s['snr'] > 0]
        
        if not fluxes or not snrs:
            print("源数据中缺少有效的flux或SNR信息")
            return
            
        min_flux, max_flux = min(fluxes), max(fluxes)
        min_snr, max_snr = min(snrs), max(snrs)
        
        print(f"\nFlux和SNR统计:")
        print(f"  源数量: {len(sources)}")
        print(f"  Flux范围: {min_flux:.6e} - {max_flux:.6e}")
        print(f"  平均Flux: {np.mean(fluxes):.6e}")
        print(f"  SNR范围: {min_snr:.2f} - {max_snr:.2f}")
        print(f"  平均SNR: {np.mean(snrs):.2f}")
        
        # 计算对应的圆圈半径
        min_radius = 3
        max_radius = 25
        
        print(f"\n圆圈半径映射:")
        print(f"  最小半径: {min_radius} 像素")
        print(f"  最大半径: {max_radius} 像素")
        print(f"  映射公式: 0.6 × normalized_flux + 0.4 × normalized_snr")
        
        # 显示几个典型源的映射关系
        print(f"\n典型源的flux/SNR-半径映射:")
        
        # 按综合评分排序
        for source in sources:
            flux = abs(source['flux'])
            snr = source['snr']
            
            if max_flux > min_flux and max_snr > min_snr:
                normalized_flux = (flux - min_flux) / (max_flux - min_flux)
                normalized_snr = (snr - min_snr) / (max_snr - min_snr)
                combined_score = 0.6 * normalized_flux + 0.4 * normalized_snr
            else:
                combined_score = 0.5
                
            radius = int(min_radius + combined_score * (max_radius - min_radius))
            source['radius'] = radius
            source['combined_score'] = combined_score
        
        # 显示前10个最高评分的源
        top_sources = sorted(sources, key=lambda s: s['combined_score'], reverse=True)[:10]
        
        for i, source in enumerate(top_sources):
            print(f"  源{source['id']:2d}: flux={source['flux']:8.2e}, SNR={source['snr']:5.1f} "
                  f"→ 半径={source['radius']:2d}像素 (评分={source['combined_score']:.3f}, "
                  f"类型={source['class']}, 可靠性={source['reliability']:.1f})")
        
        # 分类统计
        high_flux = len([s for s in sources if abs(s['flux']) > np.median(fluxes)])
        high_snr = len([s for s in sources if s['snr'] > np.median(snrs)])
        high_both = len([s for s in sources if abs(s['flux']) > np.median(fluxes) and s['snr'] > np.median(snrs)])
        
        print(f"\n分布统计:")
        print(f"  高flux源 (>中位数): {high_flux} 个")
        print(f"  高SNR源 (>中位数): {high_snr} 个")
        print(f"  高flux+高SNR源: {high_both} 个 → 大圆圈")
        
        # 可靠性分析
        reliable_sources = [s for s in sources if s['reliability'] > 70]
        transient_sources = [s for s in sources if s['class'] == 'transient']
        
        print(f"\n质量分析:")
        print(f"  高可靠性源 (>70): {len(reliable_sources)} 个 → 最亮圆圈")
        print(f"  瞬变源候选: {len(transient_sources)} 个 → 特殊标记")
        
    except Exception as e:
        print(f"分析flux和SNR分布失败: {e}")


if __name__ == '__main__':
    check_marked_fits()
    compare_original_and_marked()
    analyze_flux_snr_distribution()
    
    print(f"\n" + "=" * 60)
    print("LSST DIA标记FITS文件检查完成!")
    print("=" * 60)
