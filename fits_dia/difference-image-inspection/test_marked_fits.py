#!/usr/bin/env python3
"""
测试LSST DIA标记FITS文件功能
创建模拟源数据来测试圆圈标记功能
"""

import os
import numpy as np
from astropy.io import fits
from lsst_dia import LSSTDifferenceImageInspection


def create_mock_sources():
    """创建模拟源数据用于测试"""
    
    # 创建一些模拟源，包含不同的flux和SNR值
    mock_sources = [
        {
            'id': 1, 'scale': 2.0, 'x': 100.5, 'y': 150.3,
            'flux': 1.5e-3, 'area': 25, 'snr': 8.5, 'magnitude': 22.1,
            'fwhm': 3.2, 'ellipticity': 0.15, 'orientation': 45.0,
            'background': 0.001, 'reliability': 85.2,
            'classification': {'class': 'transient', 'confidence': 0.8, 'subclass': 'candidate'}
        },
        {
            'id': 2, 'scale': 1.0, 'x': 200.8, 'y': 250.1,
            'flux': 2.8e-3, 'area': 45, 'snr': 12.3, 'magnitude': 21.5,
            'fwhm': 4.1, 'ellipticity': 0.25, 'orientation': 120.0,
            'background': 0.0015, 'reliability': 92.1,
            'classification': {'class': 'star', 'confidence': 0.9, 'subclass': 'point_source'}
        },
        {
            'id': 3, 'scale': 4.0, 'x': 300.2, 'y': 100.7,
            'flux': -1.2e-3, 'area': 15, 'snr': 5.8, 'magnitude': 23.2,
            'fwhm': 2.8, 'ellipticity': 0.35, 'orientation': 80.0,
            'background': 0.0008, 'reliability': 45.3,
            'classification': {'class': 'artifact', 'confidence': 0.6, 'subclass': 'elongated'}
        },
        {
            'id': 4, 'scale': 2.0, 'x': 400.1, 'y': 350.9,
            'flux': 3.5e-3, 'area': 65, 'snr': 15.7, 'magnitude': 20.8,
            'fwhm': 5.2, 'ellipticity': 0.12, 'orientation': 30.0,
            'background': 0.002, 'reliability': 95.8,
            'classification': {'class': 'transient', 'confidence': 0.95, 'subclass': 'candidate'}
        },
        {
            'id': 5, 'scale': 1.0, 'x': 150.6, 'y': 300.4,
            'flux': 0.8e-3, 'area': 8, 'snr': 3.2, 'magnitude': 24.1,
            'fwhm': 2.1, 'ellipticity': 0.45, 'orientation': 160.0,
            'background': 0.0005, 'reliability': 25.7,
            'classification': {'class': 'noise', 'confidence': 0.4, 'subclass': 'low_snr'}
        }
    ]
    
    return mock_sources


def test_marked_fits_creation():
    """测试标记FITS文件创建功能"""
    
    print("=" * 60)
    print("测试LSST DIA标记FITS文件创建")
    print("=" * 60)
    
    # 加载原始差异图像
    difference_file = "../test_data/aligned_comparison_20250715_175203_difference.fits"
    
    if not os.path.exists(difference_file):
        print(f"错误: 差异图像文件不存在: {difference_file}")
        return False
    
    try:
        # 读取原始图像
        with fits.open(difference_file) as hdul:
            image_data = hdul[0].data.astype(np.float64)
            header = hdul[0].header
        
        print(f"原始图像尺寸: {image_data.shape}")
        print(f"数据范围: {np.min(image_data):.6f} 到 {np.max(image_data):.6f}")
        
        # 创建模拟源数据
        mock_sources = create_mock_sources()
        print(f"创建了 {len(mock_sources)} 个模拟源")
        
        # 创建LSST DIA实例
        lsst_dia = LSSTDifferenceImageInspection(
            detection_threshold=3.0,
            quality_assessment=True
        )
        
        # 测试标记FITS文件创建
        output_path = "../test_data/lsst_dia_test_marked.fits"
        lsst_dia.create_marked_fits(image_data, mock_sources, output_path)
        
        # 验证输出文件
        if os.path.exists(output_path):
            with fits.open(output_path) as hdul:
                marked_data = hdul[0].data
                marked_header = hdul[0].header
                
            print(f"\n✓ 标记FITS文件创建成功!")
            print(f"输出文件: {os.path.basename(output_path)}")
            print(f"标记图像尺寸: {marked_data.shape}")
            print(f"标记数据范围: {np.min(marked_data):.6f} 到 {np.max(marked_data):.6f}")
            
            # 检查头信息
            print(f"\n头信息:")
            for key in ['NSOURCES', 'MINFLUX', 'MAXFLUX', 'MINSNR', 'MAXSNR', 'MINRAD', 'MAXRAD']:
                if key in marked_header:
                    print(f"  {key}: {marked_header[key]}")
            
            # 分析标记效果
            diff = marked_data - image_data
            modified_pixels = np.sum(diff != 0)
            total_pixels = image_data.size
            
            print(f"\n标记效果:")
            print(f"  修改像素: {modified_pixels:,} 个 ({modified_pixels/total_pixels*100:.4f}%)")
            print(f"  最大增加: {np.max(diff):.6f}")
            print(f"  最小减少: {np.min(diff):.6f}")
            
            # 显示源信息和对应的圆圈大小
            print(f"\n源信息和圆圈大小:")
            fluxes = [abs(s['flux']) for s in mock_sources if s['flux'] != 0]
            snrs = [s['snr'] for s in mock_sources if s['snr'] > 0]
            min_flux, max_flux = min(fluxes), max(fluxes)
            min_snr, max_snr = min(snrs), max(snrs)
            
            for source in mock_sources:
                flux = abs(source['flux'])
                snr = source['snr']
                
                # 计算圆圈半径（与实际算法相同）
                if max_flux > min_flux and max_snr > min_snr:
                    normalized_flux = (flux - min_flux) / (max_flux - min_flux)
                    normalized_snr = (snr - min_snr) / (max_snr - min_snr)
                    combined_score = 0.6 * normalized_flux + 0.4 * normalized_snr
                else:
                    combined_score = 0.5
                
                radius = int(3 + combined_score * (25 - 3))
                
                print(f"  源{source['id']}: flux={source['flux']:8.2e}, SNR={snr:5.1f} "
                      f"→ 半径={radius:2d}px (类型={source['classification']['class']}, "
                      f"可靠性={source['reliability']:.1f})")
            
            return True
            
        else:
            print(f"\n✗ 标记FITS文件创建失败")
            return False
            
    except Exception as e:
        print(f"测试过程中出错: {e}")
        return False


if __name__ == '__main__':
    success = test_marked_fits_creation()
    
    if success:
        print(f"\n" + "=" * 60)
        print("✓ 测试成功! LSST DIA标记FITS文件功能正常工作")
        print("=" * 60)
        
        print(f"\n可以运行以下命令查看详细分析:")
        print(f"python check_marked_fits.py")
    else:
        print(f"\n" + "=" * 60)
        print("✗ 测试失败")
        print("=" * 60)
