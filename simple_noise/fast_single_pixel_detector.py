#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速单像素噪点检测器
高效检测和处理单个像素的异常噪点
"""

import numpy as np
from astropy.io import fits
from scipy import ndimage
import os

def detect_hot_cold_pixels(image, hot_threshold=3.0, cold_threshold=3.0, kernel_size=5):
    """
    快速检测热像素和冷像素（单像素噪点）
    
    参数:
    image: 输入图像
    hot_threshold: 热像素阈值（标准差倍数）
    cold_threshold: 冷像素阈值（标准差倍数）
    kernel_size: 邻域大小
    
    返回:
    hot_pixels: 热像素掩码
    cold_pixels: 冷像素掩码
    """
    
    print(f"检测热像素和冷像素...")
    print(f"热像素阈值: {hot_threshold}σ, 冷像素阈值: {cold_threshold}σ")
    print(f"邻域大小: {kernel_size}x{kernel_size}")
    
    # 计算局部中值
    print("计算局部中值...")
    local_median = ndimage.median_filter(image, size=kernel_size)
    
    # 计算局部标准差（使用MAD估计）
    print("计算局部标准差...")
    local_mad = ndimage.median_filter(np.abs(image - local_median), size=kernel_size)
    local_std = local_mad * 1.4826  # MAD到标准差的转换因子
    
    # 避免除零
    local_std = np.maximum(local_std, 1.0)
    
    # 计算标准化偏差
    deviation = (image - local_median) / local_std
    
    # 检测热像素（异常亮的像素）
    hot_pixels = deviation > hot_threshold
    
    # 检测冷像素（异常暗的像素）
    cold_pixels = deviation < -cold_threshold
    
    # 过滤边界像素
    border = kernel_size // 2
    hot_pixels[:border, :] = False
    hot_pixels[-border:, :] = False
    hot_pixels[:, :border] = False
    hot_pixels[:, -border:] = False
    
    cold_pixels[:border, :] = False
    cold_pixels[-border:, :] = False
    cold_pixels[:, :border] = False
    cold_pixels[:, -border:] = False
    
    # 确保检测到的是单像素噪点
    hot_pixels = filter_single_pixels(hot_pixels)
    cold_pixels = filter_single_pixels(cold_pixels)
    
    hot_count = np.sum(hot_pixels)
    cold_count = np.sum(cold_pixels)
    
    print(f"检测到 {hot_count} 个热像素")
    print(f"检测到 {cold_count} 个冷像素")
    print(f"总计 {hot_count + cold_count} 个单像素噪点")
    
    return hot_pixels, cold_pixels

def filter_single_pixels(mask):
    """过滤掉连通区域，只保留单像素噪点"""
    
    # 标记连通区域
    labeled, num_features = ndimage.label(mask)
    
    # 只保留面积为1的区域（单像素）
    single_pixel_mask = np.zeros_like(mask)
    for i in range(1, num_features + 1):
        region = (labeled == i)
        if np.sum(region) == 1:  # 只有一个像素
            single_pixel_mask |= region
    
    return single_pixel_mask

def repair_pixels(image, pixel_mask, method='median'):
    """
    修复单像素噪点
    
    参数:
    image: 输入图像
    pixel_mask: 需要修复的像素掩码
    method: 修复方法 ('median', 'mean', 'bilinear')
    
    返回:
    repaired_image: 修复后的图像
    """
    
    repaired_image = image.copy()
    noise_pixels = np.where(pixel_mask)
    
    if len(noise_pixels[0]) == 0:
        return repaired_image
    
    print(f"使用 {method} 方法修复 {len(noise_pixels[0])} 个像素")
    
    if method == 'median':
        # 使用3x3邻域的中位数替换
        for y, x in zip(noise_pixels[0], noise_pixels[1]):
            y_min, y_max = max(0, y-1), min(image.shape[0], y+2)
            x_min, x_max = max(0, x-1), min(image.shape[1], x+2)
            
            # 获取邻域（排除中心像素）
            neighborhood = image[y_min:y_max, x_min:x_max]
            mask = np.ones(neighborhood.shape, dtype=bool)
            center_y, center_x = y - y_min, x - x_min
            if 0 <= center_y < mask.shape[0] and 0 <= center_x < mask.shape[1]:
                mask[center_y, center_x] = False
            
            if np.any(mask):
                repaired_image[y, x] = np.median(neighborhood[mask])
                
    elif method == 'mean':
        # 使用3x3邻域的均值替换
        for y, x in zip(noise_pixels[0], noise_pixels[1]):
            y_min, y_max = max(0, y-1), min(image.shape[0], y+2)
            x_min, x_max = max(0, x-1), min(image.shape[1], x+2)
            
            # 获取邻域（排除中心像素）
            neighborhood = image[y_min:y_max, x_min:x_max]
            mask = np.ones(neighborhood.shape, dtype=bool)
            center_y, center_x = y - y_min, x - x_min
            if 0 <= center_y < mask.shape[0] and 0 <= center_x < mask.shape[1]:
                mask[center_y, center_x] = False
            
            if np.any(mask):
                repaired_image[y, x] = np.mean(neighborhood[mask])
                
    elif method == 'bilinear':
        # 使用双线性插值
        repaired_image = bilinear_interpolation_repair(image, pixel_mask)
    
    return repaired_image

def bilinear_interpolation_repair(image, pixel_mask):
    """使用双线性插值修复像素"""
    
    repaired_image = image.copy()
    h, w = image.shape
    
    # 获取需要修复的像素坐标
    noise_y, noise_x = np.where(pixel_mask)
    
    for y, x in zip(noise_y, noise_x):
        # 获取四个最近的有效邻居
        neighbors = []
        weights = []
        
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dy == 0 and dx == 0:
                    continue
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and not pixel_mask[ny, nx]:
                    distance = np.sqrt(dy*dy + dx*dx)
                    neighbors.append(image[ny, nx])
                    weights.append(1.0 / distance)
        
        if neighbors:
            weights = np.array(weights)
            weights /= np.sum(weights)
            repaired_image[y, x] = np.sum(np.array(neighbors) * weights)
    
    return repaired_image

def extract_noise_pixels(original_image, repaired_image):
    """提取噪点像素"""
    
    noise_image = original_image - repaired_image
    return noise_image

def process_fits_single_pixel(input_file, hot_threshold=3.0, cold_threshold=3.0, 
                             kernel_size=5, repair_method='median'):
    """
    处理FITS文件中的单像素噪点
    """
    
    print(f"正在读取FITS文件: {input_file}")
    
    # 读取FITS文件
    with fits.open(input_file) as hdul:
        header = hdul[0].header
        image_data = hdul[0].data.astype(np.float64)
        
        print(f"图像尺寸: {image_data.shape}")
        print(f"数据范围: [{np.min(image_data):.2f}, {np.max(image_data):.2f}]")
    
    # 处理NaN值
    if np.any(np.isnan(image_data)):
        print("检测到NaN值，将其替换为中位数")
        median_val = np.nanmedian(image_data)
        image_data = np.nan_to_num(image_data, nan=median_val)
    
    # 检测单像素噪点
    print("\n开始检测单像素噪点...")
    hot_pixels, cold_pixels = detect_hot_cold_pixels(
        image_data, hot_threshold, cold_threshold, kernel_size
    )
    
    # 合并所有噪点
    all_noise_pixels = hot_pixels | cold_pixels
    
    # 修复噪点
    print(f"\n开始修复单像素噪点...")
    repaired_image = repair_pixels(image_data, all_noise_pixels, method=repair_method)
    
    # 提取噪点
    noise_image = extract_noise_pixels(image_data, repaired_image)
    
    # 生成输出文件名
    base_name = os.path.splitext(input_file)[0]
    output_file = f"{base_name}_single_pixel_repaired.fits"
    noise_file = f"{base_name}_single_pixel_noise_map.fits"
    hot_file = f"{base_name}_hot_pixels.fits"
    cold_file = f"{base_name}_cold_pixels.fits"
    
    # 保存结果
    print(f"\n保存修复后的图像到: {output_file}")
    fits.writeto(output_file, repaired_image, header=header, overwrite=True)
    
    print(f"保存噪点图像到: {noise_file}")
    fits.writeto(noise_file, noise_image, header=header, overwrite=True)
    
    # 保存热像素和冷像素掩码
    hot_mask_image = np.zeros_like(image_data)
    hot_mask_image[hot_pixels] = image_data[hot_pixels]
    fits.writeto(hot_file, hot_mask_image, header=header, overwrite=True)
    
    cold_mask_image = np.zeros_like(image_data)
    cold_mask_image[cold_pixels] = image_data[cold_pixels]
    fits.writeto(cold_file, cold_mask_image, header=header, overwrite=True)
    
    # 显示统计信息
    total_noise_pixels = np.sum(all_noise_pixels)
    hot_count = np.sum(hot_pixels)
    cold_count = np.sum(cold_pixels)
    
    print("\n📊 处理结果统计:")
    print(f"总像素数: {image_data.size:,}")
    print(f"热像素数量: {hot_count}")
    print(f"冷像素数量: {cold_count}")
    print(f"总噪点数量: {total_noise_pixels}")
    print(f"噪点占比: {total_noise_pixels / image_data.size * 100:.6f}%")
    print(f"原始图像 - 均值: {np.mean(image_data):.4f}, 标准差: {np.std(image_data):.4f}")
    print(f"修复图像 - 均值: {np.mean(repaired_image):.4f}, 标准差: {np.std(repaired_image):.4f}")
    
    if total_noise_pixels > 0:
        noise_values = image_data[all_noise_pixels]
        print(f"噪点像素值范围: [{np.min(noise_values):.2f}, {np.max(noise_values):.2f}]")
        print(f"噪点像素均值: {np.mean(noise_values):.4f}")
    
    print(f"\n📁 生成的文件:")
    print(f"  - 修复后图像: {output_file}")
    print(f"  - 噪点图像: {noise_file}")
    print(f"  - 热像素图像: {hot_file}")
    print(f"  - 冷像素图像: {cold_file}")
    
    return repaired_image, noise_image, hot_pixels, cold_pixels

def main():
    # 查找FITS文件
    fits_files = [f for f in os.listdir('.') if f.endswith('.fit') or f.endswith('.fits')]
    
    if not fits_files:
        print("❌ 当前目录下没有找到FITS文件")
        return
    
    input_file = fits_files[0]  # 使用第一个找到的FITS文件
    print(f"🔍 找到FITS文件: {input_file}")
    
    try:
        print("🎯 开始快速单像素噪点检测和修复...")
        repaired, noise, hot_mask, cold_mask = process_fits_single_pixel(
            input_file,
            hot_threshold=3.0,      # 热像素阈值
            cold_threshold=3.0,     # 冷像素阈值
            kernel_size=5,          # 5x5邻域
            repair_method='median'  # 中位数修复
        )
        
        print(f"\n✅ 处理完成!")
        
    except Exception as e:
        print(f"❌ 处理过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
