#!/usr/bin/env python3
"""
FITS图像对齐和差异检测系统
对两个FITS文件执行图像对齐、差异检测和新亮点标记
"""

import os
import sys
import numpy as np
import cv2

# 设置matplotlib后端，确保图表在独立窗口显示
import matplotlib
matplotlib.use('TkAgg')  # 强制使用TkAgg后端，避免在PyCharm内嵌显示
import matplotlib.pyplot as plt

from astropy.io import fits
from scipy.ndimage import gaussian_filter
from pathlib import Path
import logging
from datetime import datetime
import warnings

# 忽略警告
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# 设置matplotlib中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class FITSAlignmentComparison:
    """FITS图像对齐和差异检测系统"""
    
    def __init__(self, use_central_region=True, central_region_size=200,
                 alignment_method='rigid'):
        """
        初始化对齐比较系统

        Args:
            use_central_region (bool): 是否使用中央区域抽取优化
            central_region_size (int): 中央区域大小
            alignment_method (str): 对齐方法 ('rigid', 'similarity', 'homography')
        """
        self.use_central_region = use_central_region
        self.central_region_size = central_region_size
        self.min_image_size = 300
        self.alignment_method = alignment_method
        
        # 设置日志
        self.setup_logging()
        
        # ORB特征检测器参数
        self.orb_params = {
            'nfeatures': 1000,
            'scaleFactor': 1.2,
            'nlevels': 8,
            'edgeThreshold': 31,
            'firstLevel': 0,
            'WTA_K': 2,
            'patchSize': 31,
            'fastThreshold': 20
        }

        # 尝试设置scoreType，如果不支持则跳过
        try:
            self.orb_params['scoreType'] = cv2.ORB_SCORE_HARRIS
        except AttributeError:
            # 旧版本OpenCV可能不支持这个参数
            pass
        
        # 差异检测参数
        self.diff_params = {
            'gaussian_sigma': 1.0,
            'diff_threshold': 0.1,
            'min_area': 10,
            'max_area': 1000
        }
        
    def setup_logging(self):
        """设置日志系统"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('fits_alignment.log', encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_fits_image(self, fits_path):
        """
        加载FITS图像并进行预处理
        
        Args:
            fits_path (str): FITS文件路径
            
        Returns:
            tuple: (图像数据, header信息, 是否成功)
        """
        try:
            self.logger.info(f"加载FITS文件: {fits_path}")
            
            with fits.open(fits_path) as hdul:
                header = hdul[0].header
                image_data = hdul[0].data
                
                if image_data is None:
                    self.logger.error(f"无法读取图像数据: {fits_path}")
                    return None, None, False
                
                # 转换数据类型
                image_data = image_data.astype(np.float64)
                
                # 抽取中央区域（如果启用）
                processed_data, is_extracted, original_size = self.extract_central_region(image_data)
                
                self.logger.info(f"图像加载成功: {processed_data.shape}")
                return processed_data, header, True
                
        except Exception as e:
            self.logger.error(f"加载FITS文件时出错 {fits_path}: {str(e)}")
            return None, None, False
    
    def extract_central_region(self, image_data):
        """
        抽取图像中央区域（基于现有优化）
        
        Args:
            image_data (np.ndarray): 原始图像数据
            
        Returns:
            tuple: (抽取的图像数据, 是否成功抽取, 原始图像尺寸)
        """
        try:
            height, width = image_data.shape
            
            # 检查是否启用中央区域分析
            if not self.use_central_region:
                self.logger.info(f"使用整个图像进行分析: {width}×{height} 像素")
                return image_data, False, (width, height)
            
            # 如果图像尺寸小于最小要求，使用整个图像
            if height < self.min_image_size or width < self.min_image_size:
                self.logger.info(f"图像尺寸 ({width}×{height}) 小于最小要求，使用整个图像")
                return image_data, False, (width, height)
            
            # 如果图像尺寸小于抽取区域，使用整个图像
            if height < self.central_region_size or width < self.central_region_size:
                self.logger.info(f"图像尺寸 ({width}×{height}) 小于抽取区域，使用整个图像")
                return image_data, False, (width, height)
            
            # 计算中央区域的起始坐标
            center_y, center_x = height // 2, width // 2
            half_size = self.central_region_size // 2
            
            start_y = center_y - half_size
            end_y = center_y + half_size
            start_x = center_x - half_size
            end_x = center_x + half_size
            
            # 抽取中央区域
            central_region = image_data[start_y:end_y, start_x:end_x].copy()
            
            self.logger.info(f"抽取中央区域: {self.central_region_size}×{self.central_region_size} 像素")
            return central_region, True, (width, height)
            
        except Exception as e:
            self.logger.error(f"抽取中央区域时出错: {str(e)}")
            return image_data, False, image_data.shape
    
    def preprocess_image(self, image_data):
        """
        图像预处理：转换为灰度图并进行高斯模糊降噪
        
        Args:
            image_data (np.ndarray): 输入图像数据
            
        Returns:
            np.ndarray: 预处理后的图像
        """
        try:
            # 归一化到0-255范围
            img_normalized = cv2.normalize(image_data, None, 0, 255, cv2.NORM_MINMAX)
            img_uint8 = img_normalized.astype(np.uint8)
            
            # 高斯模糊降噪
            img_blurred = gaussian_filter(img_uint8, sigma=self.diff_params['gaussian_sigma'])
            
            self.logger.info("图像预处理完成")
            return img_blurred
            
        except Exception as e:
            self.logger.error(f"图像预处理时出错: {str(e)}")
            return None
    
    def detect_and_match_features(self, img1, img2):
        """
        使用ORB检测特征点并进行匹配
        
        Args:
            img1 (np.ndarray): 参考图像
            img2 (np.ndarray): 待对齐图像
            
        Returns:
            tuple: (匹配点对, 关键点1, 关键点2, 匹配结果)
        """
        try:
            # 创建ORB检测器
            orb = cv2.ORB_create(**self.orb_params)
            
            # 检测关键点和描述符
            kp1, des1 = orb.detectAndCompute(img1, None)
            kp2, des2 = orb.detectAndCompute(img2, None)
            
            self.logger.info(f"检测到特征点: 图像1={len(kp1)}, 图像2={len(kp2)}")
            
            if des1 is None or des2 is None:
                self.logger.warning("未检测到足够的特征点")
                return None, kp1, kp2, None
            
            # 使用BFMatcher进行特征匹配
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(des1, des2)
            
            # 按距离排序
            matches = sorted(matches, key=lambda x: x.distance)
            
            self.logger.info(f"找到 {len(matches)} 个匹配点")
            
            # 提取匹配点坐标
            if len(matches) >= 4:  # 至少需要4个点来计算单应性矩阵
                src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
                return (src_pts, dst_pts), kp1, kp2, matches
            else:
                self.logger.warning("匹配点数量不足，无法进行对齐")
                return None, kp1, kp2, matches
                
        except Exception as e:
            self.logger.error(f"特征检测和匹配时出错: {str(e)}")
            return None, None, None, None

    def align_images(self, img1, img2, match_points):
        """
        使用适合天文图像的刚体变换对齐图像（平移+旋转，保持形状不变）

        Args:
            img1 (np.ndarray): 参考图像
            img2 (np.ndarray): 待对齐图像
            match_points (tuple): 匹配点对 (src_pts, dst_pts)

        Returns:
            tuple: (对齐后的图像, 变换矩阵, 是否成功)
        """
        try:
            if match_points is None:
                return img2, None, False

            src_pts, dst_pts = match_points

            # 重新整形点坐标
            src_pts_2d = src_pts.reshape(-1, 2)
            dst_pts_2d = dst_pts.reshape(-1, 2)

            transform_matrix = None

            if self.alignment_method == 'rigid':
                # 刚体变换（平移+旋转，保持形状和大小）
                self.logger.info("使用刚体变换（仅平移和旋转）")
                transform_matrix, inliers = cv2.estimateAffinePartial2D(
                    dst_pts_2d, src_pts_2d,
                    method=cv2.RANSAC,
                    ransacReprojThreshold=3.0,
                    maxIters=2000,
                    confidence=0.99
                )

            elif self.alignment_method == 'similarity':
                # 相似变换（平移+旋转+等比缩放）
                self.logger.info("使用相似变换（平移、旋转和等比缩放）")
                transform_matrix, inliers = cv2.estimateAffine2D(
                    dst_pts_2d, src_pts_2d,
                    method=cv2.RANSAC,
                    ransacReprojThreshold=5.0,
                    maxIters=2000,
                    confidence=0.95
                )

            elif self.alignment_method == 'homography':
                # 单应性变换（包含透视变形）
                self.logger.warning("使用单应性变换（可能包含透视变形）")
                homography, mask = cv2.findHomography(
                    dst_pts, src_pts,
                    cv2.RANSAC,
                    ransacReprojThreshold=5.0
                )

                if homography is None:
                    self.logger.error("单应性变换失败")
                    return img2, None, False

                # 应用单应性变换
                height, width = img1.shape
                aligned_img2 = cv2.warpPerspective(img2, homography, (width, height))
                self.logger.warning("已应用单应性变换，可能存在透视变形")
                return aligned_img2, homography, True

            # 如果指定的变换失败，尝试降级
            if transform_matrix is None:
                if self.alignment_method == 'rigid':
                    self.logger.warning("刚体变换失败，尝试相似变换")
                    transform_matrix, inliers = cv2.estimateAffine2D(
                        dst_pts_2d, src_pts_2d,
                        method=cv2.RANSAC,
                        ransacReprojThreshold=5.0,
                        maxIters=2000,
                        confidence=0.95
                    )

                if transform_matrix is None:
                    self.logger.error("所有仿射变换方法都失败")
                    return img2, None, False

            # 应用仿射变换
            height, width = img1.shape
            aligned_img2 = cv2.warpAffine(img2, transform_matrix, (width, height))

            # 分析变换类型
            self.analyze_transformation(transform_matrix)

            self.logger.info("图像对齐完成（使用天文图像友好的变换）")
            return aligned_img2, transform_matrix, True

        except Exception as e:
            self.logger.error(f"图像对齐时出错: {str(e)}")
            return img2, None, False

    def analyze_transformation(self, transform_matrix):
        """
        分析变换矩阵，输出变换信息

        Args:
            transform_matrix (np.ndarray): 2x3变换矩阵
        """
        try:
            if transform_matrix is None or transform_matrix.shape != (2, 3):
                return

            # 提取变换参数
            a, b, tx = transform_matrix[0]
            c, d, ty = transform_matrix[1]

            # 计算旋转角度
            rotation_angle = np.arctan2(b, a) * 180 / np.pi

            # 计算缩放因子
            scale_x = np.sqrt(a*a + b*b)
            scale_y = np.sqrt(c*c + d*d)

            # 计算平移
            translation_x = tx
            translation_y = ty

            self.logger.info(f"变换分析:")
            self.logger.info(f"  平移: ({translation_x:.2f}, {translation_y:.2f}) 像素")
            self.logger.info(f"  旋转: {rotation_angle:.2f} 度")
            self.logger.info(f"  缩放: X={scale_x:.4f}, Y={scale_y:.4f}")

            # 检查是否为刚体变换（无缩放）
            if abs(scale_x - 1.0) < 0.01 and abs(scale_y - 1.0) < 0.01:
                self.logger.info("  变换类型: 刚体变换（仅平移和旋转）")
            elif abs(scale_x - scale_y) < 0.01:
                self.logger.info("  变换类型: 相似变换（平移、旋转和等比缩放）")
            else:
                self.logger.warning("  变换类型: 非等比缩放，可能不适合天文图像")

        except Exception as e:
            self.logger.error(f"分析变换矩阵时出错: {str(e)}")

    def visualize_feature_matching(self, img1, img2, kp1, kp2, matches, save_path=None):
        """
        可视化特征点匹配结果

        Args:
            img1 (np.ndarray): 参考图像
            img2 (np.ndarray): 待对齐图像
            kp1 (list): 图像1的关键点
            kp2 (list): 图像2的关键点
            matches (list): 匹配结果
            save_path (str): 保存路径（可选）
        """
        try:
            if kp1 is None or kp2 is None or matches is None:
                self.logger.warning("无法可视化特征匹配：缺少关键点或匹配数据")
                return

            # 创建匹配可视化图像
            img_matches = cv2.drawMatches(
                img1, kp1, img2, kp2, matches[:20],  # 只显示前20个最佳匹配
                None,
                flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS
            )

            # 使用matplotlib显示
            plt.figure(figsize=(16, 8))
            plt.imshow(img_matches, cmap='gray')
            plt.title(f'特征点匹配可视化 (显示前20个最佳匹配，总共{len(matches)}个)', fontsize=14)
            plt.axis('off')

            # 添加统计信息
            info_text = f"图像1特征点: {len(kp1)}\n图像2特征点: {len(kp2)}\n匹配点对: {len(matches)}"
            plt.text(10, 30, info_text, fontsize=12, color='yellow',
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.7))

            # 保存图像
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                self.logger.info(f"特征匹配可视化已保存到: {save_path}")

            plt.show()

        except Exception as e:
            self.logger.error(f"可视化特征匹配时出错: {str(e)}")

    def visualize_keypoints_separately(self, img1, img2, kp1, kp2, save_path=None):
        """
        分别可视化两张图像的特征点

        Args:
            img1 (np.ndarray): 参考图像
            img2 (np.ndarray): 待对齐图像
            kp1 (list): 图像1的关键点
            kp2 (list): 图像2的关键点
            save_path (str): 保存路径（可选）
        """
        try:
            if kp1 is None or kp2 is None:
                self.logger.warning("无法可视化关键点：缺少关键点数据")
                return

            # 创建子图
            fig, axes = plt.subplots(1, 2, figsize=(16, 8))

            # 绘制图像1的特征点
            img1_kp = cv2.drawKeypoints(img1, kp1, None, color=(0, 255, 0),
                                      flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
            axes[0].imshow(img1_kp)
            axes[0].set_title(f'参考图像特征点 ({len(kp1)}个)', fontsize=12)
            axes[0].axis('off')

            # 绘制图像2的特征点
            img2_kp = cv2.drawKeypoints(img2, kp2, None, color=(0, 255, 0),
                                      flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
            axes[1].imshow(img2_kp)
            axes[1].set_title(f'待对齐图像特征点 ({len(kp2)}个)', fontsize=12)
            axes[1].axis('off')

            plt.tight_layout()

            # 保存图像
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                self.logger.info(f"特征点可视化已保存到: {save_path}")

            plt.show()

        except Exception as e:
            self.logger.error(f"可视化特征点时出错: {str(e)}")

    def analyze_match_quality(self, matches, kp1, kp2):
        """
        分析匹配质量

        Args:
            matches (list): 匹配结果
            kp1 (list): 图像1的关键点
            kp2 (list): 图像2的关键点
        """
        try:
            if not matches or not kp1 or not kp2:
                return

            # 计算匹配距离统计
            distances = [m.distance for m in matches]

            self.logger.info("匹配质量分析:")
            self.logger.info(f"  总匹配数: {len(matches)}")
            self.logger.info(f"  平均距离: {np.mean(distances):.2f}")
            self.logger.info(f"  最小距离: {np.min(distances):.2f}")
            self.logger.info(f"  最大距离: {np.max(distances):.2f}")
            self.logger.info(f"  距离标准差: {np.std(distances):.2f}")

            # 分析匹配点的空间分布
            pts1 = np.array([kp1[m.queryIdx].pt for m in matches])
            pts2 = np.array([kp2[m.trainIdx].pt for m in matches])

            # 计算匹配点的分布范围
            x1_range = np.max(pts1[:, 0]) - np.min(pts1[:, 0])
            y1_range = np.max(pts1[:, 1]) - np.min(pts1[:, 1])
            x2_range = np.max(pts2[:, 0]) - np.min(pts2[:, 0])
            y2_range = np.max(pts2[:, 1]) - np.min(pts2[:, 1])

            self.logger.info("匹配点空间分布:")
            self.logger.info(f"  图像1分布范围: X={x1_range:.1f}, Y={y1_range:.1f}")
            self.logger.info(f"  图像2分布范围: X={x2_range:.1f}, Y={y2_range:.1f}")

            # 质量评估
            if len(matches) < 4:
                self.logger.warning("⚠️  匹配点数量不足，可能影响对齐质量")
            elif len(matches) < 10:
                self.logger.warning("⚠️  匹配点数量较少，建议调整ORB参数")
            else:
                self.logger.info("✅ 匹配点数量充足")

            if np.mean(distances) > 50:
                self.logger.warning("⚠️  平均匹配距离较大，匹配质量可能不佳")
            else:
                self.logger.info("✅ 匹配距离合理")

        except Exception as e:
            self.logger.error(f"分析匹配质量时出错: {str(e)}")

    def detect_differences(self, img1, img2_aligned):
        """
        检测两张对齐图像之间的差异

        Args:
            img1 (np.ndarray): 参考图像
            img2_aligned (np.ndarray): 对齐后的图像

        Returns:
            tuple: (差异图像, 二值化差异图像, 新亮点位置)
        """
        try:
            # 计算绝对差异
            diff_img = cv2.absdiff(img1, img2_aligned)

            # 应用阈值处理
            threshold_value = np.mean(diff_img) + self.diff_params['diff_threshold'] * np.std(diff_img)
            _, binary_diff = cv2.threshold(diff_img, threshold_value, 255, cv2.THRESH_BINARY)

            # 形态学操作去除噪声
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            binary_diff = cv2.morphologyEx(binary_diff, cv2.MORPH_OPEN, kernel)
            binary_diff = cv2.morphologyEx(binary_diff, cv2.MORPH_CLOSE, kernel)

            # 查找轮廓（新亮点）
            contours, _ = cv2.findContours(binary_diff, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # 过滤轮廓（根据面积）
            new_bright_spots = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if self.diff_params['min_area'] <= area <= self.diff_params['max_area']:
                    # 计算轮廓中心
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        new_bright_spots.append((cx, cy, area, contour))

            self.logger.info(f"检测到 {len(new_bright_spots)} 个新亮点")
            return diff_img, binary_diff, new_bright_spots

        except Exception as e:
            self.logger.error(f"差异检测时出错: {str(e)}")
            return None, None, []

    def mark_new_bright_spots(self, img, bright_spots):
        """
        在图像上标记新亮点

        Args:
            img (np.ndarray): 输入图像
            bright_spots (list): 新亮点列表

        Returns:
            np.ndarray: 标记后的图像
        """
        try:
            # 转换为彩色图像以便标记
            if len(img.shape) == 2:
                marked_img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            else:
                marked_img = img.copy()

            # 标记每个新亮点
            for i, (cx, cy, area, contour) in enumerate(bright_spots):
                # 绘制轮廓
                cv2.drawContours(marked_img, [contour], -1, (0, 255, 0), 2)

                # 绘制中心点
                cv2.circle(marked_img, (cx, cy), 3, (0, 0, 255), -1)

                # 添加标签
                label = f"#{i+1} ({area:.0f}px)"
                cv2.putText(marked_img, label, (cx+5, cy-5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

            self.logger.info(f"标记了 {len(bright_spots)} 个新亮点")
            return marked_img

        except Exception as e:
            self.logger.error(f"标记新亮点时出错: {str(e)}")
            return img

    def visualize_results(self, img1, img2, img2_aligned, diff_img, binary_diff, marked_img,
                         bright_spots, save_path=None):
        """
        可视化比较结果

        Args:
            img1 (np.ndarray): 原始参考图像
            img2 (np.ndarray): 原始待比较图像
            img2_aligned (np.ndarray): 对齐后的图像
            diff_img (np.ndarray): 差异图像
            binary_diff (np.ndarray): 二值化差异图像
            marked_img (np.ndarray): 标记后的图像
            bright_spots (list): 新亮点列表
            save_path (str): 保存路径（可选）
        """
        try:
            # 创建子图
            fig, axes = plt.subplots(2, 3, figsize=(18, 12))
            fig.suptitle('FITS图像对齐和差异检测结果', fontsize=16, fontweight='bold')

            # 原始图像1
            axes[0, 0].imshow(img1, cmap='gray')
            axes[0, 0].set_title('参考图像 (图像1)', fontsize=12)
            axes[0, 0].axis('off')

            # 原始图像2
            axes[0, 1].imshow(img2, cmap='gray')
            axes[0, 1].set_title('待比较图像 (图像2)', fontsize=12)
            axes[0, 1].axis('off')

            # 对齐后的图像2
            axes[0, 2].imshow(img2_aligned, cmap='gray')
            axes[0, 2].set_title('对齐后的图像2', fontsize=12)
            axes[0, 2].axis('off')

            # 差异图像
            axes[1, 0].imshow(diff_img, cmap='hot')
            axes[1, 0].set_title('差异图像', fontsize=12)
            axes[1, 0].axis('off')

            # 二值化差异图像
            axes[1, 1].imshow(binary_diff, cmap='gray')
            axes[1, 1].set_title('二值化差异图像', fontsize=12)
            axes[1, 1].axis('off')

            # 标记新亮点的图像
            if len(marked_img.shape) == 3:
                axes[1, 2].imshow(cv2.cvtColor(marked_img, cv2.COLOR_BGR2RGB))
            else:
                axes[1, 2].imshow(marked_img, cmap='gray')
            axes[1, 2].set_title(f'新亮点标记 (共{len(bright_spots)}个)', fontsize=12)
            axes[1, 2].axis('off')

            # 调整布局
            plt.tight_layout()

            # 保存图像
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                self.logger.info(f"结果已保存到: {save_path}")

            # 显示图像
            plt.show()

            # 打印新亮点信息
            if bright_spots:
                self.logger.info("\n新检测到的亮点信息:")
                self.logger.info("=" * 50)
                for i, (cx, cy, area, _) in enumerate(bright_spots):
                    self.logger.info(f"亮点 #{i+1}: 位置=({cx}, {cy}), 面积={area:.1f}像素")
            else:
                self.logger.info("未检测到新的亮点")

        except Exception as e:
            self.logger.error(f"可视化结果时出错: {str(e)}")

    def save_results(self, output_dir, img1, img2_aligned, diff_img, binary_diff, marked_img,
                    bright_spots, filename_prefix="comparison"):
        """
        保存比较结果到文件

        Args:
            output_dir (str): 输出目录
            img1 (np.ndarray): 参考图像
            img2_aligned (np.ndarray): 对齐后的图像
            diff_img (np.ndarray): 差异图像
            binary_diff (np.ndarray): 二值化差异图像
            marked_img (np.ndarray): 标记后的图像
            bright_spots (list): 新亮点列表
            filename_prefix (str): 文件名前缀
        """
        try:
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 保存各种图像
            cv2.imwrite(os.path.join(output_dir, f"{filename_prefix}_reference_{timestamp}.png"), img1)
            cv2.imwrite(os.path.join(output_dir, f"{filename_prefix}_aligned_{timestamp}.png"), img2_aligned)
            cv2.imwrite(os.path.join(output_dir, f"{filename_prefix}_difference_{timestamp}.png"), diff_img)
            cv2.imwrite(os.path.join(output_dir, f"{filename_prefix}_binary_diff_{timestamp}.png"), binary_diff)
            cv2.imwrite(os.path.join(output_dir, f"{filename_prefix}_marked_{timestamp}.png"), marked_img)

            # 保存亮点信息到文本文件
            info_file = os.path.join(output_dir, f"{filename_prefix}_bright_spots_{timestamp}.txt")
            with open(info_file, 'w', encoding='utf-8') as f:
                f.write(f"FITS图像对齐和差异检测结果\n")
                f.write(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"检测到的新亮点数量: {len(bright_spots)}\n\n")

                if bright_spots:
                    f.write("新亮点详细信息:\n")
                    f.write("-" * 40 + "\n")
                    for i, (cx, cy, area, _) in enumerate(bright_spots):
                        f.write(f"亮点 #{i+1}:\n")
                        f.write(f"  位置: ({cx}, {cy})\n")
                        f.write(f"  面积: {area:.1f} 像素\n\n")
                else:
                    f.write("未检测到新的亮点\n")

            self.logger.info(f"所有结果已保存到目录: {output_dir}")

        except Exception as e:
            self.logger.error(f"保存结果时出错: {str(e)}")

    def process_fits_comparison(self, fits_path1, fits_path2, output_dir=None, show_visualization=True):
        """
        处理两个FITS文件的完整比较流程

        Args:
            fits_path1 (str): 参考FITS文件路径
            fits_path2 (str): 待比较FITS文件路径
            output_dir (str): 输出目录（可选）
            show_visualization (bool): 是否显示可视化结果

        Returns:
            dict: 处理结果摘要
        """
        try:
            self.logger.info("=" * 60)
            self.logger.info("开始FITS图像对齐和差异检测")
            self.logger.info("=" * 60)

            # 1. 加载FITS图像
            self.logger.info("步骤1: 加载FITS图像")
            img1_data, header1, success1 = self.load_fits_image(fits_path1)
            img2_data, header2, success2 = self.load_fits_image(fits_path2)

            if not success1 or not success2:
                self.logger.error("FITS图像加载失败")
                return None

            # 2. 图像预处理
            self.logger.info("步骤2: 图像预处理")
            img1_processed = self.preprocess_image(img1_data)
            img2_processed = self.preprocess_image(img2_data)

            if img1_processed is None or img2_processed is None:
                self.logger.error("图像预处理失败")
                return None

            # 3. 特征检测和匹配
            self.logger.info("步骤3: 特征检测和匹配")
            match_points, kp1, kp2, matches = self.detect_and_match_features(img1_processed, img2_processed)

            # 3.1 分析匹配质量
            self.analyze_match_quality(matches, kp1, kp2)

            # 3.2 可视化特征点匹配（如果启用可视化）
            if show_visualization and output_dir:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                # 可视化特征点匹配
                match_viz_path = os.path.join(output_dir, f"feature_matching_{timestamp}.png")
                self.visualize_feature_matching(img1_processed, img2_processed, kp1, kp2, matches, match_viz_path)

                # 可视化单独的特征点
                keypoints_viz_path = os.path.join(output_dir, f"keypoints_separate_{timestamp}.png")
                self.visualize_keypoints_separately(img1_processed, img2_processed, kp1, kp2, keypoints_viz_path)

            # 4. 图像对齐
            self.logger.info("步骤4: 图像对齐")
            img2_aligned, homography, alignment_success = self.align_images(
                img1_processed, img2_processed, match_points
            )

            # 5. 差异检测
            self.logger.info("步骤5: 差异检测")
            diff_img, binary_diff, bright_spots = self.detect_differences(img1_processed, img2_aligned)

            if diff_img is None:
                self.logger.error("差异检测失败")
                return None

            # 6. 标记新亮点
            self.logger.info("步骤6: 标记新亮点")
            marked_img = self.mark_new_bright_spots(img2_aligned, bright_spots)

            # 7. 结果可视化
            if show_visualization:
                self.logger.info("步骤7: 结果可视化")
                save_path = None
                if output_dir:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    save_path = os.path.join(output_dir, f"comparison_visualization_{timestamp}.png")

                self.visualize_results(
                    img1_processed, img2_processed, img2_aligned,
                    diff_img, binary_diff, marked_img, bright_spots, save_path
                )

            # 8. 保存结果
            if output_dir:
                self.logger.info("步骤8: 保存结果")
                self.save_results(
                    output_dir, img1_processed, img2_aligned, diff_img,
                    binary_diff, marked_img, bright_spots
                )

            # 生成结果摘要
            result_summary = {
                'success': True,
                'files_processed': [fits_path1, fits_path2],
                'alignment_success': alignment_success,
                'features_detected': {
                    'image1': len(kp1) if kp1 else 0,
                    'image2': len(kp2) if kp2 else 0,
                    'matches': len(matches) if matches else 0
                },
                'new_bright_spots': len(bright_spots),
                'bright_spots_details': [
                    {'position': (cx, cy), 'area': area}
                    for cx, cy, area, _ in bright_spots
                ],
                'processing_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            self.logger.info("=" * 60)
            self.logger.info("FITS图像对齐和差异检测完成")
            self.logger.info(f"检测到 {len(bright_spots)} 个新亮点")
            self.logger.info("=" * 60)

            return result_summary

        except Exception as e:
            self.logger.error(f"处理FITS比较时出错: {str(e)}")
            return None


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='FITS图像对齐和差异检测系统')
    parser.add_argument('fits1', help='参考FITS文件路径')
    parser.add_argument('fits2', help='待比较FITS文件路径')
    parser.add_argument('--output', '-o', help='输出目录路径')
    parser.add_argument('--no-visualization', action='store_true', help='不显示可视化结果')
    parser.add_argument('--no-central-region', action='store_true', help='不使用中央区域优化')
    parser.add_argument('--region-size', type=int, default=200, help='中央区域大小（默认200）')
    parser.add_argument('--alignment-method', choices=['rigid', 'similarity', 'homography'],
                       default='rigid', help='对齐方法：rigid(刚体), similarity(相似), homography(单应性)')

    args = parser.parse_args()

    # 检查文件是否存在
    if not os.path.exists(args.fits1):
        print(f"错误: 文件不存在 - {args.fits1}")
        sys.exit(1)

    if not os.path.exists(args.fits2):
        print(f"错误: 文件不存在 - {args.fits2}")
        sys.exit(1)

    # 创建比较系统
    comparator = FITSAlignmentComparison(
        use_central_region=not args.no_central_region,
        central_region_size=args.region_size,
        alignment_method=args.alignment_method
    )

    # 执行比较
    result = comparator.process_fits_comparison(
        args.fits1,
        args.fits2,
        output_dir=args.output,
        show_visualization=not args.no_visualization
    )

    if result:
        print("\n处理完成！")
        print(f"检测到 {result['new_bright_spots']} 个新亮点")
        if result['bright_spots_details']:
            print("\n新亮点详情:")
            for i, spot in enumerate(result['bright_spots_details']):
                print(f"  #{i+1}: 位置{spot['position']}, 面积{spot['area']:.1f}像素")
    else:
        print("处理失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()
