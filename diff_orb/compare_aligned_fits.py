#!/usr/bin/env python3
"""
对比已对齐的FITS文件差异检测脚本
专门用于处理 E:\fix_data\align-diff 文件夹中的已对齐FITS文件
输出FITS和JPG格式的差异结果
"""

import os
import sys
import numpy as np
import cv2
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from astropy.io import fits
from scipy.ndimage import gaussian_filter
from pathlib import Path
import logging
from datetime import datetime
import warnings
import glob
import subprocess

# 忽略警告
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# 设置matplotlib中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class AlignedFITSComparator:
    """已对齐FITS文件差异比较器"""
    
    def __init__(self):
        """初始化比较器"""
        self.setup_logging()
        
        # 差异检测参数
        self.diff_params = {
            'gaussian_sigma': 1.0,
            'diff_threshold': 0.1,
            'min_spot_area': 5,
            'max_spot_area': 1000
        }
    
    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('aligned_fits_comparison.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_fits_data(self, fits_path):
        """
        加载FITS文件数据
        
        Args:
            fits_path (str): FITS文件路径
            
        Returns:
            numpy.ndarray: 图像数据，如果失败返回None
        """
        try:
            with fits.open(fits_path) as hdul:
                data = hdul[0].data.astype(np.float64)
                
                # 处理可能的3D数据（取第一个通道）
                if len(data.shape) == 3:
                    data = data[0]
                
                self.logger.info(f"成功加载FITS文件: {os.path.basename(fits_path)}, 形状: {data.shape}")
                return data
                
        except Exception as e:
            self.logger.error(f"加载FITS文件失败 {fits_path}: {str(e)}")
            return None
    
    def normalize_image(self, image):
        """
        标准化图像数据到0-1范围

        Args:
            image (numpy.ndarray): 输入图像

        Returns:
            numpy.ndarray: 标准化后的图像
        """
        # 使用百分位数进行鲁棒标准化
        p1, p99 = np.percentile(image, [1, 99])
        normalized = np.clip((image - p1) / (p99 - p1), 0, 1)
        return normalized

    def create_overlap_mask(self, ref_image, aligned_image, threshold=1e-6):
        """
        创建重叠区域掩码，识别两个图像的有效重叠区域

        Args:
            ref_image (numpy.ndarray): 参考图像
            aligned_image (numpy.ndarray): 对齐后的图像
            threshold (float): 判断有效像素的阈值

        Returns:
            numpy.ndarray: 重叠区域掩码（1表示重叠，0表示非重叠）
        """
        # 创建有效像素掩码
        ref_valid = np.abs(ref_image) > threshold
        aligned_valid = np.abs(aligned_image) > threshold

        # 重叠区域是两个图像都有有效像素的区域
        overlap_mask = (ref_valid & aligned_valid).astype(np.uint8)

        self.logger.info(f"重叠区域像素数: {np.sum(overlap_mask)}, "
                        f"总像素数: {overlap_mask.size}, "
                        f"重叠比例: {np.sum(overlap_mask)/overlap_mask.size:.2%}")

        return overlap_mask
    
    def detect_differences(self, img1, img2):
        """
        检测两个图像之间的差异

        Args:
            img1 (numpy.ndarray): 参考图像
            img2 (numpy.ndarray): 比较图像

        Returns:
            tuple: (差异图像, 二值化差异图像, 新亮点信息, 重叠区域掩码)
        """
        # 创建重叠区域掩码
        overlap_mask = self.create_overlap_mask(img1, img2)

        # 标准化图像
        norm_img1 = self.normalize_image(img1)
        norm_img2 = self.normalize_image(img2)

        # 应用高斯模糊减少噪声
        blurred_img1 = gaussian_filter(norm_img1, sigma=self.diff_params['gaussian_sigma'])
        blurred_img2 = gaussian_filter(norm_img2, sigma=self.diff_params['gaussian_sigma'])

        # 计算差异（只在重叠区域）
        diff_image = np.abs(blurred_img2 - blurred_img1) * overlap_mask

        # 二值化差异图像
        binary_diff = (diff_image > self.diff_params['diff_threshold']).astype(np.uint8)

        # 查找连通区域（新亮点）
        contours, _ = cv2.findContours(binary_diff, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        bright_spots = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.diff_params['min_spot_area'] <= area <= self.diff_params['max_spot_area']:
                # 计算质心
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    # 确保亮点在重叠区域内
                    if overlap_mask[cy, cx] > 0:
                        bright_spots.append({
                            'position': (cx, cy),
                            'area': area,
                            'contour': contour
                        })

        self.logger.info(f"检测到 {len(bright_spots)} 个新亮点")

        return diff_image, binary_diff, bright_spots, overlap_mask
    
    def save_fits_result(self, data, output_path, header=None):
        """
        保存数据为FITS文件
        
        Args:
            data (numpy.ndarray): 要保存的数据
            output_path (str): 输出路径
            header: FITS头信息（可选）
        """
        try:
            hdu = fits.PrimaryHDU(data=data.astype(np.float32), header=header)
            hdu.writeto(output_path, overwrite=True)
            self.logger.info(f"FITS文件已保存: {output_path}")
        except Exception as e:
            self.logger.error(f"保存FITS文件失败 {output_path}: {str(e)}")
    
    def get_overlap_bounding_box(self, overlap_mask):
        """
        获取重叠区域的边界框

        Args:
            overlap_mask (numpy.ndarray): 重叠区域掩码

        Returns:
            tuple: (x_min, y_min, x_max, y_max) 边界框坐标，如果没有重叠区域返回None
        """
        try:
            # 找到所有非零像素的坐标
            coords = np.argwhere(overlap_mask > 0)

            if len(coords) == 0:
                return None

            # 获取边界框 (注意：argwhere返回的是(row, col)即(y, x))
            y_min, x_min = coords.min(axis=0)
            y_max, x_max = coords.max(axis=0)

            return (x_min, y_min, x_max, y_max)

        except Exception as e:
            self.logger.error(f"计算重叠区域边界框失败: {str(e)}")
            return None

    def save_jpg_result(self, data, output_path, title="", colormap='viridis',
                       overlap_bbox=None, draw_alignment_box=False):
        """
        保存数据为JPG文件

        Args:
            data (numpy.ndarray): 要保存的数据
            output_path (str): 输出路径
            title (str): 图像标题
            colormap (str): 颜色映射
            overlap_bbox (tuple): 重叠区域边界框 (x_min, y_min, x_max, y_max)
            draw_alignment_box (bool): 是否绘制对齐区域方框
        """
        try:
            fig, ax = plt.subplots(figsize=(10, 8))
            im = ax.imshow(data, cmap=colormap, origin='lower')
            plt.colorbar(im, ax=ax, label='强度')
            ax.set_title(title)

            # 如果需要绘制对齐区域方框
            if draw_alignment_box and overlap_bbox is not None:
                x_min, y_min, x_max, y_max = overlap_bbox
                width = x_max - x_min
                height = y_max - y_min

                # 绘制绿色方框表示对齐区域
                from matplotlib.patches import Rectangle
                rect = Rectangle((x_min, y_min), width, height,
                               linewidth=2, edgecolor='lime', facecolor='none',
                               linestyle='--', label='Alignment Region')
                ax.add_patch(rect)

                # 添加文本标注
                text_x = x_min + 10
                text_y = y_min + 20
                ax.text(text_x, text_y,
                       f'Align Box: ({x_min},{y_min})-({x_max},{y_max})\nSize: {width}x{height}',
                       color='lime', fontsize=9, weight='bold',
                       bbox=dict(boxstyle='round,pad=0.5', facecolor='black', alpha=0.7))

                # 添加图例
                ax.legend(loc='upper right', fontsize=9)

                self.logger.info(f"对齐区域边界框: ({x_min},{y_min})-({x_max},{y_max}), 大小: {width}x{height}")

            plt.tight_layout()
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            self.logger.info(f"JPG文件已保存: {output_path}")
        except Exception as e:
            self.logger.error(f"保存JPG文件失败 {output_path}: {str(e)}")
    
    def create_marked_image(self, image, bright_spots):
        """
        在图像上标记新亮点
        
        Args:
            image (numpy.ndarray): 原始图像
            bright_spots (list): 亮点信息列表
            
        Returns:
            numpy.ndarray: 标记后的图像
        """
        # 标准化图像用于显示
        normalized = self.normalize_image(image)
        
        # 转换为RGB用于标记
        marked_image = cv2.cvtColor((normalized * 255).astype(np.uint8), cv2.COLOR_GRAY2RGB)
        
        # 标记每个亮点
        for i, spot in enumerate(bright_spots):
            x, y = spot['position']
            # 绘制红色圆圈
            cv2.circle(marked_image, (x, y), 10, (255, 0, 0), 2)
            # 添加编号
            cv2.putText(marked_image, str(i+1), (x+15, y-15), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        
        return marked_image
    
    def find_aligned_fits_files(self, directory):
        """
        在指定目录中查找已对齐的FITS文件

        Args:
            directory (str): 目录路径

        Returns:
            tuple: (参考文件路径, 对齐文件路径)
        """
        # 只查找 noise_cleaned_aligned.fits 文件
        noise_cleaned_files = glob.glob(os.path.join(directory, "*noise_cleaned_aligned.fits"))

        if len(noise_cleaned_files) < 2:
            self.logger.error(f"目录中 noise_cleaned_aligned.fits 文件数量不足: {len(noise_cleaned_files)}")
            if noise_cleaned_files:
                for f in noise_cleaned_files:
                    self.logger.error(f"  - {os.path.basename(f)}")
            return None, None

        if len(noise_cleaned_files) > 2:
            self.logger.error(f"目录中 noise_cleaned_aligned.fits 文件数量过多: {len(noise_cleaned_files)}，应该只有2个")
            for f in noise_cleaned_files:
                self.logger.error(f"  - {os.path.basename(f)}")
            return None, None

        # 根据文件名模式识别模板文件和对齐文件
        # K***-*_noise_cleaned_aligned.fits 是模板文件
        # GY*_K***-*_noise_cleaned_aligned.fits 是对齐文件（下载文件）
        template_file = None
        aligned_file = None

        for file_path in noise_cleaned_files:
            filename = os.path.basename(file_path)

            # 判断是模板文件还是对齐文件
            # 模板文件格式: K***-*_noise_cleaned_aligned.fits (以K开头)
            # 对齐文件格式: GY*_K***-*_noise_cleaned_aligned.fits (以GY开头)
            if filename.startswith("K") and not filename.startswith("GY"):
                template_file = file_path
            elif filename.startswith("GY"):
                aligned_file = file_path
            else:
                self.logger.error(f"无法识别文件类型: {filename}")
                self.logger.error(f"模板文件应以 K 开头，对齐文件应以 GY 开头")
                return None, None

        # 检查是否找到了两个文件
        if not template_file or not aligned_file:
            self.logger.error("未找到完整的文件对")
            self.logger.error(f"模板文件: {os.path.basename(template_file) if template_file else '未找到'}")
            self.logger.error(f"对齐文件: {os.path.basename(aligned_file) if aligned_file else '未找到'}")
            return None, None

        self.logger.info("成功识别文件对")
        self.logger.info(f"模板文件: {os.path.basename(template_file)}")
        self.logger.info(f"对齐文件: {os.path.basename(aligned_file)}")

        return template_file, aligned_file

    def run_signal_blob_detector(self, diff_fits_path, output_directory, reference_file=None, aligned_file=None, remove_bright_lines=True, stretch_method='peak', percentile_low=99.95, max_jaggedness_ratio=2.0, fast_mode=False):
        """
        对difference.fits执行signal_blob_detector检测

        Args:
            diff_fits_path: difference.fits文件路径
            output_directory: 输出目录
            reference_file: 参考图像（模板）FITS文件路径
            aligned_file: 对齐图像（下载）FITS文件路径
            remove_bright_lines: 是否去除亮线，默认True
            stretch_method: 拉伸方法，'peak'=峰值拉伸, 'percentile'=百分位数拉伸
            percentile_low: 百分位数起点，默认99.95
            max_jaggedness_ratio: 最大锯齿比率，默认2.0
            fast_mode: 快速模式，不生成hull和poly可视化图片，默认False

        Returns:
            dict: 检测结果信息
        """
        try:
            # 查找signal_blob_detector.py
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(script_dir)
            detector_script = os.path.join(project_root, 'opencv_test', 'signal_blob_detector.py')

            if not os.path.exists(detector_script):
                self.logger.warning(f"未找到signal_blob_detector.py: {detector_script}")
                return None

            # 构建命令
            cmd = [
                sys.executable,
                detector_script,
                diff_fits_path,
                '--threshold', '0.0',
                '--min-area', '1',
                '--max-area', '1000',
                '--min-circularity', '0.79',
                '--max-jaggedness-ratio', str(max_jaggedness_ratio)
            ]

            # 添加去除亮线参数
            if remove_bright_lines:
                cmd.append('--remove-lines')

            # 添加拉伸方法参数
            cmd.extend(['--stretch-method', stretch_method])
            if stretch_method == 'percentile':
                cmd.extend(['--percentile-low', str(percentile_low)])

            # 添加参考图像和对齐图像参数
            if reference_file and os.path.exists(reference_file):
                cmd.extend(['--reference', reference_file])
            if aligned_file and os.path.exists(aligned_file):
                cmd.extend(['--aligned', aligned_file])

            # 添加快速模式参数
            if fast_mode:
                cmd.append('--fast-mode')

            self.logger.info(f"执行命令: {' '.join(cmd)}")

            # 执行检测
            result = subprocess.run(
                cmd,
                cwd=output_directory,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # 遇到无法解码的字符时替换为?
                timeout=300  # 5分钟超时
            )

            if result.returncode == 0:
                self.logger.info("signal_blob_detector检测完成")
                # 从输出中提取检测数量
                output_lines = result.stdout.split('\n')
                for line in output_lines:
                    if '过滤后剩余' in line and '个斑点' in line:
                        self.logger.info(f"  {line.strip()}")
                return {'success': True, 'output': result.stdout}
            else:
                self.logger.error(f"signal_blob_detector执行失败: {result.stderr}")
                return {'success': False, 'error': result.stderr}

        except subprocess.TimeoutExpired:
            self.logger.error("signal_blob_detector执行超时")
            return {'success': False, 'error': 'Timeout'}
        except Exception as e:
            self.logger.error(f"执行signal_blob_detector时出错: {str(e)}")
            return {'success': False, 'error': str(e)}

    def process_aligned_fits_comparison(self, input_directory, output_directory=None, remove_bright_lines=True, stretch_method='peak', percentile_low=99.95, fast_mode=False, max_jaggedness_ratio=2.0):
        """
        处理已对齐FITS文件的差异比较

        Args:
            input_directory (str): 输入目录路径
            output_directory (str): 输出目录路径
            remove_bright_lines (bool): 是否去除亮线，默认True
            stretch_method (str): 拉伸方法，'peak'=峰值拉伸, 'percentile'=百分位数拉伸
            percentile_low (float): 百分位数起点，默认99.95
            fast_mode (bool): 快速模式，减少中间文件输出，默认False
            max_jaggedness_ratio (float): 最大锯齿比率，默认2.0

        Returns:
            dict: 处理结果信息
        """
        # 设置输出目录
        if output_directory is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_directory = f"aligned_diff_results_{timestamp}"

        os.makedirs(output_directory, exist_ok=True)

        # 查找FITS文件
        reference_file, aligned_file = self.find_aligned_fits_files(input_directory)
        if not reference_file or not aligned_file:
            return None

        # 加载FITS数据
        self.logger.info("加载FITS文件...")
        ref_data = self.load_fits_data(reference_file)
        aligned_data = self.load_fits_data(aligned_file)

        if ref_data is None or aligned_data is None:
            self.logger.error("FITS文件加载失败")
            return None

        # 检查图像尺寸
        if ref_data.shape != aligned_data.shape:
            self.logger.error(f"图像尺寸不匹配: {ref_data.shape} vs {aligned_data.shape}")
            return None

        # 执行差异检测
        self.logger.info("执行差异检测...")
        diff_image, binary_diff, bright_spots, overlap_mask = self.detect_differences(ref_data, aligned_data)

        # 创建标记图像
        marked_image = self.create_marked_image(aligned_data, bright_spots)

        # 应用重叠掩码到所有输出图像（确保非重叠区域为黑色）
        self.logger.info("应用重叠掩码，确保非重叠区域为黑色...")
        ref_data = ref_data * overlap_mask
        aligned_data = aligned_data * overlap_mask

        # 生成输出文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"aligned_comparison_{timestamp}"

        # 保存FITS格式结果
        self.logger.info("保存FITS格式结果...")

        # 保存差异图像（FITS）
        diff_fits_path = os.path.join(output_directory, f"{base_name}_difference.fits")
        self.save_fits_result(diff_image, diff_fits_path)

        # 初始化文件路径变量（快速模式下可能不会创建这些文件）
        binary_fits_path = None
        marked_fits_path = None
        overlap_mask_fits_path = None
        ref_jpg_path = None
        aligned_jpg_path = None
        diff_jpg_path = None
        binary_jpg_path = None
        overlap_mask_jpg_path = None
        marked_jpg_path = None
        spots_txt_path = None

        # 快速模式：跳过大部分中间文件保存
        if not fast_mode:
            # 保存二值化差异图像（FITS）
            binary_fits_path = os.path.join(output_directory, f"{base_name}_binary_diff.fits")
            self.save_fits_result(binary_diff.astype(np.float32), binary_fits_path)

            # 保存标记图像（FITS）
            marked_fits_path = os.path.join(output_directory, f"{base_name}_marked.fits")
            # 将RGB图像转换为灰度用于FITS保存
            marked_gray = cv2.cvtColor(marked_image, cv2.COLOR_RGB2GRAY)
            self.save_fits_result(marked_gray.astype(np.float32), marked_fits_path)

            # 保存重叠掩码（FITS）
            overlap_mask_fits_path = os.path.join(output_directory, f"{base_name}_overlap_mask.fits")
            self.save_fits_result(overlap_mask.astype(np.float32), overlap_mask_fits_path)

        # 计算重叠区域边界框用于调试可视化
        self.logger.info("计算对齐区域边界框...")
        overlap_bbox = self.get_overlap_bounding_box(overlap_mask)

        if not fast_mode:
            # 保存JPG格式结果
            self.logger.info("保存JPG格式结果（包含对齐区域调试信息）...")

            # 保存参考图像（JPG）- 带对齐区域方框
            ref_jpg_path = os.path.join(output_directory, f"{base_name}_reference.jpg")
            self.save_jpg_result(self.normalize_image(ref_data), ref_jpg_path,
                               "参考图像（非重叠区域已设为黑色）", 'gray',
                               overlap_bbox=overlap_bbox, draw_alignment_box=True)

            # 保存对齐图像（JPG）- 带对齐区域方框
            aligned_jpg_path = os.path.join(output_directory, f"{base_name}_aligned.jpg")
            self.save_jpg_result(self.normalize_image(aligned_data), aligned_jpg_path,
                               "对齐图像（非重叠区域已设为黑色）", 'gray',
                               overlap_bbox=overlap_bbox, draw_alignment_box=True)

            # 保存差异图像（JPG）- 带对齐区域方框
            diff_jpg_path = os.path.join(output_directory, f"{base_name}_difference.jpg")
            self.save_jpg_result(diff_image, diff_jpg_path,
                               "差异图像（仅重叠区域）", 'hot',
                               overlap_bbox=overlap_bbox, draw_alignment_box=True)

            # 保存二值化差异图像（JPG）- 带对齐区域方框
            binary_jpg_path = os.path.join(output_directory, f"{base_name}_binary_diff.jpg")
            self.save_jpg_result(binary_diff, binary_jpg_path,
                               "二值化差异图像（仅重叠区域）", 'gray',
                               overlap_bbox=overlap_bbox, draw_alignment_box=True)

            # 保存重叠掩码（JPG）- 带对齐区域方框
            overlap_mask_jpg_path = os.path.join(output_directory, f"{base_name}_overlap_mask.jpg")
            self.save_jpg_result(overlap_mask, overlap_mask_jpg_path,
                               "重叠区域掩码（白色=重叠，黑色=非重叠）", 'gray',
                               overlap_bbox=overlap_bbox, draw_alignment_box=True)

            # 保存标记图像（JPG）- 带对齐区域方框
            marked_jpg_path = os.path.join(output_directory, f"{base_name}_marked.jpg")
            fig, ax = plt.subplots(figsize=(10, 8))
            ax.imshow(marked_image, origin='lower')
            ax.set_title(f"标记新亮点图像 (共{len(bright_spots)}个)")
            ax.axis('off')

            # 在标记图像上也绘制对齐区域方框
            if overlap_bbox is not None:
                x_min, y_min, x_max, y_max = overlap_bbox
                width = x_max - x_min
                height = y_max - y_min
                from matplotlib.patches import Rectangle
                rect = Rectangle((x_min, y_min), width, height,
                               linewidth=2, edgecolor='lime', facecolor='none',
                               linestyle='--', label='Alignment Region')
                ax.add_patch(rect)
                ax.legend(loc='upper right', fontsize=9)

            plt.tight_layout()
            plt.savefig(marked_jpg_path, dpi=150, bbox_inches='tight')
            plt.close()

            # 保存亮点详情
            spots_txt_path = os.path.join(output_directory, f"{base_name}_bright_spots.txt")
            with open(spots_txt_path, 'w', encoding='utf-8') as f:
                f.write(f"已对齐FITS文件差异检测结果\n")
                f.write(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"参考文件: {os.path.basename(reference_file)}\n")
                f.write(f"对齐文件: {os.path.basename(aligned_file)}\n")
                f.write(f"检测到新亮点数量: {len(bright_spots)}\n\n")

                if bright_spots:
                    f.write("新亮点详情:\n")
                    f.write("-" * 50 + "\n")
                    for i, spot in enumerate(bright_spots):
                        f.write(f"亮点 #{i+1}:\n")
                        f.write(f"  位置: {spot['position']}\n")
                        f.write(f"  面积: {spot['area']:.1f} 像素\n")
                        f.write("\n")
        else:
            self.logger.info("快速模式：跳过中间文件保存")

        # 执行signal_blob_detector检测
        self.logger.info("执行signal_blob_detector检测...")
        blob_detection_result = self.run_signal_blob_detector(
            diff_fits_path, output_directory,
            reference_file=reference_file,
            aligned_file=aligned_file,
            remove_bright_lines=remove_bright_lines,
            stretch_method=stretch_method,
            percentile_low=percentile_low,
            max_jaggedness_ratio=max_jaggedness_ratio,
            fast_mode=fast_mode
        )

        # 快速模式：检测完成后删除差异FITS文件
        if fast_mode and os.path.exists(diff_fits_path):
            try:
                os.remove(diff_fits_path)
                self.logger.info(f"快速模式：已删除中间文件 {os.path.basename(diff_fits_path)}")
                diff_fits_path = None  # 标记为已删除
            except Exception as e:
                self.logger.warning(f"快速模式：删除中间文件失败: {e}")

        # 返回处理结果
        output_files = {
            'fits': {},
            'jpg': {}
        }

        # 只包含实际存在的文件
        if diff_fits_path:  # 快速模式下可能已被删除
            output_files['fits']['difference'] = diff_fits_path
        if binary_fits_path:
            output_files['fits']['binary_diff'] = binary_fits_path
        if marked_fits_path:
            output_files['fits']['marked'] = marked_fits_path
        if overlap_mask_fits_path:
            output_files['fits']['overlap_mask'] = overlap_mask_fits_path
        if ref_jpg_path:
            output_files['jpg']['reference'] = ref_jpg_path
        if aligned_jpg_path:
            output_files['jpg']['aligned'] = aligned_jpg_path
        if diff_jpg_path:
            output_files['jpg']['difference'] = diff_jpg_path
        if binary_jpg_path:
            output_files['jpg']['binary_diff'] = binary_jpg_path
        if marked_jpg_path:
            output_files['jpg']['marked'] = marked_jpg_path
        if overlap_mask_jpg_path:
            output_files['jpg']['overlap_mask'] = overlap_mask_jpg_path
        if spots_txt_path:
            output_files['text'] = spots_txt_path

        result = {
            'success': True,
            'reference_file': reference_file,
            'aligned_file': aligned_file,
            'output_directory': output_directory,
            'new_bright_spots': len(bright_spots),
            'bright_spots_details': bright_spots,
            'blob_detection': blob_detection_result,
            'output_files': output_files,
            'fast_mode': fast_mode
        }

        return result


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='已对齐FITS文件差异比较工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 使用默认输入目录
  python compare_aligned_fits.py

  # 指定输入目录
  python compare_aligned_fits.py --input E:\\fix_data\\align-diff

  # 指定输入和输出目录
  python compare_aligned_fits.py --input E:\\fix_data\\align-diff --output results
        """
    )

    parser.add_argument('--input', '-i', default=r'E:\fix_data\align-diff',
                       help='包含已对齐FITS文件的输入目录')
    parser.add_argument('--output', '-o',
                       help='输出目录（默认自动生成时间戳目录）')
    parser.add_argument('--threshold', '-t', type=float, default=0.0,
                       help='差异检测阈值（默认0.0）')
    parser.add_argument('--gaussian-sigma', '-g', type=float, default=1.0,
                       help='高斯模糊参数（默认1.0）')

    args = parser.parse_args()

    # 检查输入目录
    if not os.path.exists(args.input):
        print(f"错误: 输入目录不存在 - {args.input}")
        sys.exit(1)

    # 创建比较器
    comparator = AlignedFITSComparator()

    # 更新参数
    comparator.diff_params['diff_threshold'] = args.threshold
    comparator.diff_params['gaussian_sigma'] = args.gaussian_sigma

    print("=" * 60)
    print("已对齐FITS文件差异比较工具")
    print("=" * 60)
    print(f"输入目录: {args.input}")
    print(f"输出目录: {args.output or '自动生成'}")
    print(f"差异阈值: {args.threshold}")
    print(f"高斯模糊: {args.gaussian_sigma}")
    print("=" * 60)

    # 执行比较
    try:
        result = comparator.process_aligned_fits_comparison(args.input, args.output)

        if result and result['success']:
            print("\n处理完成！")
            print("=" * 60)
            print(f"参考文件: {os.path.basename(result['reference_file'])}")
            print(f"对齐文件: {os.path.basename(result['aligned_file'])}")
            print(f"检测到新亮点: {result['new_bright_spots']} 个")

            if result['bright_spots_details']:
                print("\n新亮点详情:")
                for i, spot in enumerate(result['bright_spots_details']):
                    print(f"  #{i+1}: 位置{spot['position']}, 面积{spot['area']:.1f}像素")

            print(f"\n输出文件已保存到: {result['output_directory']}")
            print("\nFITS格式文件:")
            for name, path in result['output_files']['fits'].items():
                print(f"  {name}: {os.path.basename(path)}")

            print("\nJPG格式文件:")
            for name, path in result['output_files']['jpg'].items():
                print(f"  {name}: {os.path.basename(path)}")

        else:
            print("处理失败！请检查日志文件了解详细错误信息。")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n用户中断处理")
        sys.exit(1)
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()