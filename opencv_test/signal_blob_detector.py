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

    def __init__(self, sigma_threshold=5.0, min_area=10, max_area=500, min_circularity=0.3, gamma=2.2):
        """
        初始化检测器

        Args:
            sigma_threshold: 信号阈值（背景噪声的多少倍标准差）
            min_area: 最小面积
            max_area: 最大面积
            min_circularity: 最小圆度
            gamma: 伽马校正值
        """
        self.sigma_threshold = sigma_threshold
        self.min_area = min_area
        self.max_area = max_area
        self.min_circularity = min_circularity
        self.gamma = gamma
        
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
    
    def create_signal_mask(self, data, median, sigma):
        """
        创建信号掩码，只保留高于阈值的像素
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
            
            # 计算中心和半径
            M = cv2.moments(contour)
            if M['m00'] == 0:
                continue
            
            cx = M['m10'] / M['m00']
            cy = M['m01'] / M['m00']
            
            # 计算该区域的平均信号强度
            mask_region = np.zeros(original_data.shape, dtype=np.uint8)
            cv2.drawContours(mask_region, [contour], -1, 255, -1)
            signal_values = original_data[mask_region > 0]
            mean_signal = np.mean(signal_values)
            max_signal = np.max(signal_values)
            
            blobs.append({
                'center': (cx, cy),
                'area': area,
                'circularity': circularity,
                'mean_signal': mean_signal,
                'max_signal': max_signal,
                'contour': contour
            })
        
        # 按平均信号强度排序
        blobs.sort(key=lambda x: x['mean_signal'], reverse=True)
        
        print(f"过滤后剩余 {len(blobs)} 个斑点")
        
        return blobs
    
    def sort_blobs(self, blobs, image_shape):
        """
        对斑点进行排序
        规则：圆度 > 亮度 > 靠近图像中心
        """
        if not blobs:
            return blobs

        # 计算图像中心
        img_center_y, img_center_x = image_shape[0] / 2, image_shape[1] / 2

        # 为每个斑点计算到中心的距离
        for blob in blobs:
            cx, cy = blob['center']
            distance = np.sqrt((cx - img_center_x)**2 + (cy - img_center_y)**2)
            blob['distance_to_center'] = distance

        # 排序：圆度降序（大的在前），亮度降序（大的在前），距离升序（近的在前）
        sorted_blobs = sorted(blobs,
                             key=lambda b: (-b['circularity'], -b['max_signal'], b['distance_to_center']))

        return sorted_blobs

    def print_blob_info(self, blobs):
        """打印斑点信息"""
        if not blobs:
            print("\n未检测到任何斑点")
            return

        print(f"\n检测到的斑点详细信息（已排序：圆度>亮度>靠近中心）:")
        print(f"{'序号':<6} {'X坐标':<10} {'Y坐标':<10} {'面积':<10} {'圆度':<10} {'最大信号':<12} {'平均信号':<12} {'距中心':<10}")
        print("-" * 90)

        for i, blob in enumerate(blobs, 1):
            cx, cy = blob['center']
            dist = blob.get('distance_to_center', 0)
            print(f"{i:<6} {cx:<10.2f} {cy:<10.2f} {blob['area']:<10.1f} "
                  f"{blob['circularity']:<10.3f} {blob['max_signal']:<12.6f} {blob['mean_signal']:<12.6f} {dist:<10.1f}")

        # 统计信息
        areas = [b['area'] for b in blobs]
        signals = [b['mean_signal'] for b in blobs]
        circularities = [b['circularity'] for b in blobs]

        print(f"\n统计信息:")
        print(f"  - 总数: {len(blobs)}")
        print(f"  - 面积: {np.mean(areas):.2f} ± {np.std(areas):.2f} (范围: {np.min(areas):.2f} - {np.max(areas):.2f})")
        print(f"  - 圆度: {np.mean(circularities):.3f} ± {np.std(circularities):.3f} (范围: {np.min(circularities):.3f} - {np.max(circularities):.3f})")
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

    def extract_blob_cutouts(self, original_data, stretched_data, result_image, blobs,
                            output_folder, base_name, cutout_size=100,
                            reference_data=None, aligned_data=None,
                            stretch_method='percentile', low_percentile=1, high_percentile=99):
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
        """
        if not blobs:
            return

        print(f"\n生成每个检测结果的截图（局部拉伸方法: {stretch_method}, 百分位: {low_percentile}-{high_percentile}）...")

        half_size = cutout_size // 2

        for i, blob in enumerate(blobs, 1):
            cx, cy = blob['center']
            cx, cy = int(cx), int(cy)

            # 创建单独的文件夹
            blob_folder = os.path.join(output_folder, f"blob_{i:03d}")
            os.makedirs(blob_folder, exist_ok=True)

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
                ref_path = os.path.join(blob_folder, f"1_reference.png")
                cv2.imwrite(ref_path, ref_norm)
            else:
                # 如果没有参考图像，使用原始数据
                original_cutout = original_data[y1:y2, x1:x2]
                original_norm = self.local_stretch(original_cutout, method=stretch_method,
                                                   low_percentile=low_percentile, high_percentile=high_percentile)
                ref_path = os.path.join(blob_folder, f"1_reference.png")
                cv2.imwrite(ref_path, original_norm)

            # 提取对齐图像截图（下载图像）- 使用局部拉伸
            if aligned_data is not None:
                aligned_cutout = aligned_data[y1:y2, x1:x2]
                aligned_norm = self.local_stretch(aligned_cutout, method=stretch_method,
                                                 low_percentile=low_percentile, high_percentile=high_percentile)
                aligned_path = os.path.join(blob_folder, f"2_aligned.png")
                cv2.imwrite(aligned_path, aligned_norm)
            else:
                # 如果没有对齐图像，使用拉伸后的数据
                stretched_cutout = stretched_data[y1:y2, x1:x2]
                stretched_norm = (np.clip(stretched_cutout, 0, 1) * 255).astype(np.uint8)
                aligned_path = os.path.join(blob_folder, f"2_aligned.png")
                cv2.imwrite(aligned_path, stretched_norm)

            # 提取检测结果截图
            result_cutout = result_image[y1:y2, x1:x2]
            result_path = os.path.join(blob_folder, f"3_detection.png")
            cv2.imwrite(result_path, result_cutout)

            # 生成GIF动画
            try:
                images = []
                for img_path in [ref_path, aligned_path, result_path]:
                    img = Image.open(img_path)
                    # 确保尺寸一致
                    if img.size != (cutout_size, cutout_size):
                        img = img.resize((cutout_size, cutout_size), Image.LANCZOS)
                    images.append(img)

                gif_path = os.path.join(blob_folder, f"animation.gif")
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
                     output_dir, base_name, threshold_info, reference_data=None, aligned_data=None):
        """保存检测结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 创建带时间戳的输出文件夹
        output_folder = os.path.join(output_dir, f"detection_{timestamp}")
        os.makedirs(output_folder, exist_ok=True)
        print(f"\n输出文件夹: {output_folder}")

        # 构建参数字符串
        threshold = threshold_info.get('threshold', 0)
        peak_value = threshold_info.get('peak_value', 0)
        param_str = f"thr{threshold:.2f}_peak{peak_value:.3f}_area{self.min_area:.0f}-{self.max_area:.0f}_circ{self.min_circularity:.2f}"

        # 保存拉伸后的图像
        stretched_uint8 = (np.clip(stretched_data, 0, 1) * 255).astype(np.uint8)
        stretched_output = os.path.join(output_folder, f"{base_name}_stretched_{param_str}.png")
        cv2.imwrite(stretched_output, stretched_uint8)
        print(f"保存拉伸图像: {stretched_output}")

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
                                  reference_data=reference_data, aligned_data=aligned_data)

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

            f.write(f"检测到 {len(blobs)} 个斑点\n\n")
            f.write(f"{'序号':<6} {'X坐标':<12} {'Y坐标':<12} {'面积':<12} {'圆度':<12} {'平均信号':<14} {'最大信号':<14}\n")
            f.write("-" * 90 + "\n")

            for i, blob in enumerate(blobs, 1):
                cx, cy = blob['center']
                f.write(f"{i:<6} {cx:<12.4f} {cy:<12.4f} {blob['area']:<12.2f} "
                       f"{blob['circularity']:<12.4f} {blob['mean_signal']:<14.8f} {blob['max_signal']:<14.8f}\n")

        print(f"保存分析报告: {txt_output}")
    
    def process_fits_file(self, fits_path, output_dir=None, use_peak_stretch=True, detection_threshold=0.5,
                         reference_fits=None, aligned_fits=None):
        """
        处理 FITS 文件的完整流程

        Args:
            fits_path: difference.fits文件路径
            output_dir: 输出目录
            use_peak_stretch: 是否使用峰值拉伸
            detection_threshold: 检测阈值
            reference_fits: 参考图像（模板）FITS文件路径
            aligned_fits: 对齐图像（下载）FITS文件路径
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

        # 基于直方图峰值拉伸
        if use_peak_stretch:
            stretched_data, peak_value, end_value = self.histogram_peak_stretch(data, ratio=2.0/3.0)

            # 使用简单阈值检测拉伸后的数据
            print(f"\n使用拉伸后的数据进行检测...")
            print(f"检测阈值: {detection_threshold}")

            # 创建掩码：拉伸后值 > detection_threshold 的像素
            mask = (stretched_data > detection_threshold).astype(np.uint8) * 255
            signal_pixels = np.sum(mask > 0)
            print(f"信号像素: {signal_pixels} ({signal_pixels/mask.size*100:.3f}%)")

            # 检测斑点
            blobs = self.detect_blobs_from_mask(mask, stretched_data)

            threshold_info = {
                'threshold': detection_threshold,
                'peak_value': peak_value,
                'end_value': end_value,
                'stretch_method': 'histogram_peak',
                'signal_pixels': signal_pixels
            }
        else:
            # 使用原始数据检测
            print(f"\n使用原始数据进行检测...")
            stretched_data = data
            median, sigma = self.estimate_background_noise(data)
            mask, threshold = self.create_signal_mask(data, median, sigma)
            blobs = self.detect_blobs_from_mask(mask, data)

            threshold_info = {
                'median': median,
                'sigma': sigma,
                'threshold': threshold,
                'stretch_method': 'none'
            }

        # 排序斑点
        blobs = self.sort_blobs(blobs, data.shape)

        # 打印信息
        self.print_blob_info(blobs)

        # 绘制结果
        result_image = self.draw_blobs(stretched_data, blobs, mask)

        # 保存结果
        if output_dir is None:
            output_dir = os.path.dirname(fits_path) or '.'

        base_name = os.path.splitext(os.path.basename(fits_path))[0]

        self.save_results(data, stretched_data, mask, result_image, blobs,
                         output_dir, base_name, threshold_info,
                         reference_data=reference_data, aligned_data=aligned_data)

        print(f"\n处理完成！")
        return blobs


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='基于直方图峰值的斑点检测')
    parser.add_argument('fits_file', nargs='?',
                       default='aligned_comparison_20251004_151632_difference.fits',
                       help='FITS 文件路径（difference.fits）')
    parser.add_argument('--threshold', type=float, default=0.5,
                       help='检测阈值（拉伸后的值），默认 0.5，推荐范围 0.3-0.8')
    parser.add_argument('--min-area', type=float, default=1,
                       help='最小面积，默认 1')
    parser.add_argument('--max-area', type=float, default=1000,
                       help='最大面积，默认 1000')
    parser.add_argument('--min-circularity', type=float, default=0.3,
                       help='最小圆度 (0-1)，默认 0.3')
    parser.add_argument('--no-peak-stretch', action='store_true',
                       help='禁用基于峰值的拉伸')
    parser.add_argument('--reference', type=str, default=None,
                       help='参考图像（模板）FITS文件路径')
    parser.add_argument('--aligned', type=str, default=None,
                       help='对齐图像（下载）FITS文件路径')

    args = parser.parse_args()

    print("=" * 80)
    print("基于直方图峰值的斑点检测")
    if not args.no_peak_stretch:
        print("拉伸策略: 峰值为起点，峰值到最大值的2/3为终点")
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
        gamma=2.2  # 保留但不使用
    )

    detector.process_fits_file(fits_file,
                              use_peak_stretch=not args.no_peak_stretch,
                              detection_threshold=args.threshold,
                              reference_fits=args.reference,
                              aligned_fits=args.aligned)


if __name__ == "__main__":
    main()

