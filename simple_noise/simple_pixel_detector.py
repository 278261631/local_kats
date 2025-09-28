#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单高效的单像素噪点检测器
使用简单算法快速检测单像素噪点
"""

import numpy as np
from astropy.io import fits
from scipy import ndimage
import os
import cv2

def detect_outlier_pixels(image, threshold=5.0):
    """
    使用简单的离群值检测方法检测单像素噪点
    
    参数:
    image: 输入图像
    threshold: 阈值（标准差倍数）
    
    返回:
    outlier_mask: 离群像素掩码
    """
    
    print(f"使用离群值检测方法，阈值: {threshold}σ")
    
    # 使用3x3均值滤波计算局部均值
    local_mean = ndimage.uniform_filter(image.astype(np.float64), size=3)
    
    # 计算全局标准差作为噪声水平的估计
    global_std = np.std(image)
    
    # 计算每个像素与局部均值的偏差
    deviation = np.abs(image - local_mean)
    
    # 检测离群像素
    outlier_mask = deviation > (threshold * global_std)
    
    # 排除边界像素
    outlier_mask[0, :] = False
    outlier_mask[-1, :] = False
    outlier_mask[:, 0] = False
    outlier_mask[:, -1] = False
    
    # 过滤掉连通区域，只保留单像素
    outlier_mask = filter_single_pixels_fast(outlier_mask)
    
    outlier_count = np.sum(outlier_mask)
    print(f"检测到 {outlier_count} 个离群像素")
    
    return outlier_mask

def detect_hot_cold_pixels_simple(image, hot_threshold=3.0, cold_threshold=3.0):
    """
    简单的热像素和冷像素检测
    
    参数:
    image: 输入图像
    hot_threshold: 热像素阈值
    cold_threshold: 冷像素阈值
    
    返回:
    hot_mask: 热像素掩码
    cold_mask: 冷像素掩码
    """
    
    print(f"简单热冷像素检测，热阈值: {hot_threshold}σ, 冷阈值: {cold_threshold}σ")
    
    # 使用3x3均值滤波
    local_mean = ndimage.uniform_filter(image.astype(np.float64), size=3)
    
    # 计算全局标准差
    global_std = np.std(image)
    
    # 计算偏差
    deviation = image - local_mean
    
    # 检测热像素（比周围亮很多）
    hot_mask = deviation > (hot_threshold * global_std)
    
    # 检测冷像素（比周围暗很多）
    cold_mask = deviation < -(cold_threshold * global_std)
    
    # 排除边界
    hot_mask[0, :] = hot_mask[-1, :] = hot_mask[:, 0] = hot_mask[:, -1] = False
    cold_mask[0, :] = cold_mask[-1, :] = cold_mask[:, 0] = cold_mask[:, -1] = False
    
    # 过滤单像素
    hot_mask = filter_single_pixels_fast(hot_mask)
    cold_mask = filter_single_pixels_fast(cold_mask)
    
    hot_count = np.sum(hot_mask)
    cold_count = np.sum(cold_mask)
    
    print(f"检测到 {hot_count} 个热像素")
    print(f"检测到 {cold_count} 个冷像素")
    
    return hot_mask, cold_mask

def filter_single_pixels_fast(mask):
    """快速过滤，只保留单像素噪点"""
    
    if not np.any(mask):
        return mask
    
    # 使用形态学腐蚀和膨胀来识别单像素
    kernel = np.ones((3, 3), dtype=bool)
    kernel[1, 1] = False  # 不包括中心像素
    
    # 对每个候选像素检查其8邻域
    result_mask = np.zeros_like(mask)
    candidates = np.where(mask)
    
    for y, x in zip(candidates[0], candidates[1]):
        # 检查3x3邻域
        y_min, y_max = max(0, y-1), min(mask.shape[0], y+2)
        x_min, x_max = max(0, x-1), min(mask.shape[1], x+2)
        
        neighborhood = mask[y_min:y_max, x_min:x_max]
        
        # 如果邻域中只有中心像素为True，则认为是单像素噪点
        center_y, center_x = y - y_min, x - x_min
        if (0 <= center_y < neighborhood.shape[0] and 
            0 <= center_x < neighborhood.shape[1]):
            
            # 临时移除中心像素
            temp_neighborhood = neighborhood.copy()
            temp_neighborhood[center_y, center_x] = False
            
            # 如果邻域中没有其他True像素，则是单像素噪点
            if not np.any(temp_neighborhood):
                result_mask[y, x] = True
    
    return result_mask

def apply_adaptive_median_filter(image, ksize=3):
    """
    应用自适应中值滤波

    参数:
    image: 输入图像
    ksize: 滤波核大小

    返回:
    filtered_image: 滤波后的图像
    """

    print(f"应用自适应中值滤波，核大小: {ksize}")

    # 确保数据是适合OpenCV处理的格式
    if image.dtype == np.uint16:
        # 保持uint16格式
        cv_image = image.copy()
    elif image.dtype == np.float64:
        # 转换为float32以节省内存
        cv_image = image.astype(np.float32)
    else:
        # 其他格式转换为float32
        cv_image = image.astype(np.float32)

    def safe_median_blur(img, ksize):
        """安全的中值滤波，处理不同数据类型和核大小限制"""
        try:
            # 首先尝试直接滤波
            return cv2.medianBlur(img, ksize), img.dtype, "直接处理"
        except cv2.error as e:
            print(f"  直接处理失败: {e}")

            # 如果是uint16且核大小较大，转换为uint8处理
            if img.dtype == np.uint16 and ksize > 5:
                print(f"  uint16大核大小，转换为uint8处理")
                temp_img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                temp_filtered = cv2.medianBlur(temp_img, ksize)
                filtered = temp_filtered.astype(np.float32) * (img.max() - img.min()) / 255.0 + img.min()
                return filtered.astype(img.dtype), img.dtype, "uint16->uint8转换"

            # 对于其他情况，转换为uint8处理
            elif img.dtype != np.uint8:
                print(f"  转换为uint8处理")
                temp_img = cv2.normalize(img.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                temp_filtered = cv2.medianBlur(temp_img, ksize)
                filtered = temp_filtered.astype(np.float32) * (img.max() - img.min()) / 255.0 + img.min()
                return filtered.astype(img.dtype), img.dtype, "转换为uint8"

            else:
                raise e

    try:
        # 尝试使用 adaptiveMedianBlur (如果存在)
        filtered_data = cv2.adaptiveMedianBlur(cv_image, ksize=ksize)
        method = "adaptiveMedianBlur"
        print(f"使用方法: {method}")
    except AttributeError:
        print("adaptiveMedianBlur 不可用，使用标准中值滤波")
        filtered_data, result_dtype, method = safe_median_blur(cv_image, ksize)
        print(f"使用方法: {method}")
    except cv2.error:
        print("adaptiveMedianBlur 失败，使用标准中值滤波")
        filtered_data, result_dtype, method = safe_median_blur(cv_image, ksize)
        print(f"使用方法: {method}")

    return filtered_data

def repair_pixels_simple(image, pixel_mask):
    """
    简单的像素修复方法
    
    参数:
    image: 输入图像
    pixel_mask: 需要修复的像素掩码
    
    返回:
    repaired_image: 修复后的图像
    """
    
    repaired_image = image.copy()
    noise_pixels = np.where(pixel_mask)
    
    if len(noise_pixels[0]) == 0:
        return repaired_image
    
    print(f"修复 {len(noise_pixels[0])} 个像素")
    
    # 使用3x3邻域的均值替换
    for y, x in zip(noise_pixels[0], noise_pixels[1]):
        # 获取3x3邻域
        y_min, y_max = max(0, y-1), min(image.shape[0], y+2)
        x_min, x_max = max(0, x-1), min(image.shape[1], x+2)
        
        # 计算邻域均值（排除中心像素）
        neighborhood = image[y_min:y_max, x_min:x_max]
        mask = np.ones(neighborhood.shape, dtype=bool)
        
        center_y, center_x = y - y_min, x - x_min
        if (0 <= center_y < mask.shape[0] and 
            0 <= center_x < mask.shape[1]):
            mask[center_y, center_x] = False
        
        if np.any(mask):
            repaired_image[y, x] = np.mean(neighborhood[mask])
    
    return repaired_image

def process_fits_simple(input_file, method='outlier', threshold=4.0, output_dir=None):
    """
    简单处理FITS文件中的单像素噪点

    参数:
    input_file: 输入FITS文件
    method: 检测方法 ('outlier', 'hot_cold', 或 'adaptive_median')
    threshold: 检测阈值
    output_dir: 输出目录，如果为None则使用输入文件所在目录
    """
    
    print(f"正在读取FITS文件: {input_file}")
    
    # 读取FITS文件
    with fits.open(input_file) as hdul:
        header = hdul[0].header
        image_data = hdul[0].data.astype(np.float64)
        
        print(f"图像尺寸: {image_data.shape}")
        print(f"数据范围: [{np.min(image_data):.2f}, {np.max(image_data):.2f}]")
        print(f"图像均值: {np.mean(image_data):.2f}")
        print(f"图像标准差: {np.std(image_data):.2f}")
    
    # 处理NaN值
    if np.any(np.isnan(image_data)):
        print("检测到NaN值，将其替换为中位数")
        median_val = np.nanmedian(image_data)
        image_data = np.nan_to_num(image_data, nan=median_val)
    
    print(f"\n开始检测单像素噪点 (方法: {method})...")

    if method == 'outlier':
        # 离群值检测
        noise_mask = detect_outlier_pixels(image_data, threshold)

    elif method == 'hot_cold':
        # 热冷像素检测
        hot_mask, cold_mask = detect_hot_cold_pixels_simple(image_data, threshold, threshold)
        noise_mask = hot_mask | cold_mask

        # 保存热像素和冷像素
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            hot_file = os.path.join(output_dir, f"{base_name}_hot_pixels_simple.fits")
            cold_file = os.path.join(output_dir, f"{base_name}_cold_pixels_simple.fits")
        else:
            hot_file = f"{os.path.splitext(input_file)[0]}_hot_pixels_simple.fits"
            cold_file = f"{os.path.splitext(input_file)[0]}_cold_pixels_simple.fits"

        hot_image = np.zeros_like(image_data)
        hot_image[hot_mask] = image_data[hot_mask]
        fits.writeto(hot_file, hot_image, header=header, overwrite=True)

        cold_image = np.zeros_like(image_data)
        cold_image[cold_mask] = image_data[cold_mask]
        fits.writeto(cold_file, cold_image, header=header, overwrite=True)

        print(f"热像素图像保存为: {hot_file}")
        print(f"冷像素图像保存为: {cold_file}")

    elif method == 'adaptive_median':
        # 自适应中值滤波降噪
        print("使用自适应中值滤波方法")
        ksize = 3  # 使用3x3核
        repaired_image = apply_adaptive_median_filter(image_data, ksize)

        # 计算噪点（原图与滤波后的差异）
        noise_image = image_data - repaired_image

        # 创建噪点掩码（基于差异阈值）
        noise_threshold = np.std(noise_image) * 2.0  # 使用2倍标准差作为阈值
        noise_mask = np.abs(noise_image) > noise_threshold

        # 生成输出文件名
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{base_name}_adaptive_median_filtered.fits")
            noise_file = os.path.join(output_dir, f"{base_name}_adaptive_median_noise.fits")
        else:
            output_file = f"{os.path.splitext(input_file)[0]}_adaptive_median_filtered.fits"
            noise_file = f"{os.path.splitext(input_file)[0]}_adaptive_median_noise.fits"

        # 保存结果
        print(f"\n保存滤波后的图像到: {output_file}")
        fits.writeto(output_file, repaired_image, header=header, overwrite=True)

        print(f"保存噪点图像到: {noise_file}")
        fits.writeto(noise_file, noise_image, header=header, overwrite=True)

        # 显示统计信息
        total_noise_pixels = np.sum(noise_mask)
        print("\n📊 自适应中值滤波结果统计:")
        print(f"总像素数: {image_data.size:,}")
        print(f"检测到的噪点数量: {total_noise_pixels}")
        print(f"噪点占比: {total_noise_pixels / image_data.size * 100:.6f}%")
        print(f"原始图像 - 均值: {np.mean(image_data):.4f}, 标准差: {np.std(image_data):.4f}")
        print(f"滤波图像 - 均值: {np.mean(repaired_image):.4f}, 标准差: {np.std(repaired_image):.4f}")
        print(f"噪点阈值: {noise_threshold:.4f}")

        print(f"\n📁 生成的文件:")
        print(f"  - 滤波后图像: {output_file}")
        print(f"  - 噪点图像: {noise_file}")

        return repaired_image, noise_image, noise_mask

    # 修复噪点（仅对outlier和hot_cold方法）
    print(f"\n开始修复单像素噪点...")
    repaired_image = repair_pixels_simple(image_data, noise_mask)
    
    # 提取噪点
    noise_image = image_data - repaired_image
    
    # 生成输出文件名
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{base_name}_simple_repaired.fits")
        noise_file = os.path.join(output_dir, f"{base_name}_simple_noise.fits")
    else:
        output_file = f"{os.path.splitext(input_file)[0]}_simple_repaired.fits"
        noise_file = f"{os.path.splitext(input_file)[0]}_simple_noise.fits"
    
    # 保存结果
    print(f"\n保存修复后的图像到: {output_file}")
    fits.writeto(output_file, repaired_image, header=header, overwrite=True)
    
    print(f"保存噪点图像到: {noise_file}")
    fits.writeto(noise_file, noise_image, header=header, overwrite=True)
    
    # 显示统计信息
    total_noise_pixels = np.sum(noise_mask)
    
    print("\n📊 处理结果统计:")
    print(f"总像素数: {image_data.size:,}")
    print(f"检测到的噪点数量: {total_noise_pixels}")
    print(f"噪点占比: {total_noise_pixels / image_data.size * 100:.6f}%")
    print(f"原始图像 - 均值: {np.mean(image_data):.4f}, 标准差: {np.std(image_data):.4f}")
    print(f"修复图像 - 均值: {np.mean(repaired_image):.4f}, 标准差: {np.std(repaired_image):.4f}")
    
    if total_noise_pixels > 0:
        noise_values = image_data[noise_mask]
        print(f"噪点像素值范围: [{np.min(noise_values):.2f}, {np.max(noise_values):.2f}]")
        print(f"噪点像素均值: {np.mean(noise_values):.4f}")
        
        # 显示一些噪点像素的位置
        noise_coords = np.where(noise_mask)
        print(f"前10个噪点位置: {list(zip(noise_coords[0][:10], noise_coords[1][:10]))}")
    
    print(f"\n📁 生成的文件:")
    print(f"  - 修复后图像: {output_file}")
    print(f"  - 噪点图像: {noise_file}")
    
    return repaired_image, noise_image, noise_mask

def main():
    # 查找FITS文件
    fits_files = [f for f in os.listdir('.') if f.endswith('.fit') or f.endswith('.fits')]
    
    if not fits_files:
        print("❌ 当前目录下没有找到FITS文件")
        return
    
    input_file = fits_files[0]  # 使用第一个找到的FITS文件
    print(f"🔍 找到FITS文件: {input_file}")
    
    try:
        print("🎯 开始简单单像素噪点检测和修复...")
        
        # 使用离群值检测方法
        print("\n=== 方法1: 离群值检测 ===")
        repaired1, noise1, mask1 = process_fits_simple(
            input_file, method='outlier', threshold=0.8
        )
        
        # 使用热冷像素检测方法
        print("\n=== 方法2: 热冷像素检测 ===")
        repaired2, noise2, mask2 = process_fits_simple(
            input_file, method='hot_cold', threshold=0.8
        )
        
        print(f"\n✅ 所有处理完成!")
        
    except Exception as e:
        print(f"❌ 处理过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
