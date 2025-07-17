"""
快速星点检测器 - 不使用SEP的高效实现
使用OpenCV和astropy进行星点检测
"""

import numpy as np
import cv2
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
import matplotlib.pyplot as plt
import os
from pathlib import Path
import logging

class StarDetector:
    def __init__(self, min_area=5, max_area=1000, threshold_factor=3.0, min_circularity=0.3, min_solidity=0.5,
                 adaptive_threshold=True, dark_star_mode=False, circle_thickness=1, circle_size_factor=1.5):
        """
        初始化星点检测器

        Parameters:
        -----------
        min_area : int
            最小星点面积（像素）
        max_area : int
            最大星点面积（像素）
        threshold_factor : float
            阈值因子，用于确定检测阈值
        min_circularity : float
            最小圆度 (0-1，1为完美圆形)
        min_solidity : float
            最小实心度 (0-1，1为完全实心)
        adaptive_threshold : bool
            是否使用自适应阈值
        dark_star_mode : bool
            暗星检测模式，使用更低的阈值
        circle_thickness : int
            圆圈线条粗细（像素）
        circle_size_factor : float
            圆圈大小倍数
        """
        self.min_area = min_area
        self.max_area = max_area
        self.threshold_factor = threshold_factor
        self.min_circularity = min_circularity
        self.min_solidity = min_solidity
        self.adaptive_threshold = adaptive_threshold
        self.dark_star_mode = dark_star_mode
        self.circle_thickness = circle_thickness
        self.circle_size_factor = circle_size_factor
        
        # 设置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def load_fits_image(self, fits_path):
        """
        加载FITS文件并返回图像数据
        
        Parameters:
        -----------
        fits_path : str
            FITS文件路径
            
        Returns:
        --------
        numpy.ndarray
            图像数据
        """
        try:
            with fits.open(fits_path) as hdul:
                # 获取主要图像数据
                image_data = hdul[0].data
                
                # 如果是3D数据，取第一个切片
                if len(image_data.shape) == 3:
                    image_data = image_data[0]
                    
                # 确保数据类型为float
                image_data = image_data.astype(np.float32)
                
                self.logger.info(f"加载FITS文件: {fits_path}")
                self.logger.info(f"图像尺寸: {image_data.shape}")
                
                return image_data
                
        except Exception as e:
            self.logger.error(f"加载FITS文件失败: {e}")
            return None
    
    def preprocess_image(self, image_data):
        """
        预处理图像数据

        Parameters:
        -----------
        image_data : numpy.ndarray
            原始图像数据

        Returns:
        --------
        numpy.ndarray
            预处理后的8位图像
        """
        # 计算统计信息
        mean, median, std = sigma_clipped_stats(image_data, sigma=3.0)

        self.logger.info(f"图像统计: mean={mean:.2f}, median={median:.2f}, std={std:.2f}")

        if self.dark_star_mode:
            # 暗星模式：更敏感的归一化
            vmin = median - 1 * std  # 更低的下限
            vmax = median + 5 * std  # 更低的上限，增强对比度
            self.logger.info("使用暗星检测模式")
        else:
            # 标准模式
            vmin = median - 2 * std
            vmax = median + 10 * std

        # 裁剪和缩放
        normalized = np.clip((image_data - vmin) / (vmax - vmin), 0, 1)
        image_8bit = (normalized * 255).astype(np.uint8)

        # 暗星模式下应用直方图均衡化增强对比度
        if self.dark_star_mode:
            image_8bit = cv2.equalizeHist(image_8bit)
            self.logger.info("应用直方图均衡化增强暗星对比度")

        return image_8bit, mean, median, std

    def calculate_shape_metrics(self, contour):
        """
        计算轮廓的形状指标

        Parameters:
        -----------
        contour : numpy.ndarray
            OpenCV轮廓

        Returns:
        --------
        tuple
            (circularity, solidity, aspect_ratio)
        """
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)

        # 计算圆度 (4π*面积/周长²)
        if perimeter > 0:
            circularity = 4 * np.pi * area / (perimeter * perimeter)
        else:
            circularity = 0

        # 计算实心度 (轮廓面积/凸包面积)
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        if hull_area > 0:
            solidity = area / hull_area
        else:
            solidity = 0

        # 计算长宽比
        rect = cv2.minAreaRect(contour)
        width, height = rect[1]
        if height > 0:
            aspect_ratio = width / height if width > height else height / width
        else:
            aspect_ratio = 1

        return circularity, solidity, aspect_ratio
    
    def detect_stars_opencv(self, image_8bit, background_stats):
        """
        使用OpenCV检测星点

        Parameters:
        -----------
        image_8bit : numpy.ndarray
            8位预处理图像
        background_stats : tuple
            背景统计信息 (mean, median, std)

        Returns:
        --------
        list
            检测到的星点坐标列表 [(x, y, area), ...]
        """
        mean, median, std = background_stats

        if self.adaptive_threshold:
            # 自适应阈值检测
            binary = cv2.adaptiveThreshold(
                image_8bit, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
            self.logger.info("使用自适应阈值")
        else:
            # 传统固定阈值
            if self.dark_star_mode:
                # 暗星模式：更低的阈值
                threshold_factor = self.threshold_factor * 0.5  # 降低阈值因子
                threshold_value = median + threshold_factor * std
                threshold_8bit = int(np.clip((threshold_value - median + std) / (5*std) * 255, 0, 255))
                self.logger.info(f"暗星模式阈值: {threshold_8bit}")
            else:
                threshold_value = median + self.threshold_factor * std
                threshold_8bit = int(np.clip((threshold_value - median + 2*std) / (10*std) * 255, 0, 255))
                self.logger.info(f"标准阈值: {threshold_8bit}")

            # 二值化
            _, binary = cv2.threshold(image_8bit, threshold_8bit, 255, cv2.THRESH_BINARY)

        # 形态学操作去除噪声
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))  # 更小的核，保留小星点
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        # 查找轮廓
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        stars = []
        filtered_count = 0

        for contour in contours:
            area = cv2.contourArea(contour)

            # 过滤面积
            if self.min_area <= area <= self.max_area:
                # 计算形状指标
                circularity, solidity, aspect_ratio = self.calculate_shape_metrics(contour)

                # 过滤圆度和实心度
                if circularity >= self.min_circularity and solidity >= self.min_solidity:
                    # 计算质心
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        stars.append((cx, cy, area, circularity, solidity, aspect_ratio))
                else:
                    filtered_count += 1
        
        self.logger.info(f"检测到 {len(stars)} 个圆形星点 (过滤掉 {filtered_count} 个非圆形对象)")
        return stars
    
    def create_marked_image(self, image_8bit, stars, output_path):
        """
        创建标记了星点的图像
        
        Parameters:
        -----------
        image_8bit : numpy.ndarray
            8位图像
        stars : list
            星点列表
        output_path : str
            输出图像路径
        """
        # 转换为RGB图像用于显示
        if len(image_8bit.shape) == 2:
            marked_image = cv2.cvtColor(image_8bit, cv2.COLOR_GRAY2RGB)
        else:
            marked_image = image_8bit.copy()
        
        # 标记星点
        for i, star_data in enumerate(stars):
            if len(star_data) == 6:  # 新格式包含形状指标
                x, y, area, circularity, solidity, aspect_ratio = star_data
            else:  # 兼容旧格式
                x, y, area = star_data[:3]
                circularity = 1.0

            # 根据圆度选择颜色 - 越圆越绿
            if circularity >= 0.8:
                color = (0, 255, 0)  # 绿色 - 很圆
            elif circularity >= 0.5:
                color = (0, 255, 255)  # 黄色 - 较圆
            else:
                color = (0, 128, 255)  # 橙色 - 一般圆

            # 绘制可配置大小和粗细的圆圈标记星点
            base_radius = max(8, int(np.sqrt(area / np.pi) * self.circle_size_factor) + 5)
            radius = min(base_radius, 30)  # 限制最大半径为30像素
            cv2.circle(marked_image, (x, y), radius, color, self.circle_thickness)

            # 绘制内圈增强可见性（如果圆圈足够大）
            if radius > 10:
                inner_radius = max(4, radius - 4)
                cv2.circle(marked_image, (x, y), inner_radius, color, self.circle_thickness)

            # 添加编号 - 位置调整到圆圈外
            text_x = x + radius + 3
            text_y = y + 4
            cv2.putText(marked_image, str(i+1), (text_x, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # 为编号添加黑色背景增强可读性
            cv2.putText(marked_image, str(i+1), (text_x-1, text_y-1),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        
        # 保存图像
        cv2.imwrite(output_path, cv2.cvtColor(marked_image, cv2.COLOR_RGB2BGR))
        self.logger.info(f"标记图像已保存: {output_path}")
        
        return marked_image

    def create_marked_fits(self, image_data, stars, output_path):
        """
        创建标记了星点的FITS文件

        Parameters:
        -----------
        image_data : numpy.ndarray
            原始FITS图像数据
        stars : list
            星点列表
        output_path : str
            输出FITS文件路径
        """
        # 复制原始图像数据
        marked_data = image_data.copy().astype(np.float32)

        # 获取图像的统计信息用于标记强度
        mean, median, std = sigma_clipped_stats(marked_data, sigma=3.0)
        mark_intensity = median + 5 * std  # 标记强度比背景亮很多

        # 标记星点
        for i, star_data in enumerate(stars):
            if len(star_data) == 6:  # 新格式包含形状指标
                x, y, area, circularity, solidity, aspect_ratio = star_data
            else:  # 兼容旧格式
                x, y, area = star_data[:3]

            # 计算圆圈半径
            base_radius = max(8, int(np.sqrt(area / np.pi) * self.circle_size_factor) + 5)
            radius = min(base_radius, 30)

            # 在FITS数据中绘制圆圈
            self._draw_circle_in_fits(marked_data, x, y, radius, mark_intensity)

            # 如果圆圈足够大，绘制内圈
            if radius > 10:
                inner_radius = max(4, radius - 4)
                self._draw_circle_in_fits(marked_data, x, y, inner_radius, mark_intensity)

        # 保存标记后的FITS文件
        try:
            from astropy.io import fits
            hdu = fits.PrimaryHDU(marked_data)
            hdu.writeto(output_path, overwrite=True)
            self.logger.info(f"标记FITS文件已保存: {output_path}")
        except Exception as e:
            self.logger.error(f"保存FITS文件失败: {e}")

    def _draw_circle_in_fits(self, data, cx, cy, radius, intensity):
        """
        在FITS数据中绘制圆圈

        Parameters:
        -----------
        data : numpy.ndarray
            FITS图像数据
        cx, cy : int
            圆心坐标
        radius : int
            圆圈半径
        intensity : float
            标记强度值
        """
        height, width = data.shape

        # 创建圆圈的坐标
        y_coords, x_coords = np.ogrid[:height, :width]

        # 计算到圆心的距离
        distances = np.sqrt((x_coords - cx)**2 + (y_coords - cy)**2)

        # 创建圆圈掩码（圆环，不是实心圆）
        thickness = max(1, self.circle_thickness)
        outer_mask = distances <= radius
        inner_mask = distances <= (radius - thickness)
        circle_mask = outer_mask & ~inner_mask

        # 在圆圈位置设置标记强度
        data[circle_mask] = intensity
    
    def process_fits_file(self, fits_path, output_dir, save_marked_fits=False):
        """
        处理单个FITS文件

        Parameters:
        -----------
        fits_path : str
            FITS文件路径
        output_dir : str
            输出目录
        save_marked_fits : bool
            是否保存标记后的FITS文件

        Returns:
        --------
        dict
            处理结果
        """
        # 加载图像
        image_data = self.load_fits_image(fits_path)
        if image_data is None:
            return None

        # 预处理
        image_8bit, mean, median, std = self.preprocess_image(image_data)

        # 检测星点
        stars = self.detect_stars_opencv(image_8bit, (mean, median, std))

        # 创建输出文件名
        fits_name = Path(fits_path).stem
        jpg_output_path = os.path.join(output_dir, f"{fits_name}_stars.jpg")

        # 创建标记图像
        marked_image = self.create_marked_image(image_8bit, stars, jpg_output_path)

        # 如果需要，创建标记后的FITS文件
        fits_output_path = None
        if save_marked_fits:
            fits_output_path = os.path.join(output_dir, f"{fits_name}_marked.fits")
            self.create_marked_fits(image_data, stars, fits_output_path)

        # 返回结果
        result = {
            'fits_file': fits_path,
            'output_image': jpg_output_path,
            'output_fits': fits_output_path,
            'num_stars': len(stars),
            'stars': stars,
            'image_stats': {'mean': mean, 'median': median, 'std': std}
        }

        return result
