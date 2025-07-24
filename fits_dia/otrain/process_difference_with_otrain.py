#!/usr/bin/env python3
"""
使用dcorre otrain方法处理FITS差异图像
基于O'TRAIN: Optical TRAnsient Identification NEtwork
参考: https://github.com/dcorre/otrain
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from astropy.io import fits
from astropy.visualization import ZScaleInterval, ImageNormalize
import logging
from datetime import datetime
import argparse
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OTrainProcessor:
    """
    使用O'TRAIN方法处理FITS差异图像的处理器
    """
    
    def __init__(self, output_dir=None):
        """
        初始化处理器
        
        Args:
            output_dir (str): 输出目录路径
        """
        self.output_dir = output_dir or "otrain_results"
        self.setup_output_directory()
        
        # O'TRAIN相关参数
        self.cutout_size = 32  # 标准cutout大小
        self.detection_threshold = 2.5  # 检测阈值 (降低以增加灵敏度)
        self.min_area = 3  # 最小区域面积 (降低以检测更小的候选天体)
        
        logger.info(f"O'TRAIN处理器初始化完成，输出目录: {self.output_dir}")
    
    def setup_output_directory(self):
        """创建输出目录"""
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"输出目录已创建: {self.output_dir}")
    
    def load_fits_image(self, fits_path):
        """
        加载FITS图像
        
        Args:
            fits_path (str): FITS文件路径
            
        Returns:
            tuple: (图像数据, 头信息, 是否成功)
        """
        try:
            logger.info(f"加载FITS文件: {fits_path}")
            
            with fits.open(fits_path) as hdul:
                header = hdul[0].header
                image_data = hdul[0].data
                
                if image_data is None:
                    logger.error(f"无法读取图像数据: {fits_path}")
                    return None, None, False
                
                # 转换数据类型
                image_data = image_data.astype(np.float64)
                
                # 处理可能的3D数据（取第一个通道）
                if len(image_data.shape) == 3:
                    image_data = image_data[0]
                
                logger.info(f"图像加载成功: {image_data.shape}")
                logger.info(f"数据范围: [{np.min(image_data):.6f}, {np.max(image_data):.6f}]")
                
                return image_data, header, True
                
        except Exception as e:
            logger.error(f"加载FITS文件时出错 {fits_path}: {str(e)}")
            return None, None, False
    
    def detect_candidates(self, image_data):
        """
        检测候选瞬变天体
        
        Args:
            image_data (np.ndarray): 图像数据
            
        Returns:
            list: 候选天体位置列表 [(x, y, flux), ...]
        """
        try:
            logger.info("开始检测候选瞬变天体...")
            
            # 计算图像统计信息
            mean_val = np.mean(image_data)
            std_val = np.std(image_data)
            threshold = mean_val + self.detection_threshold * std_val
            
            logger.info(f"检测阈值: {threshold:.6f} (mean={mean_val:.6f}, std={std_val:.6f})")
            
            # 简单的阈值检测
            mask = image_data > threshold
            
            # 查找连通区域
            from scipy import ndimage
            labeled_array, num_features = ndimage.label(mask)
            
            candidates = []
            
            for i in range(1, num_features + 1):
                # 获取每个连通区域的信息
                region_mask = labeled_array == i
                region_size = np.sum(region_mask)
                
                if region_size >= self.min_area:
                    # 计算质心
                    y_coords, x_coords = np.where(region_mask)
                    center_x = np.mean(x_coords)
                    center_y = np.mean(y_coords)
                    
                    # 计算总流量
                    total_flux = np.sum(image_data[region_mask])
                    
                    candidates.append((center_x, center_y, total_flux, region_size))
            
            logger.info(f"检测到 {len(candidates)} 个候选天体")
            return candidates
            
        except Exception as e:
            logger.error(f"检测候选天体时出错: {str(e)}")
            return []
    
    def extract_cutouts(self, image_data, candidates):
        """
        提取候选天体的cutout图像
        
        Args:
            image_data (np.ndarray): 原始图像数据
            candidates (list): 候选天体列表
            
        Returns:
            list: cutout图像列表
        """
        try:
            logger.info(f"提取 {len(candidates)} 个cutout图像...")
            
            cutouts = []
            half_size = self.cutout_size // 2
            
            for i, (center_x, center_y, flux, size) in enumerate(candidates):
                # 计算cutout边界
                x_min = max(0, int(center_x - half_size))
                x_max = min(image_data.shape[1], int(center_x + half_size))
                y_min = max(0, int(center_y - half_size))
                y_max = min(image_data.shape[0], int(center_y + half_size))
                
                # 提取cutout
                cutout = image_data[y_min:y_max, x_min:x_max]
                
                # 确保cutout大小一致（填充或裁剪）
                if cutout.shape != (self.cutout_size, self.cutout_size):
                    # 创建标准大小的cutout
                    standard_cutout = np.zeros((self.cutout_size, self.cutout_size))
                    
                    # 计算放置位置
                    start_y = (self.cutout_size - cutout.shape[0]) // 2
                    start_x = (self.cutout_size - cutout.shape[1]) // 2
                    end_y = start_y + cutout.shape[0]
                    end_x = start_x + cutout.shape[1]
                    
                    standard_cutout[start_y:end_y, start_x:end_x] = cutout
                    cutout = standard_cutout
                
                cutouts.append({
                    'image': cutout,
                    'center': (center_x, center_y),
                    'flux': flux,
                    'size': size,
                    'id': i
                })
            
            logger.info(f"成功提取 {len(cutouts)} 个cutout图像")
            return cutouts
            
        except Exception as e:
            logger.error(f"提取cutout时出错: {str(e)}")
            return []
    
    def simulate_otrain_classification(self, cutouts):
        """
        模拟O'TRAIN CNN分类
        (实际使用时需要加载训练好的模型)
        
        Args:
            cutouts (list): cutout图像列表
            
        Returns:
            list: 分类结果列表
        """
        try:
            logger.info("开始模拟O'TRAIN分类...")
            
            results = []
            
            for cutout_data in cutouts:
                cutout = cutout_data['image']
                
                # 模拟CNN分类逻辑
                # 实际使用时这里会调用训练好的CNN模型
                
                # 简单的特征计算作为模拟
                max_val = np.max(cutout)
                mean_val = np.mean(cutout)
                std_val = np.std(cutout)
                
                # 模拟分类得分 (0-1之间，1表示真实瞬变天体)
                # 这里使用简单的启发式规则作为示例
                if max_val > mean_val + 3 * std_val and std_val > 0.1:
                    score = min(0.9, max_val / (mean_val + 3 * std_val))
                else:
                    score = 0.1
                
                # 分类结果
                classification = "real" if score > 0.5 else "bogus"
                
                results.append({
                    'id': cutout_data['id'],
                    'center': cutout_data['center'],
                    'flux': cutout_data['flux'],
                    'size': cutout_data['size'],
                    'score': score,
                    'classification': classification,
                    'cutout': cutout
                })
            
            real_count = sum(1 for r in results if r['classification'] == 'real')
            logger.info(f"分类完成: {real_count}/{len(results)} 个被分类为真实瞬变天体")
            
            return results
            
        except Exception as e:
            logger.error(f"分类时出错: {str(e)}")
            return []
    
    def save_results(self, image_data, results, fits_path, header):
        """
        保存处理结果

        Args:
            image_data (np.ndarray): 原始图像数据
            results (list): 分类结果
            fits_path (str): 原始FITS文件路径
            header: FITS头信息
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = Path(fits_path).stem

            # 保存结果文本文件
            results_file = os.path.join(self.output_dir, f"{base_name}_otrain_results_{timestamp}.txt")
            with open(results_file, 'w', encoding='utf-8') as f:
                f.write("O'TRAIN处理结果\n")
                f.write("="*50 + "\n")
                f.write(f"输入文件: {fits_path}\n")
                f.write(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"总候选数: {len(results)}\n")

                real_candidates = [r for r in results if r['classification'] == 'real']
                f.write(f"真实瞬变天体: {len(real_candidates)}\n\n")

                f.write("详细结果:\n")
                f.write("-"*50 + "\n")
                for result in results:
                    f.write(f"ID: {result['id']}\n")
                    f.write(f"位置: ({result['center'][0]:.2f}, {result['center'][1]:.2f})\n")
                    f.write(f"流量: {result['flux']:.2f}\n")
                    f.write(f"大小: {result['size']} 像素\n")
                    f.write(f"分类得分: {result['score']:.3f}\n")
                    f.write(f"分类结果: {result['classification']}\n")
                    f.write("-"*30 + "\n")

            logger.info(f"结果已保存到: {results_file}")

            # 创建可视化图像
            self.create_visualization(image_data, results, base_name, timestamp)

            # 创建带标记的FITS文件
            self.create_marked_fits(image_data, results, fits_path, header, base_name, timestamp)

        except Exception as e:
            logger.error(f"保存结果时出错: {str(e)}")
    
    def create_visualization(self, image_data, results, base_name, timestamp):
        """
        创建可视化图像
        
        Args:
            image_data (np.ndarray): 原始图像数据
            results (list): 分类结果
            base_name (str): 基础文件名
            timestamp (str): 时间戳
        """
        try:
            # 创建图像显示
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            fig.suptitle(f'O\'TRAIN处理结果 - {base_name}', fontsize=16)
            
            # 图像归一化
            norm = ImageNormalize(image_data, interval=ZScaleInterval())
            
            # 1. 原始图像
            ax1 = axes[0, 0]
            im1 = ax1.imshow(image_data, cmap='gray', norm=norm, origin='lower')
            ax1.set_title('原始差异图像')
            ax1.set_xlabel('X (像素)')
            ax1.set_ylabel('Y (像素)')
            plt.colorbar(im1, ax=ax1)
            
            # 2. 标记所有候选天体
            ax2 = axes[0, 1]
            im2 = ax2.imshow(image_data, cmap='gray', norm=norm, origin='lower')
            for result in results:
                x, y = result['center']
                color = 'red' if result['classification'] == 'real' else 'blue'
                ax2.plot(x, y, 'o', color=color, markersize=8, fillstyle='none', linewidth=2)
                ax2.text(x+2, y+2, f"{result['id']}", color=color, fontsize=8)
            ax2.set_title('所有候选天体 (红色=真实, 蓝色=虚假)')
            ax2.set_xlabel('X (像素)')
            ax2.set_ylabel('Y (像素)')
            
            # 3. 只显示真实瞬变天体
            ax3 = axes[1, 0]
            im3 = ax3.imshow(image_data, cmap='gray', norm=norm, origin='lower')
            real_candidates = [r for r in results if r['classification'] == 'real']
            for result in real_candidates:
                x, y = result['center']
                ax3.plot(x, y, 'ro', markersize=10, fillstyle='none', linewidth=2)
                ax3.text(x+2, y+2, f"ID:{result['id']}\nScore:{result['score']:.2f}", 
                        color='red', fontsize=8, bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7))
            ax3.set_title(f'真实瞬变天体 ({len(real_candidates)}个)')
            ax3.set_xlabel('X (像素)')
            ax3.set_ylabel('Y (像素)')
            
            # 4. 分类得分分布
            ax4 = axes[1, 1]
            scores = [r['score'] for r in results]
            ax4.hist(scores, bins=20, alpha=0.7, edgecolor='black')
            ax4.axvline(x=0.5, color='red', linestyle='--', label='分类阈值')
            ax4.set_xlabel('分类得分')
            ax4.set_ylabel('候选天体数量')
            ax4.set_title('分类得分分布')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # 保存图像
            viz_file = os.path.join(self.output_dir, f"{base_name}_otrain_visualization_{timestamp}.png")
            plt.savefig(viz_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"可视化图像已保存到: {viz_file}")
            
        except Exception as e:
            logger.error(f"创建可视化时出错: {str(e)}")

    def create_marked_fits(self, image_data, results, fits_path, header, base_name, timestamp):
        """
        创建带有圆圈标记的FITS文件

        Args:
            image_data (np.ndarray): 原始图像数据
            results (list): 分类结果
            fits_path (str): 原始FITS文件路径
            header: FITS头信息
            base_name (str): 基础文件名
            timestamp (str): 时间戳
        """
        try:
            logger.info("创建带标记的FITS文件...")

            # 复制原始图像数据
            marked_image = image_data.copy()

            # 为每个候选天体绘制圆圈标记
            for result in results:
                center_x, center_y = result['center']
                size = result['size']
                classification = result['classification']

                # 根据像素数计算圆圈半径 - 增大圆圈直径
                # 使用更大的倍数，确保圆圈更明显
                radius = max(8, int(np.sqrt(size / np.pi) * 3.0))  # 从1.5增加到3.0，最小半径从3增加到8

                # 根据分类结果设置标记强度和样式
                if classification == 'real':
                    # 真实瞬变天体使用更强的标记，绘制实心圆圈
                    mark_intensity = np.max(image_data) * 1.2  # 增强亮度
                    self._draw_circle(marked_image, int(center_x), int(center_y), radius, mark_intensity, style='solid')
                else:
                    # 虚假检测使用较弱的标记，绘制虚线圆圈
                    mark_intensity = np.max(image_data) * 0.6  # 适中亮度
                    self._draw_circle(marked_image, int(center_x), int(center_y), radius, mark_intensity, style='dashed')

            # 创建新的FITS头信息
            new_header = header.copy()
            new_header['HISTORY'] = f'O\'TRAIN processed on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            new_header['HISTORY'] = f'Detected {len(results)} candidates'
            real_count = sum(1 for r in results if r['classification'] == 'real')
            new_header['HISTORY'] = f'Identified {real_count} real transients'
            new_header['OTRAIN'] = 'T'
            new_header['OTCANDS'] = len(results)
            new_header['OTREALS'] = real_count

            # 保存带标记的FITS文件
            marked_fits_file = os.path.join(self.output_dir, f"{base_name}_otrain_marked_{timestamp}.fits")

            # 创建HDU并保存
            hdu = fits.PrimaryHDU(data=marked_image, header=new_header)
            hdu.writeto(marked_fits_file, overwrite=True)

            logger.info(f"带标记的FITS文件已保存到: {marked_fits_file}")

        except Exception as e:
            logger.error(f"创建带标记FITS文件时出错: {str(e)}")

    def _draw_circle(self, image, center_x, center_y, radius, intensity, style='solid'):
        """
        在图像上绘制圆圈（优化版本，只在局部区域工作）

        Args:
            image (np.ndarray): 图像数据
            center_x (int): 圆心X坐标
            center_y (int): 圆心Y坐标
            radius (int): 圆圈半径
            intensity (float): 标记强度
            style (str): 圆圈样式，'solid'为实线，'dashed'为虚线
        """
        try:
            height, width = image.shape

            # 边界检查
            if center_x < 0 or center_x >= width or center_y < 0 or center_y >= height:
                return

            # 只在圆圈周围的局部区域工作，提高效率
            margin = radius + 3
            x_min = max(0, center_x - margin)
            x_max = min(width, center_x + margin + 1)
            y_min = max(0, center_y - margin)
            y_max = min(height, center_y + margin + 1)

            # 创建局部坐标网格
            y_local, x_local = np.ogrid[y_min:y_max, x_min:x_max]

            # 计算到圆心的距离
            distance = np.sqrt((x_local - center_x)**2 + (y_local - center_y)**2)

            if style == 'solid':
                # 实心圆圈（用于real分类）- 更细的线条
                inner_radius = max(1, radius - 0.5)  # 减小线条粗细
                outer_radius = radius + 0.5
                circle_mask = (distance >= inner_radius) & (distance <= outer_radius)

                # 应用圆圈到局部区域
                image[y_min:y_max, x_min:x_max][circle_mask] = intensity

                # 在圆心添加一个小点作为中心标记
                center_mask = distance <= 1.5
                image[y_min:y_max, x_min:x_max][center_mask] = intensity * 0.8

            elif style == 'dashed':
                # 虚线圆圈（用于bogus分类）- 更细的线条
                inner_radius = max(1, radius - 0.5)  # 减小线条粗细
                outer_radius = radius + 0.5
                circle_mask = (distance >= inner_radius) & (distance <= outer_radius)

                # 创建虚线效果：只在特定角度范围内绘制
                angle = np.arctan2(y_local - center_y, x_local - center_x)
                # 将角度转换为0-2π范围
                angle = (angle + 2 * np.pi) % (2 * np.pi)

                # 创建虚线模式：每π/4弧度绘制，每π/4弧度空白
                dash_pattern = ((angle % (np.pi/2)) < (np.pi/4))

                # 应用虚线圆圈到局部区域
                dashed_mask = circle_mask & dash_pattern
                image[y_min:y_max, x_min:x_max][dashed_mask] = intensity

        except Exception as e:
            logger.error(f"绘制圆圈时出错: {str(e)}")

    def process_fits_file(self, fits_path):
        """
        处理FITS文件的主要方法
        
        Args:
            fits_path (str): FITS文件路径
            
        Returns:
            dict: 处理结果摘要
        """
        try:
            logger.info("="*60)
            logger.info("开始O'TRAIN处理")
            logger.info("="*60)
            
            # 1. 加载FITS文件
            image_data, header, success = self.load_fits_image(fits_path)
            if not success:
                return None
            
            # 2. 检测候选天体
            candidates = self.detect_candidates(image_data)
            if not candidates:
                logger.warning("未检测到任何候选天体")
                return {"candidates": 0, "real_transients": 0}
            
            # 3. 提取cutout
            cutouts = self.extract_cutouts(image_data, candidates)
            if not cutouts:
                logger.warning("未能提取任何cutout")
                return {"candidates": len(candidates), "real_transients": 0}
            
            # 4. CNN分类
            results = self.simulate_otrain_classification(cutouts)
            if not results:
                logger.warning("分类失败")
                return {"candidates": len(candidates), "real_transients": 0}
            
            # 5. 保存结果
            self.save_results(image_data, results, fits_path, header)
            
            # 统计结果
            real_count = sum(1 for r in results if r['classification'] == 'real')
            
            summary = {
                "candidates": len(candidates),
                "real_transients": real_count,
                "classification_results": results
            }
            
            logger.info("="*60)
            logger.info("O'TRAIN处理完成")
            logger.info(f"候选天体: {len(candidates)}")
            logger.info(f"真实瞬变天体: {real_count}")
            logger.info("="*60)
            
            return summary
            
        except Exception as e:
            logger.error(f"处理FITS文件时出错: {str(e)}")
            return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="使用O'TRAIN方法处理FITS差异图像")
    parser.add_argument('fits_file', help='FITS文件路径')
    parser.add_argument('--output-dir', '-o', help='输出目录路径')
    parser.add_argument('--cutout-size', type=int, default=32, help='Cutout大小 (默认: 32)')
    parser.add_argument('--threshold', type=float, default=2.5, help='检测阈值 (默认: 2.5, 更低=更敏感)')
    parser.add_argument('--min-area', type=int, default=3, help='最小区域面积 (默认: 3, 更低=检测更小目标)')
    
    args = parser.parse_args()
    
    # 检查输入文件
    if not os.path.exists(args.fits_file):
        logger.error(f"输入文件不存在: {args.fits_file}")
        sys.exit(1)
    
    # 创建处理器
    processor = OTrainProcessor(output_dir=args.output_dir)
    processor.cutout_size = args.cutout_size
    processor.detection_threshold = args.threshold
    processor.min_area = args.min_area
    
    # 处理文件
    result = processor.process_fits_file(args.fits_file)
    
    if result:
        print(f"\n处理完成!")
        print(f"检测到候选天体: {result['candidates']}")
        print(f"真实瞬变天体: {result['real_transients']}")
        print(f"结果已保存到: {processor.output_dir}")
    else:
        print("处理失败!")
        sys.exit(1)


if __name__ == "__main__":
    main()
