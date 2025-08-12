#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单像素噪点检测器
专门检测和处理单个像素的异常噪点
"""

import numpy as np
from astropy.io import fits
import matplotlib.pyplot as plt
from scipy import ndimage
from scipy.stats import median_abs_deviation
import os

def detect_single_pixel_noise(image, method='statistical', sensitivity=3.0, 
                             kernel_size=3, min_contrast=100):
    """
    检测单像素噪点
    
    参数:
    image: 输入图像
    method: 检测方法 ('statistical', 'morphological', 'gradient', 'combined')
    sensitivity: 敏感度阈值（标准差倍数）
    kernel_size: 邻域大小
    min_contrast: 最小对比度阈值
    
    返回:
    noise_mask: 噪点掩码
    noise_pixels: 噪点像素坐标
    """
    
    print(f"使用 {method} 方法检测单像素噪点...")
    print(f"敏感度: {sensitivity}, 核大小: {kernel_size}, 最小对比度: {min_contrast}")
    
    if method == 'statistical':
        return _statistical_detection(image, sensitivity, kernel_size)
    elif method == 'morphological':
        return _morphological_detection(image, kernel_size, min_contrast)
    elif method == 'gradient':
        return _gradient_detection(image, sensitivity, kernel_size)
    elif method == 'combined':
        return _combined_detection(image, sensitivity, kernel_size, min_contrast)
    else:
        raise ValueError(f"未知的检测方法: {method}")

def _statistical_detection(image, sensitivity, kernel_size):
    """统计方法：基于局部统计特性检测异常像素"""
    
    # 计算局部均值和标准差
    local_mean = ndimage.uniform_filter(image.astype(np.float64), size=kernel_size)
    local_var = ndimage.uniform_filter(image.astype(np.float64)**2, size=kernel_size) - local_mean**2
    local_std = np.sqrt(np.maximum(local_var, 0))
    
    # 计算每个像素与局部均值的偏差
    deviation = np.abs(image - local_mean)
    
    # 检测异常像素（偏差超过敏感度倍的局部标准差）
    noise_mask = deviation > (sensitivity * local_std)
    
    # 排除边界像素
    border = kernel_size // 2
    noise_mask[:border, :] = False
    noise_mask[-border:, :] = False
    noise_mask[:, :border] = False
    noise_mask[:, -border:] = False
    
    noise_pixels = np.where(noise_mask)
    
    print(f"统计方法检测到 {len(noise_pixels[0])} 个噪点像素")
    return noise_mask, noise_pixels

def _morphological_detection(image, kernel_size, min_contrast):
    """形态学方法：检测孤立的高值或低值像素"""

    # 使用更高效的中值滤波代替形态学运算
    median_filtered = ndimage.median_filter(image, size=kernel_size)

    # 检测与中值滤波结果差异较大的像素
    difference = np.abs(image - median_filtered)
    noise_mask = difference > min_contrast

    # 确保检测到的是单像素噪点
    noise_mask = _filter_single_pixels(noise_mask)

    noise_pixels = np.where(noise_mask)

    print(f"形态学方法检测到 {len(noise_pixels[0])} 个噪点像素")
    return noise_mask, noise_pixels

def _gradient_detection(image, sensitivity, kernel_size):
    """梯度方法：检测梯度异常的像素"""
    
    # 计算梯度
    grad_x = ndimage.sobel(image, axis=1)
    grad_y = ndimage.sobel(image, axis=0)
    gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
    
    # 计算局部梯度统计
    local_grad_mean = ndimage.uniform_filter(gradient_magnitude, size=kernel_size)
    local_grad_std = np.sqrt(
        ndimage.uniform_filter(gradient_magnitude**2, size=kernel_size) - local_grad_mean**2
    )
    
    # 检测梯度异常像素
    noise_mask = gradient_magnitude > (local_grad_mean + sensitivity * local_grad_std)
    
    # 确保检测到的是单像素噪点
    noise_mask = _filter_single_pixels(noise_mask)
    
    noise_pixels = np.where(noise_mask)
    
    print(f"梯度方法检测到 {len(noise_pixels[0])} 个噪点像素")
    return noise_mask, noise_pixels

def _combined_detection(image, sensitivity, kernel_size, min_contrast):
    """组合方法：结合多种检测方法"""
    
    # 获取各种方法的结果
    stat_mask, _ = _statistical_detection(image, sensitivity, kernel_size)
    morph_mask, _ = _morphological_detection(image, kernel_size, min_contrast)
    grad_mask, _ = _gradient_detection(image, sensitivity, kernel_size)
    
    # 投票机制：至少两种方法检测到的像素才认为是噪点
    vote_count = stat_mask.astype(int) + morph_mask.astype(int) + grad_mask.astype(int)
    noise_mask = vote_count >= 2
    
    noise_pixels = np.where(noise_mask)
    
    print(f"组合方法检测到 {len(noise_pixels[0])} 个噪点像素")
    return noise_mask, noise_pixels

def _filter_single_pixels(mask):
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

def remove_single_pixel_noise(image, noise_mask, method='median'):
    """
    移除单像素噪点
    
    参数:
    image: 输入图像
    noise_mask: 噪点掩码
    method: 修复方法 ('median', 'mean', 'interpolation')
    
    返回:
    cleaned_image: 清理后的图像
    """
    
    cleaned_image = image.copy()
    noise_pixels = np.where(noise_mask)
    
    print(f"使用 {method} 方法修复 {len(noise_pixels[0])} 个噪点像素")
    
    if method == 'median':
        # 使用3x3邻域的中位数替换
        for y, x in zip(noise_pixels[0], noise_pixels[1]):
            y_min, y_max = max(0, y-1), min(image.shape[0], y+2)
            x_min, x_max = max(0, x-1), min(image.shape[1], x+2)
            neighborhood = image[y_min:y_max, x_min:x_max]
            # 排除中心像素本身
            neighborhood_flat = neighborhood.flatten()
            center_idx = (y-y_min) * neighborhood.shape[1] + (x-x_min)
            if center_idx < len(neighborhood_flat):
                neighborhood_flat = np.delete(neighborhood_flat, center_idx)
            cleaned_image[y, x] = np.median(neighborhood_flat)
            
    elif method == 'mean':
        # 使用3x3邻域的均值替换
        for y, x in zip(noise_pixels[0], noise_pixels[1]):
            y_min, y_max = max(0, y-1), min(image.shape[0], y+2)
            x_min, x_max = max(0, x-1), min(image.shape[1], x+2)
            neighborhood = image[y_min:y_max, x_min:x_max]
            # 排除中心像素本身
            mask = np.ones(neighborhood.shape, dtype=bool)
            mask[y-y_min, x-x_min] = False
            cleaned_image[y, x] = np.mean(neighborhood[mask])
            
    elif method == 'interpolation':
        # 使用双线性插值
        cleaned_image = _interpolate_noise_pixels(image, noise_mask)
    
    return cleaned_image

def _interpolate_noise_pixels(image, noise_mask):
    """使用插值方法修复噪点像素"""
    
    from scipy.interpolate import griddata
    
    cleaned_image = image.copy()
    h, w = image.shape
    
    # 创建坐标网格
    y_coords, x_coords = np.mgrid[0:h, 0:w]
    
    # 获取非噪点像素的坐标和值
    valid_mask = ~noise_mask
    valid_points = np.column_stack((y_coords[valid_mask], x_coords[valid_mask]))
    valid_values = image[valid_mask]
    
    # 获取需要插值的噪点坐标
    noise_points = np.column_stack((y_coords[noise_mask], x_coords[noise_mask]))
    
    if len(noise_points) > 0 and len(valid_points) > 0:
        # 使用最近邻插值修复噪点
        interpolated_values = griddata(valid_points, valid_values, noise_points, method='nearest')
        cleaned_image[noise_mask] = interpolated_values
    
    return cleaned_image

def extract_single_pixel_noise(image, noise_mask):
    """提取单像素噪点"""
    
    noise_image = np.zeros_like(image)
    noise_image[noise_mask] = image[noise_mask]
    
    return noise_image

def process_fits_single_pixel_noise(input_file, output_file, noise_file, 
                                  method='combined', sensitivity=3.0, 
                                  kernel_size=3, min_contrast=100, 
                                  repair_method='median'):
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
    print("开始检测单像素噪点...")
    noise_mask, noise_pixels = detect_single_pixel_noise(
        image_data, method=method, sensitivity=sensitivity,
        kernel_size=kernel_size, min_contrast=min_contrast
    )
    
    # 移除噪点
    print("开始移除单像素噪点...")
    cleaned_image = remove_single_pixel_noise(image_data, noise_mask, method=repair_method)
    
    # 提取噪点
    noise_image = extract_single_pixel_noise(image_data, noise_mask)
    
    # 保存结果
    print(f"保存清理后的图像到: {output_file}")
    fits.writeto(output_file, cleaned_image, header=header, overwrite=True)
    
    print(f"保存噪点图像到: {noise_file}")
    fits.writeto(noise_file, noise_image, header=header, overwrite=True)
    
    # 显示统计信息
    print("\n处理结果统计:")
    print(f"检测到的单像素噪点数量: {len(noise_pixels[0])}")
    print(f"噪点占总像素的比例: {len(noise_pixels[0]) / image_data.size * 100:.4f}%")
    print(f"原始图像 - 均值: {np.mean(image_data):.4f}, 标准差: {np.std(image_data):.4f}")
    print(f"清理图像 - 均值: {np.mean(cleaned_image):.4f}, 标准差: {np.std(cleaned_image):.4f}")
    
    if len(noise_pixels[0]) > 0:
        noise_values = image_data[noise_mask]
        print(f"噪点像素值范围: [{np.min(noise_values):.2f}, {np.max(noise_values):.2f}]")
        print(f"噪点像素均值: {np.mean(noise_values):.4f}")
    
    return cleaned_image, noise_image, noise_mask

def main():
    # 查找FITS文件
    fits_files = [f for f in os.listdir('.') if f.endswith('.fit') or f.endswith('.fits')]
    
    if not fits_files:
        print("❌ 当前目录下没有找到FITS文件")
        return
    
    input_file = fits_files[0]  # 使用第一个找到的FITS文件
    print(f"🔍 找到FITS文件: {input_file}")
    
    # 生成输出文件名
    base_name = os.path.splitext(input_file)[0]
    output_file = f"{base_name}_single_pixel_cleaned.fits"
    noise_file = f"{base_name}_single_pixel_noise.fits"
    
    try:
        print("🎯 开始单像素噪点检测和处理...")
        cleaned, noise, mask = process_fits_single_pixel_noise(
            input_file, output_file, noise_file,
            method='combined',      # 使用组合方法
            sensitivity=3.0,        # 敏感度
            kernel_size=3,          # 3x3邻域
            min_contrast=200,       # 最小对比度
            repair_method='median'  # 中位数修复
        )
        
        print(f"\n✅ 处理完成!")
        print(f"📁 清理后图像: {output_file}")
        print(f"📁 噪点图像: {noise_file}")
        
    except Exception as e:
        print(f"❌ 处理过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
