"""
基于信号强度的斑点检测器
可以过滤掉背景噪声，只检测强信号
"""

import cv2
import numpy as np
from astropy.io import fits
import os
import sys
import argparse
from datetime import datetime
from PIL import Image


class SignalBlobDetector:
    """基于信号强度的斑点检测器"""

    def __init__(self, sigma_threshold=5.0, min_area=2, max_area=36, min_circularity=0.79, gamma=2.2, max_jaggedness_ratio=1.2):
        """
        初始化检测器

        Args:
            sigma_threshold: 信号阈值（背景噪声的多少倍标准差）
            min_area: 最小面积
            max_area: 最大面积
            min_circularity: 最小圆度，默认0.79
            gamma: 伽马校正值
            max_jaggedness_ratio: 最大锯齿比率（poly顶点数/hull顶点数），默认1.2
        """
        self.sigma_threshold = sigma_threshold
        self.min_area = min_area
        self.max_area = max_area
        self.min_circularity = min_circularity
        self.gamma = gamma
        self.max_jaggedness_ratio = max_jaggedness_ratio
        
    def load_fits_image(self, fits_path):
        """加载 FITS 文件"""
        try:
            print(f"\n加载 FITS 文件: {fits_path}")
            
            with fits.open(fits_path) as hdul:
                data = hdul[0].data
                header = hdul[0].header
                
                if data is None:
                    print("错误: 无法读取图像数据")
                    return None, None
                
                data = data.astype(np.float64)
                
                if len(data.shape) == 3:
                    print(f"检测到 3D 数据，取第一个通道")
                    data = data[0]
                
                print(f"图像信息:")
                print(f"  - 形状: {data.shape}")
                print(f"  - 数据范围: [{np.min(data):.6f}, {np.max(data):.6f}]")
                print(f"  - 均值: {np.mean(data):.6f}, 标准差: {np.std(data):.6f}")
                
                return data, header
                
        except Exception as e:
            print(f"加载 FITS 文件失败: {str(e)}")
            return None, None
    
    def histogram_peak_stretch(self, data, ratio=2.0/3.0):
        """
        基于直方图峰值的拉伸策略
        以峰值为起点，峰值到最大值的 ratio 为终点

        Args:
            data: 输入数据
            ratio: 从峰值到最大值的比例，默认 2/3
        """
        print(f"\n基于直方图峰值的拉伸:")
        print(f"  - 原始范围: [{np.min(data):.6f}, {np.max(data):.6f}]")
        print(f"  - 原始均值: {np.mean(data):.6f}, 标准差: {np.std(data):.6f}")

        # 计算直方图（使用更多bins以获得更精确的峰值）
        hist, bin_edges = np.histogram(data.flatten(), bins=2000)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        # 手动查找局部峰值（不依赖scipy）
        peaks = []
        for i in range(1, len(hist) - 1):
            # 如果当前点比左右两边都高，且频率大于阈值
            if hist[i] > hist[i-1] and hist[i] > hist[i+1] and hist[i] > 1000:
                peaks.append(i)

        if len(peaks) > 0:
            # 按峰值高度排序，找到最高的几个峰
            peaks = np.array(peaks)
            sorted_peaks = peaks[np.argsort(hist[peaks])[::-1]]

            print(f"  - 找到 {len(peaks)} 个峰值:")
            for i, peak_idx in enumerate(sorted_peaks[:5]):  # 显示前5个最高峰
                print(f"    峰{i+1}: 值={bin_centers[peak_idx]:.6f}, 频率={hist[peak_idx]}")

            # 使用最高峰作为主峰
            peak_idx = sorted_peaks[0]
            peak_value = bin_centers[peak_idx]
        else:
            # 如果没找到峰值，使用最高频率
            peak_idx = np.argmax(hist)
            peak_value = bin_centers[peak_idx]
            print(f"  - 未找到明显峰值，使用最高频率点")

        # 计算最大值
        max_value = np.max(data)

        # 计算终点：峰值 + (最大值 - 峰值) * ratio
        end_value = peak_value + (max_value - peak_value) * ratio

        print(f"  - 选定峰值: {peak_value:.6f} (频率: {hist[peak_idx]})")
        print(f"  - 最大值: {max_value:.6f}")
        print(f"  - 拉伸起点（峰值）: {peak_value:.6f}")
        print(f"  - 拉伸终点（峰值到最大的{ratio:.2%}）: {end_value:.6f}")

        # 线性拉伸：峰值映射到0，终点映射到1
        if end_value > peak_value:
            stretched = (data - peak_value) / (end_value - peak_value)
            stretched = np.clip(stretched, 0, 1)
        else:
            stretched = data.copy()

        print(f"  - 拉伸后范围: [{np.min(stretched):.6f}, {np.max(stretched):.6f}]")
        print(f"  - 拉伸后均值: {np.mean(stretched):.6f}, 标准差: {np.std(stretched):.6f}")

        # 统计拉伸效果
        bg_pixels = np.sum(stretched <= 0)
        dark_pixels = np.sum((stretched > 0) & (stretched < 0.1))
        mid_pixels = np.sum((stretched >= 0.1) & (stretched < 0.5))
        bright_pixels = np.sum(stretched >= 0.5)
        total = stretched.size
        print(f"  - 背景像素(<=0): {bg_pixels} ({bg_pixels/total*100:.2f}%)")
        print(f"  - 暗像素(0-0.1): {dark_pixels} ({dark_pixels/total*100:.2f}%)")
        print(f"  - 中等像素(0.1-0.5): {mid_pixels} ({mid_pixels/total*100:.2f}%)")
        print(f"  - 亮像素(>=0.5): {bright_pixels} ({bright_pixels/total*100:.2f}%)")

        return stretched, peak_value, end_value

    def percentile_stretch(self, data, low_percentile=99.95, use_max=True):
        """
        基于百分位数的拉伸策略
        使用指定百分位数作为起点，最大值作为终点

        Args:
            data: 输入数据
            low_percentile: 低百分位数，默认99.95
            use_max: 是否使用最大值作为终点，默认True
        """
        print(f"\n基于百分位数的拉伸 ({low_percentile}%-最大值):")
        print(f"  - 原始范围: [{np.min(data):.6f}, {np.max(data):.6f}]")
        print(f"  - 原始均值: {np.mean(data):.6f}, 标准差: {np.std(data):.6f}")

        # 计算百分位数作为起点
        vmin = np.percentile(data, low_percentile)
        # 使用实际最大值作为终点
        vmax = np.max(data)

        print(f"  - {low_percentile}% 百分位数: {vmin:.6f}")
        print(f"  - 最大值: {vmax:.6f}")
        print(f"  - 拉伸起点: {vmin:.6f}")
        print(f"  - 拉伸终点（最大值）: {vmax:.6f}")

        # 线性拉伸
        if vmax > vmin:
            stretched = (data - vmin) / (vmax - vmin)
            stretched = np.clip(stretched, 0, 1)
        else:
            stretched = data.copy()

        print(f"  - 拉伸后范围: [{np.min(stretched):.6f}, {np.max(stretched):.6f}]")
        print(f"  - 拉伸后均值: {np.mean(stretched):.6f}, 标准差: {np.std(stretched):.6f}")

        # 统计拉伸效果
        bg_pixels = np.sum(stretched <= 0)
        dark_pixels = np.sum((stretched > 0) & (stretched < 0.1))
        mid_pixels = np.sum((stretched >= 0.1) & (stretched < 0.5))
        bright_pixels = np.sum(stretched >= 0.5)
        total = stretched.size
        print(f"  - 背景像素(<=0): {bg_pixels} ({bg_pixels/total*100:.2f}%)")
        print(f"  - 暗像素(0-0.1): {dark_pixels} ({dark_pixels/total*100:.2f}%)")
        print(f"  - 中等像素(0.1-0.5): {mid_pixels} ({mid_pixels/total*100:.2f}%)")
        print(f"  - 亮像素(>=0.5): {bright_pixels} ({bright_pixels/total*100:.2f}%)")

        return stretched, vmin, vmax

    def estimate_background_noise(self, data):
        """
        估计背景噪声水平
        使用中位数和 MAD (Median Absolute Deviation)
        """
        median = np.median(data)
        mad = np.median(np.abs(data - median))
        sigma = 1.4826 * mad  # MAD 到标准差的转换因子

        print(f"\n背景噪声估计:")
        print(f"  - 中位数: {median:.6f}")
        print(f"  - MAD: {mad:.6f}")
        print(f"  - 估计标准差: {sigma:.6f}")
        print(f"  - {self.sigma_threshold}σ 阈值: {median + self.sigma_threshold * sigma:.6f}")

        return median, sigma

    def remove_bright_lines(self, image, threshold=50, dilate_size=5):
        """
        去除图像中的亮线
        使用边缘检测和霍夫直线检测方法

        Args:
            image: 输入图像（uint8格式）
            threshold: 亮度阈值
            dilate_size: 膨胀大小

        Returns:
            去除亮线后的图像
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # 检测亮区域
        _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

        # 边缘检测
        edges = cv2.Canny(binary, 50, 150, apertureSize=3)

        # 霍夫直线检测
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50,
                                minLineLength=30, maxLineGap=10)

        # 创建掩码
        mask = np.zeros(gray.shape, dtype=np.uint8)

        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                # 在掩码上画线，加粗一些
                cv2.line(mask, (x1, y1), (x2, y2), 255, 3)

        # 膨胀掩码
        if dilate_size > 0:
            kernel = np.ones((dilate_size, dilate_size), np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=1)

        # 使用掩码修复图像
        result = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)

        return result

    def create_signal_mask(self, data, median, sigma):
        """
        创建信号掩码，只保留高于阈值的像素

        .. deprecated::
            此方法已废弃，不再使用。
            实际的mask创建逻辑在 process_fits_file() 方法的第1048行。
            使用硬阈值对拉伸后的数据进行二值化：
            mask = (stretched_data_no_lines > detection_threshold).astype(np.uint8) * 255
        """
        threshold = median + self.sigma_threshold * sigma
        mask = (data > threshold).astype(np.uint8) * 255

        signal_pixels = np.sum(mask > 0)
        total_pixels = mask.size
        percentage = (signal_pixels / total_pixels) * 100

        print(f"\n信号掩码:")
        print(f"  - 阈值: {threshold:.6f}")
        print(f"  - 信号像素: {signal_pixels} ({percentage:.3f}%)")

        return mask, threshold
    
    def detect_blobs_from_mask(self, mask, original_data):
        """
        从掩码中检测斑点
        """
        # 形态学操作，去除小噪点
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask_cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask_cleaned = cv2.morphologyEx(mask_cleaned, cv2.MORPH_CLOSE, kernel)

        # 查找轮廓
        contours, _ = cv2.findContours(mask_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        print(f"\n检测到 {len(contours)} 个候选区域")

        # 估计背景噪声水平（用于计算SNR）
        # 使用整个图像的背景区域（排除掩码区域）
        background_mask = (mask_cleaned == 0)
        if np.sum(background_mask) > 0:
            background_values = original_data[background_mask]
            background_median = np.median(background_values)
            background_mad = np.median(np.abs(background_values - background_median))
            background_sigma = 1.4826 * background_mad
        else:
            background_median = np.median(original_data)
            background_sigma = np.std(original_data)

        print(f"背景噪声: median={background_median:.6f}, sigma={background_sigma:.6f}")

        # 过滤轮廓
        blobs = []
        for contour in contours:
            area = cv2.contourArea(contour)

            # 面积过滤
            if area < self.min_area or area > self.max_area:
                continue

            # 计算圆度
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * area / (perimeter * perimeter)

            # 圆度过滤
            if circularity < self.min_circularity:
                continue

            # 锯齿检测
            hull = cv2.convexHull(contour)
            eps = 0.01 * cv2.arcLength(contour, True)
            poly = cv2.approxPolyDP(contour, eps, True)

            # 计算锯齿比率
            hull_vertices = len(hull)
            poly_vertices = len(poly)
            if hull_vertices > 0:
                jaggedness_ratio = poly_vertices / hull_vertices
            else:
                jaggedness_ratio = 0

            # 锯齿比率过滤
            if jaggedness_ratio > self.max_jaggedness_ratio:
                continue

            # 计算中心和半径
            M = cv2.moments(contour)
            if M['m00'] == 0:
                continue

            cx = M['m10'] / M['m00']
            cy = M['m01'] / M['m00']

            # 计算该区域的信号强度
            mask_region = np.zeros(original_data.shape, dtype=np.uint8)
            cv2.drawContours(mask_region, [contour], -1, 255, -1)
            signal_values = original_data[mask_region > 0]
            mean_signal = np.mean(signal_values)
            max_signal = np.max(signal_values)

            # 计算SNR（信噪比）
            # SNR = (信号 - 背景) / 背景噪声
            snr = (mean_signal - background_median) / (background_sigma + 1e-10)
            max_snr = (max_signal - background_median) / (background_sigma + 1e-10)

            blobs.append({
                'center': (cx, cy),
                'area': area,
                'circularity': circularity,
                'jaggedness_ratio': jaggedness_ratio,
                'hull_vertices': hull_vertices,
                'poly_vertices': poly_vertices,
                'mean_signal': mean_signal,
                'max_signal': max_signal,
                'snr': snr,
                'max_snr': max_snr,
                'contour': contour
            })

        # 按SNR排序（初步排序）
        blobs.sort(key=lambda x: x['snr'], reverse=True)

        print(f"过滤后剩余 {len(blobs)} 个斑点")

        return blobs
    
    def sort_blobs(self, blobs, image_shape):
        """
        对斑点进行排序
        规则：面积和圆度的综合得分作为第一判断依据
        """
        if not blobs:
            return blobs

        # 计算图像中心
        img_center_y, img_center_x = image_shape[0] / 2, image_shape[1] / 2

        # 为每个斑点计算综合得分
        for blob in blobs:
            cx, cy = blob['center']
            distance = np.sqrt((cx - img_center_x)**2 + (cy - img_center_y)**2)
            blob['distance_to_center'] = distance

            # 计算面积和圆度的综合得分（非线性）
            # 面积归一化：假设合理面积范围是 min_area 到 max_area，映射到0-1
            area_normalized = (blob['area'] - self.min_area) / (self.max_area - self.min_area + 1e-10)
            area_normalized = np.clip(area_normalized, 0, 1)

            # 圆度已经是0-1范围
            circularity = blob['circularity']

            # 非线性综合得分：让圆度占更大比例
            # 方案：(圆度^2) × 2000 × 面积归一化(0-1)
            # 圆度的2次方：让圆度差异被适度放大
            # - 圆度0.9: 0.9^2 = 0.81
            # - 圆度0.95: 0.95^2 = 0.90
            # - 圆度0.99: 0.99^2 = 0.98
            # 乘以2000：大幅放大圆度的影响力
            # 乘以归一化面积(0-1)：让面积也有一定影响

            # 综合得分：(圆度^2) × 2000 × 面积归一化(0-1)
            blob['quality_score'] = (circularity ** 2) * 2000 * area_normalized

        # 排序：综合得分降序（大的在前）
        sorted_blobs = sorted(blobs, key=lambda b: -b['quality_score'])

        return sorted_blobs

    def print_blob_info(self, blobs):
        """打印斑点信息"""
        if not blobs:
            print("\n未检测到任何斑点")
            return

        print(f"\n检测到的斑点详细信息（已排序：综合得分=(圆度^2)×2000×面积归一化）:")
        print(f"{'序号':<6} {'综合得分':<10} {'面积':<10} {'圆度':<10} {'锯齿比':<10} {'Hull顶点':<10} {'Poly顶点':<10} {'X坐标':<10} {'Y坐标':<10} {'SNR':<10} {'最大SNR':<10} {'平均信号':<12}")
        print("-" * 140)

        for i, blob in enumerate(blobs, 1):
            cx, cy = blob['center']
            quality_score = blob.get('quality_score', 0)
            snr = blob.get('snr', 0)
            max_snr = blob.get('max_snr', 0)
            jaggedness = blob.get('jaggedness_ratio', 0)
            hull_verts = blob.get('hull_vertices', 0)
            poly_verts = blob.get('poly_vertices', 0)
            print(f"{i:<6} {quality_score:<10.3f} {blob['area']:<10.1f} {blob['circularity']:<10.3f} "
                  f"{jaggedness:<10.3f} {hull_verts:<10} {poly_verts:<10} "
                  f"{cx:<10.2f} {cy:<10.2f} {snr:<10.2f} {max_snr:<10.2f} {blob['mean_signal']:<12.6f}")

        # 统计信息
        quality_scores = [b.get('quality_score', 0) for b in blobs]
        areas = [b['area'] for b in blobs]
        signals = [b['mean_signal'] for b in blobs]
        circularities = [b['circularity'] for b in blobs]
        jaggedness_ratios = [b.get('jaggedness_ratio', 0) for b in blobs]
        snrs = [b.get('snr', 0) for b in blobs]

        print(f"\n统计信息:")
        print(f"  - 总数: {len(blobs)}")
        print(f"  - 综合得分: {np.mean(quality_scores):.3f} ± {np.std(quality_scores):.3f} (范围: {np.min(quality_scores):.3f} - {np.max(quality_scores):.3f})")
        print(f"  - 面积: {np.mean(areas):.2f} ± {np.std(areas):.2f} (范围: {np.min(areas):.2f} - {np.max(areas):.2f})")
        print(f"  - 圆度: {np.mean(circularities):.3f} ± {np.std(circularities):.3f} (范围: {np.min(circularities):.3f} - {np.max(circularities):.3f})")
        print(f"  - 锯齿比: {np.mean(jaggedness_ratios):.3f} ± {np.std(jaggedness_ratios):.3f} (范围: {np.min(jaggedness_ratios):.3f} - {np.max(jaggedness_ratios):.3f})")
        print(f"  - SNR: {np.mean(snrs):.2f} ± {np.std(snrs):.2f} (范围: {np.min(snrs):.2f} - {np.max(snrs):.2f})")
        print(f"  - 平均信号: {np.mean(signals):.6f} ± {np.std(signals):.6f}")
        print(f"  - 信号范围: {np.min(signals):.6f} - {np.max(signals):.6f}")
    
    def draw_blobs(self, data, blobs, mask):
        """绘制检测结果"""
        # 创建彩色图像
        normalized = ((data - np.min(data)) / (np.max(data) - np.min(data)) * 255).astype(np.uint8)
        color_image = cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)

        # 绘制斑点
        for i, blob in enumerate(blobs, 1):
            cx, cy = blob['center']

            # 绘制大空心圆（绿色）
            cv2.circle(color_image, (int(cx), int(cy)), 20, (0, 255, 0), 2)

            # 标注序号（远离中心，只标注前50个）
            if i <= 50:
                cv2.putText(color_image, str(i), (int(cx)+25, int(cy)-25),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        return color_image
    
    def local_stretch(self, cutout, method='percentile', low_percentile=1, high_percentile=99):
        """
        对截图进行局部拉伸以增强细节

        Args:
            cutout: 截图数据
            method: 拉伸方法 ('percentile', 'adaptive', 'histogram')
            low_percentile: 低百分位（默认1%）
            high_percentile: 高百分位（默认99%）

        Returns:
            拉伸后的uint8图像
        """
        if cutout.size == 0:
            return np.zeros_like(cutout, dtype=np.uint8)

        if method == 'percentile':
            # 百分位拉伸：使用1%和99%百分位作为黑白点
            vmin = np.percentile(cutout, low_percentile)
            vmax = np.percentile(cutout, high_percentile)

            if vmax - vmin < 1e-10:
                # 如果范围太小，使用全局最小最大值
                vmin = np.min(cutout)
                vmax = np.max(cutout)

            stretched = np.clip((cutout - vmin) / (vmax - vmin + 1e-10), 0, 1)

        elif method == 'adaptive':
            # 自适应拉伸：基于局部统计
            mean = np.mean(cutout)
            std = np.std(cutout)

            vmin = max(np.min(cutout), mean - 2 * std)
            vmax = min(np.max(cutout), mean + 2 * std)

            stretched = np.clip((cutout - vmin) / (vmax - vmin + 1e-10), 0, 1)

        elif method == 'histogram':
            # 直方图均衡化
            # 先归一化到0-1
            normalized = (cutout - np.min(cutout)) / (np.max(cutout) - np.min(cutout) + 1e-10)
            # 转换到0-255
            uint8_img = (normalized * 255).astype(np.uint8)
            # 应用直方图均衡化
            equalized = cv2.equalizeHist(uint8_img)
            stretched = equalized / 255.0

        else:
            # 默认：简单归一化
            stretched = (cutout - np.min(cutout)) / (np.max(cutout) - np.min(cutout) + 1e-10)

        return (stretched * 255).astype(np.uint8)

    def pixel_to_radec(self, x, y, header):
        """
        将像素坐标转换为RA/DEC坐标

        Args:
            x: X像素坐标
            y: Y像素坐标
            header: FITS header

        Returns:
            (ra, dec) 或 (None, None)
        """
        try:
            # 尝试从header中获取WCS信息
            if 'CRVAL1' in header and 'CRVAL2' in header:
                crval1 = header['CRVAL1']  # 参考点RA
                crval2 = header['CRVAL2']  # 参考点DEC
                crpix1 = header.get('CRPIX1', header['NAXIS1'] / 2)  # 参考像素X
                crpix2 = header.get('CRPIX2', header['NAXIS2'] / 2)  # 参考像素Y
                cd1_1 = header.get('CD1_1', header.get('CDELT1', 0))
                cd2_2 = header.get('CD2_2', header.get('CDELT2', 0))

                # 简单线性转换
                dx = x - crpix1
                dy = y - crpix2
                ra = crval1 + dx * cd1_1
                dec = crval2 + dy * cd2_2

                return ra, dec
        except:
            pass

        return None, None

    def extract_filename_info(self, base_name):
        """
        从文件名中提取gy*和K***-*信息

        Args:
            base_name: 基础文件名

        Returns:
            (gy_info, k_info) 或 (None, None)
        """
        import re

        # 尝试匹配gy*格式
        gy_match = re.search(r'(gy\d+)', base_name, re.IGNORECASE)
        gy_info = gy_match.group(1) if gy_match else None

        # 尝试匹配K***-*格式
        k_match = re.search(r'(K\d+-\d+)', base_name, re.IGNORECASE)
        k_info = k_match.group(1) if k_match else None

        return gy_info, k_info

    def extract_blob_cutouts(self, original_data, stretched_data, result_image, blobs,
                            output_folder, base_name, cutout_size=100,
                            reference_data=None, aligned_data=None,
                            stretch_method='percentile', low_percentile=1, high_percentile=99,
                            header=None, generate_shape_viz=False):
        """
        为每个检测结果提取截图并生成GIF

        Args:
            original_data: 原始FITS数据（difference.fits）
            stretched_data: 拉伸后的数据
            result_image: 带标记的结果图
            blobs: 检测到的斑点列表
            output_folder: 输出文件夹
            base_name: 基础文件名
            cutout_size: 截图大小（默认100x100）
            reference_data: 参考图像数据（模板图像）
            aligned_data: 对齐图像数据（下载图像）
            stretch_method: 拉伸方法 ('percentile', 'adaptive', 'histogram')
            low_percentile: 低百分位（默认1%）
            high_percentile: 高百分位（默认99%）
            header: FITS header（用于坐标转换）
            generate_shape_viz: 是否生成hull和poly可视化图片（默认False，快速模式下为False）
        """
        if not blobs:
            return

        print(f"\n生成每个检测结果的截图（局部拉伸方法: {stretch_method}, 百分位: {low_percentile}-{high_percentile}）...")

        # 创建统一的cutouts文件夹
        cutouts_folder = os.path.join(output_folder, "cutouts")
        os.makedirs(cutouts_folder, exist_ok=True)

        # 提取文件名信息
        gy_info, k_info = self.extract_filename_info(base_name)

        half_size = cutout_size // 2

        for i, blob in enumerate(blobs, 1):
            cx, cy = blob['center']
            cx, cy = int(cx), int(cy)

            # 转换为RA/DEC坐标
            ra, dec = None, None
            if header is not None:
                ra, dec = self.pixel_to_radec(cx, cy, header)

            # 构建文件名前缀，排序序号放在最前面
            name_parts = []

            # 首先添加排序序号（3位补零）
            name_parts.append(f"{i:03d}")

            # 然后添加坐标信息
            if ra is not None and dec is not None:
                name_parts.append(f"RA{ra:.6f}_DEC{dec:.6f}")
            else:
                name_parts.append(f"X{cx:04d}_Y{cy:04d}")

            # 最后添加其他信息
            if gy_info:
                name_parts.append(gy_info)
            if k_info:
                name_parts.append(k_info)

            file_prefix = "_".join(name_parts)

            # 计算截图区域
            x1 = max(0, cx - half_size)
            y1 = max(0, cy - half_size)
            x2 = min(original_data.shape[1], cx + half_size)
            y2 = min(original_data.shape[0], cy + half_size)

            # 提取参考图像截图（模板图像）- 使用局部拉伸
            if reference_data is not None:
                ref_cutout = reference_data[y1:y2, x1:x2]
                ref_norm = self.local_stretch(ref_cutout, method=stretch_method,
                                             low_percentile=low_percentile, high_percentile=high_percentile)
                ref_path = os.path.join(cutouts_folder, f"{file_prefix}_1_reference.png")
                cv2.imwrite(ref_path, ref_norm)
            else:
                # 如果没有参考图像，使用原始数据
                original_cutout = original_data[y1:y2, x1:x2]
                original_norm = self.local_stretch(original_cutout, method=stretch_method,
                                                   low_percentile=low_percentile, high_percentile=high_percentile)
                ref_path = os.path.join(cutouts_folder, f"{file_prefix}_1_reference.png")
                cv2.imwrite(ref_path, original_norm)

            # 提取对齐图像截图（下载图像）- 使用局部拉伸
            if aligned_data is not None:
                aligned_cutout = aligned_data[y1:y2, x1:x2]
                aligned_norm = self.local_stretch(aligned_cutout, method=stretch_method,
                                                 low_percentile=low_percentile, high_percentile=high_percentile)
                aligned_path = os.path.join(cutouts_folder, f"{file_prefix}_2_aligned.png")
                cv2.imwrite(aligned_path, aligned_norm)
            else:
                # 如果没有对齐图像，使用拉伸后的数据
                stretched_cutout = stretched_data[y1:y2, x1:x2]
                stretched_norm = (np.clip(stretched_cutout, 0, 1) * 255).astype(np.uint8)
                aligned_path = os.path.join(cutouts_folder, f"{file_prefix}_2_aligned.png")
                cv2.imwrite(aligned_path, stretched_norm)

            # 提取检测结果截图
            result_cutout = result_image[y1:y2, x1:x2]
            result_path = os.path.join(cutouts_folder, f"{file_prefix}_3_detection.png")
            cv2.imwrite(result_path, result_cutout)

            # 生成hull和poly可视化图片（仅在非快速模式下）
            if generate_shape_viz and 'contour' in blob:
                contour = blob['contour']

                # 计算contour相对于cutout的偏移
                offset_x = x1
                offset_y = y1

                # 调整contour坐标到cutout坐标系
                contour_shifted = contour.copy()
                contour_shifted[:, 0, 0] -= offset_x
                contour_shifted[:, 0, 1] -= offset_y

                # 过滤掉超出cutout范围的点
                valid_mask = (
                    (contour_shifted[:, 0, 0] >= 0) &
                    (contour_shifted[:, 0, 0] < (x2 - x1)) &
                    (contour_shifted[:, 0, 1] >= 0) &
                    (contour_shifted[:, 0, 1] < (y2 - y1))
                )

                if np.any(valid_mask):
                    contour_shifted = contour_shifted[valid_mask]

                    # 计算hull和poly
                    hull = cv2.convexHull(contour_shifted)
                    eps = 0.01 * cv2.arcLength(contour_shifted, True)
                    poly = cv2.approxPolyDP(contour_shifted, eps, True)

                    # === 1. 生成contour单独可视化图片 ===
                    contour_viz = np.zeros((cutout_size, cutout_size, 3), dtype=np.uint8)

                    # 绘制原始轮廓（白色，粗线）
                    cv2.drawContours(contour_viz, [contour_shifted], -1, (255, 255, 255), 2)

                    # 标注轮廓顶点（黄色小圆点）
                    for point in contour_shifted:
                        pt = tuple(point[0])
                        cv2.circle(contour_viz, pt, 1, (0, 255, 255), -1)

                    # 添加标题
                    cv2.putText(contour_viz, "Contour", (5, 15),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

                    # 添加轮廓点数信息
                    contour_points = len(contour_shifted)
                    cv2.putText(contour_viz, f"Points: {contour_points}", (5, 35),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 255), 1)

                    # 保存contour可视化图片
                    contour_viz_path = os.path.join(cutouts_folder, f"{file_prefix}_4_contour.png")
                    cv2.imwrite(contour_viz_path, contour_viz)

                    # === 2. 生成hull可视化图片 ===
                    hull_viz = np.zeros((cutout_size, cutout_size, 3), dtype=np.uint8)

                    # 绘制原始轮廓（灰色，细线）
                    cv2.drawContours(hull_viz, [contour_shifted], -1, (128, 128, 128), 1)

                    # 绘制凸包（绿色，粗线）
                    cv2.drawContours(hull_viz, [hull], -1, (0, 255, 0), 2)

                    # 标注hull顶点（绿色小圆点）
                    for point in hull:
                        pt = tuple(point[0])
                        cv2.circle(hull_viz, pt, 3, (0, 255, 0), -1)

                    # 添加标题和信息
                    cv2.putText(hull_viz, "Convex Hull", (5, 15),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                    hull_verts = blob.get('hull_vertices', len(hull))
                    cv2.putText(hull_viz, f"Vertices: {hull_verts}", (5, 35),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)

                    # 保存hull可视化图片
                    hull_viz_path = os.path.join(cutouts_folder, f"{file_prefix}_5_hull.png")
                    cv2.imwrite(hull_viz_path, hull_viz)

                    # === 3. 生成poly可视化图片 ===
                    poly_viz = np.zeros((cutout_size, cutout_size, 3), dtype=np.uint8)

                    # 绘制原始轮廓（灰色，细线）
                    cv2.drawContours(poly_viz, [contour_shifted], -1, (128, 128, 128), 1)

                    # 绘制多边形近似（红色，粗线）
                    cv2.drawContours(poly_viz, [poly], -1, (0, 0, 255), 2)

                    # 标注poly顶点（红色小圆点）
                    for point in poly:
                        pt = tuple(point[0])
                        cv2.circle(poly_viz, pt, 3, (0, 0, 255), -1)

                    # 添加标题和信息
                    cv2.putText(poly_viz, "Polygon Approx", (5, 15),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
                    poly_verts = blob.get('poly_vertices', len(poly))
                    cv2.putText(poly_viz, f"Vertices: {poly_verts}", (5, 35),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)

                    # 保存poly可视化图片
                    poly_viz_path = os.path.join(cutouts_folder, f"{file_prefix}_6_poly.png")
                    cv2.imwrite(poly_viz_path, poly_viz)

                    # === 4. 生成综合对比图片 ===
                    shape_viz = np.zeros((cutout_size, cutout_size, 3), dtype=np.uint8)

                    # 绘制原始轮廓（白色，细线）
                    cv2.drawContours(shape_viz, [contour_shifted], -1, (255, 255, 255), 1)

                    # 绘制凸包（绿色，粗线）
                    cv2.drawContours(shape_viz, [hull], -1, (0, 255, 0), 2)

                    # 绘制多边形近似（红色，粗线）
                    cv2.drawContours(shape_viz, [poly], -1, (0, 0, 255), 2)

                    # 标注hull顶点（绿色小圆点）
                    for point in hull:
                        pt = tuple(point[0])
                        cv2.circle(shape_viz, pt, 2, (0, 255, 0), -1)

                    # 标注poly顶点（红色小圆点）
                    for point in poly:
                        pt = tuple(point[0])
                        cv2.circle(shape_viz, pt, 3, (0, 0, 255), -1)

                    # 添加图例文字
                    cv2.putText(shape_viz, "White: Contour", (5, 15),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
                    cv2.putText(shape_viz, "Green: Hull", (5, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)
                    cv2.putText(shape_viz, "Red: Poly", (5, 45),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)

                    # 添加顶点数信息
                    jagg_ratio = blob.get('jaggedness_ratio', 0)
                    cv2.putText(shape_viz, f"Hull: {hull_verts}", (5, 65),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)
                    cv2.putText(shape_viz, f"Poly: {poly_verts}", (5, 80),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)
                    cv2.putText(shape_viz, f"Ratio: {jagg_ratio:.3f}", (5, 95),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 0), 1)

                    # 保存综合对比图片
                    shape_viz_path = os.path.join(cutouts_folder, f"{file_prefix}_7_combined.png")
                    cv2.imwrite(shape_viz_path, shape_viz)

            # 生成GIF动画（只包含reference和aligned，不包含detection）
            try:
                images = []
                for img_path in [ref_path, aligned_path]:
                    # 读取图像
                    img = Image.open(img_path)
                    # 确保尺寸一致
                    if img.size != (cutout_size, cutout_size):
                        img = img.resize((cutout_size, cutout_size), Image.LANCZOS)

                    # 转换为RGB模式以便绘制彩色圆圈
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                    # 转换为numpy数组以便使用OpenCV绘制
                    img_array = np.array(img)

                    # 在图像中央画空心绿色圆圈
                    center_x = cutout_size // 2
                    center_y = cutout_size // 2
                    radius = min(cutout_size // 4, 20)  # 圆圈半径，不超过20像素
                    color = (0, 255, 0)  # 绿色 (RGB)
                    thickness = 1  # 线条粗细为1像素（细线）

                    cv2.circle(img_array, (center_x, center_y), radius, color, thickness)

                    # 转换回PIL图像
                    img_with_circle = Image.fromarray(img_array)
                    images.append(img_with_circle)

                gif_path = os.path.join(cutouts_folder, f"{file_prefix}_animation.gif")
                images[0].save(
                    gif_path,
                    save_all=True,
                    append_images=images[1:],
                    duration=800,  # 每帧800ms
                    loop=0  # 无限循环
                )

            except Exception as e:
                print(f"  警告: 生成GIF失败 (blob {i}): {str(e)}")

        print(f"已为 {len(blobs)} 个检测结果生成截图和GIF")

    def save_results(self, original_data, stretched_data, mask, result_image, blobs,
                     output_dir, base_name, threshold_info, reference_data=None, aligned_data=None, header=None, generate_shape_viz=False):
        """保存检测结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 创建带时间戳的输出文件夹
        output_folder = os.path.join(output_dir, f"detection_{timestamp}")
        os.makedirs(output_folder, exist_ok=True)
        print(f"\n输出文件夹: {output_folder}")

        # 构建参数字符串
        threshold = threshold_info.get('threshold', 0)
        stretch_method = threshold_info.get('stretch_method', 'unknown')

        # 根据拉伸方法构建不同的参数字符串
        if 'peak' in stretch_method:
            peak_value = threshold_info.get('peak_value', 0)
            param_str = f"{stretch_method}_thr{threshold:.2f}_peak{peak_value:.3f}_area{self.min_area:.0f}-{self.max_area:.0f}_circ{self.min_circularity:.2f}"
        else:
            # percentile 方法
            param_str = f"{stretch_method}_thr{threshold:.2f}_area{self.min_area:.0f}-{self.max_area:.0f}_circ{self.min_circularity:.2f}"

        # 保存拉伸后的图像（已经是去除亮线后的数据）
        stretched_uint8 = (np.clip(stretched_data, 0, 1) * 255).astype(np.uint8)
        stretched_output = os.path.join(output_folder, f"{base_name}_stretched_{stretch_method}.png")
        cv2.imwrite(stretched_output, stretched_uint8)
        print(f"保存拉伸图像（已去除亮线）: {stretched_output}")

        # 保存掩码
        mask_output = os.path.join(output_folder, f"{base_name}_mask_{param_str}.png")
        cv2.imwrite(mask_output, mask)
        print(f"保存信号掩码: {mask_output}")

        # 保存检测结果图
        result_output = os.path.join(output_folder, f"{base_name}_blobs_{param_str}.png")
        cv2.imwrite(result_output, result_image)
        print(f"保存检测结果图: {result_output}")

        # 生成每个检测结果的截图和GIF
        self.extract_blob_cutouts(original_data, stretched_data, result_image, blobs,
                                  output_folder, base_name,
                                  reference_data=reference_data, aligned_data=aligned_data,
                                  header=header, generate_shape_viz=generate_shape_viz)

        # 保存详细信息
        txt_output = os.path.join(output_folder, f"{base_name}_analysis_{param_str}.txt")

        with open(txt_output, 'w', encoding='utf-8') as f:
            f.write(f"基于信号强度的斑点检测结果\n")
            f.write(f"=" * 80 + "\n")
            f.write(f"时间: {timestamp}\n\n")

            f.write(f"检测参数:\n")
            f.write(f"  - 信号阈值: {self.sigma_threshold}σ\n")
            f.write(f"  - 面积范围: {self.min_area} - {self.max_area}\n")
            f.write(f"  - 最小圆度: {self.min_circularity}\n")
            f.write(f"  - 最大锯齿比率: {self.max_jaggedness_ratio}\n")
            f.write(f"  - 拉伸方法: {threshold_info.get('stretch_method', 'unknown')}\n")
            if 'peak_value' in threshold_info:
                f.write(f"  - 直方图峰值: {threshold_info['peak_value']:.6f}\n")
                f.write(f"  - 拉伸终点: {threshold_info['end_value']:.6f}\n")
            f.write("\n")

            if 'median' in threshold_info:
                f.write(f"背景噪声:\n")
                f.write(f"  - 中位数: {threshold_info['median']:.6f}\n")
                f.write(f"  - 标准差: {threshold_info['sigma']:.6f}\n")

            f.write(f"检测阈值: {threshold_info['threshold']:.6f}\n")
            if 'signal_pixels' in threshold_info:
                f.write(f"信号像素数: {threshold_info['signal_pixels']}\n")
            f.write("\n")

            f.write(f"检测到 {len(blobs)} 个斑点（按综合得分排序：(圆度^2)×2000×面积归一化）\n\n")
            f.write(f"{'序号':<6} {'综合得分':<12} {'面积':<12} {'圆度':<12} {'锯齿比':<12} {'Hull顶点':<10} {'Poly顶点':<10} {'X坐标':<12} {'Y坐标':<12} {'SNR':<12} {'最大SNR':<12} {'平均信号':<14} {'最大信号':<14}\n")
            f.write("-" * 162 + "\n")

            for i, blob in enumerate(blobs, 1):
                cx, cy = blob['center']
                quality_score = blob.get('quality_score', 0)
                snr = blob.get('snr', 0)
                max_snr = blob.get('max_snr', 0)
                jaggedness_ratio = blob.get('jaggedness_ratio', 0)
                hull_vertices = blob.get('hull_vertices', 0)
                poly_vertices = blob.get('poly_vertices', 0)
                f.write(f"{i:<6} {quality_score:<12.4f} {blob['area']:<12.2f} {blob['circularity']:<12.4f} "
                       f"{jaggedness_ratio:<12.4f} {hull_vertices:<10} {poly_vertices:<10} "
                       f"{cx:<12.4f} {cy:<12.4f} {snr:<12.2f} {max_snr:<12.2f} "
                       f"{blob['mean_signal']:<14.8f} {blob['max_signal']:<14.8f}\n")

        print(f"保存分析报告: {txt_output}")
    
    def process_fits_file(self, fits_path, output_dir=None, use_peak_stretch=None, detection_threshold=0.0,
                         reference_fits=None, aligned_fits=None, remove_bright_lines=True,
                         stretch_method='percentile', percentile_low=99.95, fast_mode=False):
        """
        处理 FITS 文件的完整流程

        Args:
            fits_path: difference.fits文件路径
            output_dir: 输出目录
            use_peak_stretch: 是否使用峰值拉伸（已废弃，使用stretch_method，默认None表示由stretch_method决定）
            detection_threshold: 检测阈值，默认0.0（拉伸后数据范围0-1）
            reference_fits: 参考图像（模板）FITS文件路径
            aligned_fits: 对齐图像（下载）FITS文件路径
            remove_bright_lines: 是否去除亮线，默认True
            stretch_method: 拉伸方法，'peak'=峰值拉伸, 'percentile'=百分位数拉伸（默认）
            percentile_low: 百分位数起点，默认99.95，终点使用最大值
            fast_mode: 快速模式，不生成hull和poly可视化图片，默认False
        """
        # 加载数据
        data, header = self.load_fits_image(fits_path)
        if data is None:
            return

        # 加载参考图像和对齐图像（如果提供）
        reference_data = None
        aligned_data = None

        if reference_fits and os.path.exists(reference_fits):
            reference_data, _ = self.load_fits_image(reference_fits)
            if reference_data is not None:
                print(f"已加载参考图像: {os.path.basename(reference_fits)}")

        if aligned_fits and os.path.exists(aligned_fits):
            aligned_data, _ = self.load_fits_image(aligned_fits)
            if aligned_data is not None:
                print(f"已加载对齐图像: {os.path.basename(aligned_fits)}")

        # 根据选择的拉伸方法进行拉伸
        # 如果明确指定了 use_peak_stretch，则使用该参数（向后兼容）
        # 否则使用 stretch_method 参数
        if use_peak_stretch is True or (use_peak_stretch is None and stretch_method == 'peak'):
            # 峰值拉伸
            stretched_data, value1, value2 = self.histogram_peak_stretch(data, ratio=2.0/3.0)
            stretch_method_name = 'histogram_peak'
        elif use_peak_stretch is False or stretch_method == 'percentile':
            # 百分位数拉伸（使用最大值作为终点）
            stretched_data, value1, value2 = self.percentile_stretch(data, percentile_low, use_max=True)
            stretch_method_name = f'percentile_{percentile_low}_max'
        else:
            # 默认使用百分位数拉伸
            stretched_data, value1, value2 = self.percentile_stretch(data, percentile_low, use_max=True)
            stretch_method_name = f'percentile_{percentile_low}_max'

        # 根据参数决定是否去除亮线
        if remove_bright_lines:
            print("\n执行亮线去除...")
            stretched_uint8 = (np.clip(stretched_data, 0, 1) * 255).astype(np.uint8)
            stretched_no_lines_uint8 = self.remove_bright_lines(stretched_uint8)
            # 转换回0-1范围的float数据用于后续检测
            stretched_data_no_lines = stretched_no_lines_uint8.astype(np.float64) / 255.0
            print("亮线去除完成，使用去除亮线后的数据进行检测")
        else:
            print("\n跳过亮线去除，使用原始拉伸数据进行检测")
            stretched_data_no_lines = stretched_data

        # 使用简单阈值检测拉伸后的数据
        detection_data_desc = "去除亮线后的数据" if remove_bright_lines else "拉伸数据"
        print(f"\n使用{detection_data_desc}进行检测...")
        print(f"检测阈值: {detection_threshold}")

        # 创建掩码：拉伸后值 > detection_threshold 的像素
        mask = (stretched_data_no_lines > detection_threshold).astype(np.uint8) * 255
        signal_pixels = np.sum(mask > 0)
        print(f"信号像素: {signal_pixels} ({signal_pixels/mask.size*100:.3f}%)")

        # 检测斑点
        blobs = self.detect_blobs_from_mask(mask, stretched_data_no_lines)

        threshold_info = {
            'threshold': detection_threshold,
            'value1': value1,
            'value2': value2,
            'stretch_method': stretch_method_name,
            'signal_pixels': signal_pixels
        }

        # 兼容旧代码
        if stretch_method == 'peak' or use_peak_stretch:
            threshold_info['peak_value'] = value1
            threshold_info['end_value'] = value2

        # 排序斑点
        blobs = self.sort_blobs(blobs, data.shape)

        # 打印信息
        self.print_blob_info(blobs)

        # 绘制结果（使用去除亮线后的数据）
        result_image = self.draw_blobs(stretched_data_no_lines, blobs, mask)

        # 保存结果
        if output_dir is None:
            output_dir = os.path.dirname(fits_path) or '.'

        base_name = os.path.splitext(os.path.basename(fits_path))[0]

        # 保存时传递去除亮线后的数据
        # 在非快速模式下生成hull和poly可视化
        self.save_results(data, stretched_data_no_lines, mask, result_image, blobs,
                         output_dir, base_name, threshold_info,
                         reference_data=reference_data, aligned_data=aligned_data,
                         header=header, generate_shape_viz=not fast_mode)

        print(f"\n处理完成！")
        return blobs


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='基于直方图峰值的斑点检测')
    parser.add_argument('fits_file', nargs='?',
                       default='aligned_comparison_20251004_151632_difference.fits',
                       help='FITS 文件路径（difference.fits）')
    parser.add_argument('--threshold', type=float, default=0.0,
                       help='检测阈值（拉伸后的值），默认 0.0，推荐范围 0.0-0.5')
    parser.add_argument('--min-area', type=float, default=2,
                       help='最小面积，默认 2')
    parser.add_argument('--max-area', type=float, default=36,
                       help='最大面积，默认 36')
    parser.add_argument('--min-circularity', type=float, default=0.79,
                       help='最小圆度 (0-1)，默认 0.79')
    parser.add_argument('--max-jaggedness-ratio', type=float, default=1.2,
                       help='最大锯齿比率（poly顶点数/hull顶点数），默认 1.2')
    parser.add_argument('--stretch-method', type=str, default='percentile',
                       choices=['peak', 'percentile'],
                       help='拉伸方法: peak=峰值拉伸, percentile=百分位数拉伸(默认)')
    parser.add_argument('--percentile-low', type=float, default=99.95,
                       help='百分位数拉伸的低百分位数，默认99.95，终点使用最大值')
    parser.add_argument('--no-peak-stretch', action='store_true',
                       help='禁用基于峰值的拉伸（已废弃，使用--stretch-method）')
    parser.add_argument('--remove-lines', action='store_true',
                       help='去除亮线（默认不去除，添加此参数后去除）')
    parser.add_argument('--reference', type=str, default=None,
                       help='参考图像（模板）FITS文件路径')
    parser.add_argument('--aligned', type=str, default=None,
                       help='对齐图像（下载）FITS文件路径')
    parser.add_argument('--fast-mode', action='store_true',
                       help='快速模式，不生成hull和poly可视化图片（默认生成）')

    args = parser.parse_args()

    print("=" * 80)
    print("基于直方图的斑点检测")
    if args.stretch_method == 'peak':
        print("拉伸策略: 峰值为起点，峰值到最大值的2/3为终点")
    elif args.stretch_method == 'percentile':
        print(f"拉伸策略: {args.percentile_low}%-最大值")
    print(f"检测阈值: {args.threshold}")
    print("=" * 80)

    # 处理文件路径
    if not os.path.isabs(args.fits_file):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        fits_file = os.path.join(script_dir, args.fits_file)
    else:
        fits_file = args.fits_file

    if not os.path.exists(fits_file):
        print(f"错误: 文件不存在: {fits_file}")
        return

    # 创建检测器并处理
    detector = SignalBlobDetector(
        sigma_threshold=3.0,  # 保留但不使用
        min_area=args.min_area,
        max_area=args.max_area,
        min_circularity=args.min_circularity,
        gamma=2.2,  # 保留但不使用
        max_jaggedness_ratio=args.max_jaggedness_ratio
    )

    # 如果指定了 --no-peak-stretch，则明确设置 use_peak_stretch=False
    # 否则设置为 None，让 stretch_method 参数决定
    use_peak = False if args.no_peak_stretch else None

    detector.process_fits_file(fits_file,
                              use_peak_stretch=use_peak,
                              detection_threshold=args.threshold,
                              reference_fits=args.reference,
                              aligned_fits=args.aligned,
                              remove_bright_lines=args.remove_lines,
                              stretch_method=args.stretch_method,
                              percentile_low=args.percentile_low,
                              fast_mode=args.fast_mode)


if __name__ == "__main__":
    main()