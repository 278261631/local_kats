#!/usr/bin/env python3
"""
FITS文件监控和质量评估系统
监控指定目录中新创建的FITS文件，读取header信息并评估图像质量
"""

import os
import time
import logging
from pathlib import Path
from datetime import datetime
import numpy as np
import sep
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from photutils.detection import DAOStarFinder
from scipy.ndimage import gaussian_filter
import warnings
import glob

# 忽略一些常见的警告
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fits_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FITSQualityAnalyzer:
    """FITS图像质量分析器"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def analyze_fits_quality(self, fits_path):
        """
        分析FITS文件的图像质量
        
        Args:
            fits_path (str): FITS文件路径
            
        Returns:
            dict: 包含质量评估结果的字典
        """
        try:
            with fits.open(fits_path) as hdul:
                header = hdul[0].header
                image_data = hdul[0].data
                
                if image_data is None:
                    self.logger.error(f"无法读取图像数据: {fits_path}")
                    return None
                
                # 输出header信息
                self.print_header_info(header, fits_path)
                
                # 转换数据类型
                image_data = image_data.astype(np.float64)
                
                # 计算图像质量参数
                quality_metrics = self.calculate_quality_metrics(image_data)
                
                return quality_metrics
                
        except Exception as e:
            self.logger.error(f"分析FITS文件时出错 {fits_path}: {str(e)}")
            return None
    
    def print_header_info(self, header, fits_path):
        """打印FITS header信息"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"FITS文件: {fits_path}")
        self.logger.info(f"{'='*60}")
        
        # 常见的重要header关键字
        important_keys = [
            'SIMPLE', 'BITPIX', 'NAXIS', 'NAXIS1', 'NAXIS2',
            'OBJECT', 'TELESCOP', 'INSTRUME', 'FILTER',
            'EXPTIME', 'DATE-OBS', 'RA', 'DEC',
            'AIRMASS', 'GAIN', 'RDNOISE', 'PIXSCALE'
        ]
        
        for key in important_keys:
            if key in header:
                self.logger.info(f"{key:10s}: {header[key]}")
        
        # 打印所有其他header信息
        self.logger.info(f"\n完整Header信息:")
        for key, value in header.items():
            if key not in important_keys:
                self.logger.info(f"{key:10s}: {value}")
    
    def calculate_quality_metrics(self, image_data):
        """
        计算图像质量指标
        
        Args:
            image_data (np.ndarray): 图像数据
            
        Returns:
            dict: 质量指标字典
        """
        try:
            # 背景估计和源检测
            bkg = sep.Background(image_data)
            data_sub = image_data - bkg.back()
            
            # 检测源
            objects = sep.extract(data_sub, thresh=3.0, err=bkg.globalrms)
            
            if len(objects) == 0:
                self.logger.warning("未检测到任何源")
                return {
                    'n_sources': 0,
                    'fwhm': np.nan,
                    'ellipticity': np.nan,
                    'lm5sig': np.nan,
                    'background_mean': float(np.mean(bkg.back())),
                    'background_rms': float(bkg.globalrms)
                }
            
            # 计算FWHM
            fwhm = self.calculate_fwhm(objects)
            
            # 计算椭圆度
            ellipticity = self.calculate_ellipticity(objects)
            
            # 计算5σ限制星等
            lm5sig = self.calculate_limiting_magnitude(data_sub, bkg.globalrms)
            
            quality_metrics = {
                'n_sources': len(objects),
                'fwhm': fwhm,
                'ellipticity': ellipticity,
                'lm5sig': lm5sig,
                'background_mean': float(np.mean(bkg.back())),
                'background_rms': float(bkg.globalrms)
            }
            
            # 输出质量评估结果
            self.print_quality_results(quality_metrics)
            
            return quality_metrics
            
        except Exception as e:
            self.logger.error(f"计算质量指标时出错: {str(e)}")
            return None
    
    def calculate_fwhm(self, objects):
        """计算FWHM (半高全宽)"""
        try:
            # 使用SEP检测到的源的a和b参数计算FWHM
            # FWHM ≈ 2 * sqrt(2 * ln(2)) * sigma
            # 对于椭圆高斯分布，使用几何平均
            a_values = objects['a']
            b_values = objects['b']
            
            # 过滤异常值
            valid_mask = (a_values > 0) & (b_values > 0) & (a_values < 50) & (b_values < 50)
            if np.sum(valid_mask) == 0:
                return np.nan
            
            a_filtered = a_values[valid_mask]
            b_filtered = b_values[valid_mask]
            
            # 计算几何平均半径，然后转换为FWHM
            geometric_mean_radius = np.sqrt(a_filtered * b_filtered)
            fwhm_values = 2.355 * geometric_mean_radius  # 2.355 = 2*sqrt(2*ln(2))
            
            # 使用中位数作为代表值，更稳健
            median_fwhm = np.median(fwhm_values)
            
            return float(median_fwhm)
            
        except Exception as e:
            self.logger.error(f"计算FWHM时出错: {str(e)}")
            return np.nan
    
    def calculate_ellipticity(self, objects):
        """计算椭圆度"""
        try:
            a_values = objects['a']
            b_values = objects['b']
            
            # 过滤异常值
            valid_mask = (a_values > 0) & (b_values > 0) & (a_values >= b_values)
            if np.sum(valid_mask) == 0:
                return np.nan
            
            a_filtered = a_values[valid_mask]
            b_filtered = b_values[valid_mask]
            
            # 椭圆度定义: e = 1 - b/a
            ellipticity_values = 1.0 - (b_filtered / a_filtered)
            
            # 使用中位数
            median_ellipticity = np.median(ellipticity_values)
            
            return float(median_ellipticity)
            
        except Exception as e:
            self.logger.error(f"计算椭圆度时出错: {str(e)}")
            return np.nan
    
    def calculate_limiting_magnitude(self, data_sub, background_rms):
        """计算5σ限制星等"""
        try:
            # 5σ检测阈值
            threshold_5sigma = 5.0 * background_rms
            
            # 假设一个典型的孔径半径（像素）
            aperture_radius = 3.0
            aperture_area = np.pi * aperture_radius**2
            
            # 5σ限制通量
            flux_5sigma = threshold_5sigma * np.sqrt(aperture_area)
            
            # 转换为星等（需要零点星等，这里使用一个典型值）
            # 实际应用中应该从header或校准数据中获取
            zeropoint = 25.0  # 典型的零点星等
            
            if flux_5sigma > 0:
                lm5sig = zeropoint - 2.5 * np.log10(flux_5sigma)
            else:
                lm5sig = np.nan
            
            return float(lm5sig)
            
        except Exception as e:
            self.logger.error(f"计算限制星等时出错: {str(e)}")
            return np.nan
    
    def print_quality_results(self, metrics):
        """打印质量评估结果"""
        self.logger.info(f"\n图像质量评估结果:")
        self.logger.info(f"{'='*40}")
        self.logger.info(f"检测到的源数量: {metrics['n_sources']}")
        self.logger.info(f"FWHM (像素):     {metrics['fwhm']:.2f}")
        self.logger.info(f"椭圆度:          {metrics['ellipticity']:.3f}")
        self.logger.info(f"5σ限制星等:      {metrics['lm5sig']:.2f}")
        self.logger.info(f"背景均值:        {metrics['background_mean']:.2f}")
        self.logger.info(f"背景RMS:         {metrics['background_rms']:.2f}")
        
        # 质量评估
        self.evaluate_image_quality(metrics)
    
    def evaluate_image_quality(self, metrics):
        """评估图像质量等级"""
        self.logger.info(f"\n质量评估:")
        self.logger.info(f"{'='*40}")
        
        quality_issues = []
        
        # FWHM评估
        if not np.isnan(metrics['fwhm']):
            if metrics['fwhm'] < 2.0:
                self.logger.info("✓ FWHM: 优秀 (< 2.0 像素)")
            elif metrics['fwhm'] < 3.0:
                self.logger.info("○ FWHM: 良好 (2.0-3.0 像素)")
            elif metrics['fwhm'] < 5.0:
                self.logger.info("△ FWHM: 一般 (3.0-5.0 像素)")
            else:
                self.logger.info("✗ FWHM: 较差 (> 5.0 像素)")
                quality_issues.append("FWHM过大")
        
        # 椭圆度评估
        if not np.isnan(metrics['ellipticity']):
            if metrics['ellipticity'] < 0.1:
                self.logger.info("✓ 椭圆度: 优秀 (< 0.1)")
            elif metrics['ellipticity'] < 0.2:
                self.logger.info("○ 椭圆度: 良好 (0.1-0.2)")
            elif metrics['ellipticity'] < 0.3:
                self.logger.info("△ 椭圆度: 一般 (0.2-0.3)")
            else:
                self.logger.info("✗ 椭圆度: 较差 (> 0.3)")
                quality_issues.append("椭圆度过高")
        
        # 源数量评估
        if metrics['n_sources'] < 10:
            self.logger.info("✗ 源数量: 较少 (< 10)")
            quality_issues.append("检测到的源数量过少")
        elif metrics['n_sources'] < 50:
            self.logger.info("○ 源数量: 一般 (10-50)")
        else:
            self.logger.info("✓ 源数量: 充足 (> 50)")
        
        # 总体评估
        if len(quality_issues) == 0:
            self.logger.info("\n总体评估: 图像质量良好 ✓")
        else:
            self.logger.info(f"\n总体评估: 发现质量问题 ✗")
            for issue in quality_issues:
                self.logger.info(f"  - {issue}")


class FITSFileMonitor:
    """FITS文件监控器（使用轮询方式）"""

    def __init__(self, monitor_directory):
        self.monitor_directory = monitor_directory
        self.analyzer = FITSQualityAnalyzer()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.known_files = set()  # 已知的文件集合

        # 初始化时记录所有现有文件
        self.initialize_known_files()

    def initialize_known_files(self):
        """初始化已知文件列表"""
        try:
            fits_pattern = os.path.join(self.monitor_directory, "**", "*.fits")
            existing_files = glob.glob(fits_pattern, recursive=True)
            self.known_files = set(existing_files)
            self.logger.info(f"初始化完成，发现 {len(self.known_files)} 个现有FITS文件")
        except Exception as e:
            self.logger.error(f"初始化已知文件时出错: {str(e)}")

    def scan_for_new_files(self):
        """扫描新的FITS文件"""
        try:
            # 获取所有FITS文件
            fits_pattern = os.path.join(self.monitor_directory, "**", "*.fits")
            current_files = set(glob.glob(fits_pattern, recursive=True))

            # 找出新文件
            new_files = current_files - self.known_files

            if new_files:
                for file_path in new_files:
                    self.logger.info(f"检测到新的FITS文件: {file_path}")

                    # 等待文件写入完成
                    self.wait_for_file_complete(file_path)

                    # 处理文件
                    self.process_fits_file(file_path)

                # 更新已知文件集合
                self.known_files = current_files

        except Exception as e:
            self.logger.error(f"扫描文件时出错: {str(e)}")

    def wait_for_file_complete(self, file_path, timeout=30):
        """等待文件写入完成"""
        start_time = time.time()
        last_size = 0

        while time.time() - start_time < timeout:
            try:
                current_size = os.path.getsize(file_path)
                if current_size == last_size and current_size > 0:
                    # 文件大小稳定，等待额外1秒确保写入完成
                    time.sleep(1)
                    break
                last_size = current_size
                time.sleep(0.5)
            except OSError:
                # 文件可能还在写入中
                time.sleep(0.5)
                continue

    def process_fits_file(self, file_path):
        """处理FITS文件"""
        try:
            self.logger.info(f"开始分析FITS文件: {file_path}")

            # 分析图像质量
            quality_metrics = self.analyzer.analyze_fits_quality(file_path)

            if quality_metrics:
                self.logger.info(f"FITS文件分析完成: {file_path}")
            else:
                self.logger.error(f"FITS文件分析失败: {file_path}")

        except Exception as e:
            self.logger.error(f"处理FITS文件时出错 {file_path}: {str(e)}")

    def start_monitoring(self, scan_interval=5):
        """开始监控"""
        self.logger.info(f"开始监控目录: {self.monitor_directory}")
        self.logger.info(f"扫描间隔: {scan_interval} 秒")

        try:
            while True:
                self.scan_for_new_files()
                time.sleep(scan_interval)
        except KeyboardInterrupt:
            self.logger.info("收到停止信号，正在关闭监控...")
        except Exception as e:
            self.logger.error(f"监控过程中出错: {str(e)}")


def main():
    """主函数"""
    # 监控目录
    monitor_directory = r"E:\fix_data"

    # 检查目录是否存在
    if not os.path.exists(monitor_directory):
        logger.error(f"监控目录不存在: {monitor_directory}")
        logger.info("创建测试目录用于演示...")
        # 为了演示，我们使用当前目录下的一个测试目录
        monitor_directory = os.path.join(os.getcwd(), "test_fits_data")
        os.makedirs(monitor_directory, exist_ok=True)
        logger.info(f"使用测试目录: {monitor_directory}")

    # 创建监控器
    monitor = FITSFileMonitor(monitor_directory)

    # 启动监控
    monitor.start_monitoring(scan_interval=5)


if __name__ == "__main__":
    main()
