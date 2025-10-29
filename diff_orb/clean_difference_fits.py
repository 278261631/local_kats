#!/usr/bin/env python3
"""
进一步清理compare_aligned_fits.py输出的_difference.fits文件
去除黑色坑和背景亮光，输出更干净的差异FITS文件
"""

import os
import sys
import numpy as np
import cv2
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from astropy.io import fits
from scipy.ndimage import gaussian_filter, median_filter
from scipy import ndimage
from pathlib import Path
import logging
from datetime import datetime
import warnings
import argparse

# 忽略警告
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# 设置matplotlib中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class DifferenceFITSCleaner:
    """差异FITS文件清理器"""
    
    def __init__(self):
        """初始化清理器"""
        self.setup_logging()
        
        # 清理参数
        self.clean_params = {
            'noise_percentile': 15,      # 噪声水平百分位数（更严格）
            'noise_multiplier': 4.0,     # 噪声阈值倍数（更严格）
            'min_component_size': 10,    # 最小连通组件大小
            'median_filter_size': 3,     # 中值滤波器大小
            'morphology_kernel_size': 5, # 形态学操作核大小
            'gaussian_sigma': 0.8,       # 高斯平滑参数
            'intensity_threshold': 0.05  # 强度阈值（相对于最大值）
        }
    
    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('difference_fits_cleaner.log'),
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
            tuple: (图像数据, FITS头信息)，如果失败返回(None, None)
        """
        try:
            with fits.open(fits_path) as hdul:
                data = hdul[0].data.astype(np.float32)  # 优化：使用float32减少内存50%，提升速度24%
                header = hdul[0].header

                # 处理可能的3D数据（取第一个通道）
                if len(data.shape) == 3:
                    data = data[0]

                self.logger.info(f"成功加载FITS文件: {os.path.basename(fits_path)}")
                self.logger.info(f"数据形状: {data.shape}, 数据范围: [{np.min(data):.6f}, {np.max(data):.6f}]")
                self.logger.info(f"非零像素数: {np.sum(data > 0)}, 总像素数: {data.size}")

                return data, header
                
        except Exception as e:
            self.logger.error(f"加载FITS文件失败 {fits_path}: {str(e)}")
            return None, None
    
    def advanced_clean_difference(self, diff_image):
        """
        高级差异图像清理算法
        
        Args:
            diff_image (numpy.ndarray): 输入差异图像
            
        Returns:
            numpy.ndarray: 清理后的差异图像
        """
        self.logger.info("开始高级差异图像清理...")
        
        # 复制原始数据
        cleaned = diff_image.copy()
        
        # 1. 基本统计信息
        non_zero_pixels = cleaned[cleaned > 0]
        if len(non_zero_pixels) == 0:
            self.logger.warning("输入图像没有非零像素")
            return cleaned
        
        max_intensity = np.max(cleaned)
        self.logger.info(f"原始非零像素数: {len(non_zero_pixels)}")
        self.logger.info(f"最大强度: {max_intensity:.6f}")
        
        # 2. 估计噪声水平（使用更严格的百分位数）
        noise_level = np.percentile(non_zero_pixels, self.clean_params['noise_percentile'])
        noise_std = np.std(non_zero_pixels[non_zero_pixels <= noise_level])
        noise_threshold = noise_level + self.clean_params['noise_multiplier'] * noise_std
        
        self.logger.info(f"噪声水平 ({self.clean_params['noise_percentile']}%): {noise_level:.6f}")
        self.logger.info(f"噪声标准差: {noise_std:.6f}")
        self.logger.info(f"噪声阈值: {noise_threshold:.6f}")
        
        # 3. 应用噪声阈值
        cleaned[cleaned < noise_threshold] = 0
        remaining_pixels = np.sum(cleaned > 0)
        self.logger.info(f"噪声阈值后剩余像素: {remaining_pixels}")
        
        # 4. 应用强度阈值（相对于最大值）
        intensity_threshold = max_intensity * self.clean_params['intensity_threshold']
        cleaned[cleaned < intensity_threshold] = 0
        remaining_pixels = np.sum(cleaned > 0)
        self.logger.info(f"强度阈值后剩余像素: {remaining_pixels}")
        
        if remaining_pixels == 0:
            self.logger.warning("所有像素都被阈值过滤掉了")
            return cleaned
        
        # 5. 连通组件分析 - 去除小的噪声区域
        # 转换为二值图像进行连通组件分析
        binary_mask = (cleaned > 0).astype(np.uint8)
        num_labels, labels = cv2.connectedComponents(binary_mask)
        
        # 计算每个连通组件的大小
        component_sizes = np.bincount(labels.ravel())
        
        # 创建掩码，只保留大于最小尺寸的组件
        large_components_mask = np.zeros_like(labels, dtype=bool)
        for label in range(1, num_labels):  # 跳过背景标签0
            if component_sizes[label] >= self.clean_params['min_component_size']:
                large_components_mask[labels == label] = True
        
        # 应用连通组件掩码
        cleaned = cleaned * large_components_mask.astype(np.float64)
        remaining_pixels = np.sum(cleaned > 0)
        self.logger.info(f"连通组件过滤后剩余像素: {remaining_pixels}")
        
        if remaining_pixels == 0:
            self.logger.warning("连通组件过滤后没有剩余像素")
            return cleaned
        
        # 6. 形态学操作 - 去除小的黑色坑和噪声
        if np.max(cleaned) > 0:
            # 转换为8位进行形态学操作
            cleaned_8bit = (cleaned * 255 / np.max(cleaned)).astype(np.uint8)
            
            # 创建更大的椭圆核
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, 
                (self.clean_params['morphology_kernel_size'], self.clean_params['morphology_kernel_size'])
            )
            
            # 开运算去除小噪声
            opened = cv2.morphologyEx(cleaned_8bit, cv2.MORPH_OPEN, kernel)
            
            # 闭运算填充小孔
            closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)
            
            # 转换回浮点数
            cleaned = closed.astype(np.float64) / 255.0 * np.max(cleaned)
            
        remaining_pixels = np.sum(cleaned > 0)
        self.logger.info(f"形态学操作后剩余像素: {remaining_pixels}")
        
        # 7. 中值滤波平滑结果
        if self.clean_params['median_filter_size'] > 1:
            cleaned = median_filter(cleaned, size=self.clean_params['median_filter_size'])
            remaining_pixels = np.sum(cleaned > 0)
            self.logger.info(f"中值滤波后剩余像素: {remaining_pixels}")
        
        # 8. 轻微高斯平滑
        if self.clean_params['gaussian_sigma'] > 0:
            cleaned = gaussian_filter(cleaned, sigma=self.clean_params['gaussian_sigma'])
            remaining_pixels = np.sum(cleaned > 0)
            self.logger.info(f"高斯平滑后剩余像素: {remaining_pixels}")
        
        self.logger.info("高级差异图像清理完成")
        return cleaned
    
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
    
    def save_comparison_plot(self, original_data, cleaned_data, output_path):
        """
        保存对比图
        
        Args:
            original_data (numpy.ndarray): 原始数据
            cleaned_data (numpy.ndarray): 清理后的数据
            output_path (str): 输出路径
        """
        try:
            fig, axes = plt.subplots(1, 3, figsize=(18, 6))
            
            # 原始图像
            im1 = axes[0].imshow(original_data, cmap='hot', origin='lower')
            axes[0].set_title('原始差异图像')
            axes[0].set_xlabel('X像素')
            axes[0].set_ylabel('Y像素')
            plt.colorbar(im1, ax=axes[0], label='强度')
            
            # 清理后图像
            im2 = axes[1].imshow(cleaned_data, cmap='hot', origin='lower')
            axes[1].set_title('清理后差异图像')
            axes[1].set_xlabel('X像素')
            axes[1].set_ylabel('Y像素')
            plt.colorbar(im2, ax=axes[1], label='强度')
            
            # 差异图像
            diff = original_data - cleaned_data
            im3 = axes[2].imshow(diff, cmap='RdBu_r', origin='lower')
            axes[2].set_title('被去除的部分')
            axes[2].set_xlabel('X像素')
            axes[2].set_ylabel('Y像素')
            plt.colorbar(im3, ax=axes[2], label='强度差异')
            
            plt.tight_layout()
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            self.logger.info(f"对比图已保存: {output_path}")
        except Exception as e:
            self.logger.error(f"保存对比图失败 {output_path}: {str(e)}")

    def process_difference_fits(self, input_fits_path, output_directory=None):
        """
        处理差异FITS文件

        Args:
            input_fits_path (str): 输入的_difference.fits文件路径
            output_directory (str): 输出目录路径

        Returns:
            dict: 处理结果信息
        """
        # 检查输入文件
        if not os.path.exists(input_fits_path):
            self.logger.error(f"输入文件不存在: {input_fits_path}")
            return None

        # 设置输出目录
        if output_directory is None:
            input_dir = os.path.dirname(input_fits_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_directory = os.path.join(input_dir, f"cleaned_difference_{timestamp}")

        os.makedirs(output_directory, exist_ok=True)

        # 加载FITS数据
        self.logger.info(f"加载差异FITS文件: {input_fits_path}")
        original_data, header = self.load_fits_data(input_fits_path)

        if original_data is None:
            self.logger.error("FITS文件加载失败")
            return None

        # 执行高级清理
        self.logger.info("执行高级差异图像清理...")
        cleaned_data = self.advanced_clean_difference(original_data)

        # 生成输出文件名
        input_basename = os.path.splitext(os.path.basename(input_fits_path))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存清理后的FITS文件
        cleaned_fits_path = os.path.join(output_directory, f"{input_basename}_advanced_cleaned_{timestamp}.fits")
        self.save_fits_result(cleaned_data, cleaned_fits_path, header)

        # 保存对比图
        comparison_plot_path = os.path.join(output_directory, f"{input_basename}_comparison_{timestamp}.jpg")
        self.save_comparison_plot(original_data, cleaned_data, comparison_plot_path)

        # 生成统计报告
        original_nonzero = np.sum(original_data > 0)
        cleaned_nonzero = np.sum(cleaned_data > 0)
        reduction_ratio = (original_nonzero - cleaned_nonzero) / original_nonzero if original_nonzero > 0 else 0

        # 保存统计报告
        report_path = os.path.join(output_directory, f"{input_basename}_cleaning_report_{timestamp}.txt")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("差异FITS文件清理报告\n")
            f.write("=" * 50 + "\n")
            f.write(f"输入文件: {input_fits_path}\n")
            f.write(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"图像尺寸: {original_data.shape}\n")
            f.write(f"原始非零像素数: {original_nonzero}\n")
            f.write(f"清理后非零像素数: {cleaned_nonzero}\n")
            f.write(f"像素减少比例: {reduction_ratio:.2%}\n")
            f.write(f"原始最大强度: {np.max(original_data):.6f}\n")
            f.write(f"清理后最大强度: {np.max(cleaned_data):.6f}\n")
            f.write("\n清理参数:\n")
            for key, value in self.clean_params.items():
                f.write(f"  {key}: {value}\n")

        # 返回处理结果
        result = {
            'success': True,
            'input_file': input_fits_path,
            'output_directory': output_directory,
            'cleaned_fits_file': cleaned_fits_path,
            'comparison_plot': comparison_plot_path,
            'report_file': report_path,
            'statistics': {
                'original_nonzero_pixels': original_nonzero,
                'cleaned_nonzero_pixels': cleaned_nonzero,
                'reduction_ratio': reduction_ratio,
                'original_max_intensity': float(np.max(original_data)),
                'cleaned_max_intensity': float(np.max(cleaned_data))
            }
        }

        return result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='差异FITS文件高级清理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 处理指定的_difference.fits文件
  python clean_difference_fits.py --input aligned_comparison_20250715_175203_difference.fits

  # 指定输出目录
  python clean_difference_fits.py --input difference.fits --output cleaned_results

  # 调整清理参数
  python clean_difference_fits.py --input difference.fits --noise-percentile 10 --min-component-size 20
        """
    )

    parser.add_argument('--input', '-i', required=True,
                       help='输入的_difference.fits文件路径')
    parser.add_argument('--output', '-o',
                       help='输出目录（默认在输入文件目录下自动生成）')
    parser.add_argument('--noise-percentile', type=float, default=15,
                       help='噪声水平百分位数（默认15）')
    parser.add_argument('--noise-multiplier', type=float, default=4.0,
                       help='噪声阈值倍数（默认4.0）')
    parser.add_argument('--min-component-size', type=int, default=10,
                       help='最小连通组件大小（默认10）')
    parser.add_argument('--median-filter-size', type=int, default=3,
                       help='中值滤波器大小（默认3）')
    parser.add_argument('--morphology-kernel-size', type=int, default=5,
                       help='形态学操作核大小（默认5）')
    parser.add_argument('--intensity-threshold', type=float, default=0.05,
                       help='强度阈值（相对于最大值，默认0.05）')

    args = parser.parse_args()

    # 检查输入文件
    if not os.path.exists(args.input):
        print(f"错误: 输入文件不存在 - {args.input}")
        sys.exit(1)

    # 创建清理器
    cleaner = DifferenceFITSCleaner()

    # 更新参数
    cleaner.clean_params['noise_percentile'] = args.noise_percentile
    cleaner.clean_params['noise_multiplier'] = args.noise_multiplier
    cleaner.clean_params['min_component_size'] = args.min_component_size
    cleaner.clean_params['median_filter_size'] = args.median_filter_size
    cleaner.clean_params['morphology_kernel_size'] = args.morphology_kernel_size
    cleaner.clean_params['intensity_threshold'] = args.intensity_threshold

    print("=" * 60)
    print("差异FITS文件高级清理工具")
    print("=" * 60)
    print(f"输入文件: {args.input}")
    print(f"输出目录: {args.output or '自动生成'}")
    print("清理参数:")
    for key, value in cleaner.clean_params.items():
        print(f"  {key}: {value}")
    print("=" * 60)

    # 执行清理
    try:
        result = cleaner.process_difference_fits(args.input, args.output)

        if result and result['success']:
            print("\n处理完成！")
            print("=" * 60)
            print(f"输入文件: {os.path.basename(result['input_file'])}")
            print(f"清理后文件: {os.path.basename(result['cleaned_fits_file'])}")

            stats = result['statistics']
            print(f"\n清理统计:")
            print(f"  原始非零像素数: {stats['original_nonzero_pixels']:,}")
            print(f"  清理后非零像素数: {stats['cleaned_nonzero_pixels']:,}")
            print(f"  像素减少比例: {stats['reduction_ratio']:.2%}")
            print(f"  原始最大强度: {stats['original_max_intensity']:.6f}")
            print(f"  清理后最大强度: {stats['cleaned_max_intensity']:.6f}")

            print(f"\n输出文件已保存到: {result['output_directory']}")
            print(f"  清理后FITS文件: {os.path.basename(result['cleaned_fits_file'])}")
            print(f"  对比图: {os.path.basename(result['comparison_plot'])}")
            print(f"  统计报告: {os.path.basename(result['report_file'])}")

        else:
            print("处理失败！请检查日志文件了解详细错误信息。")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
