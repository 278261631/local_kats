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
import csv
import json
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 忽略一些常见的警告
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fits_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)



class DataRecorder:
    """数据记录器，用于保存分析结果到CSV文件"""

    def __init__(self, csv_filename='fits_quality_log.csv'):
        self.csv_filename = csv_filename
        self.logger = logging.getLogger(self.__class__.__name__)

        # 创建CSV文件并写入表头
        self.initialize_csv()

    def initialize_csv(self):
        """初始化CSV文件"""
        try:
            with open(self.csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'timestamp', 'filename', 'n_sources', 'fwhm', 'ellipticity',
                    'lm5sig', 'background_mean', 'background_rms'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

            self.logger.info(f"CSV记录文件已创建: {self.csv_filename}")

        except Exception as e:
            self.logger.error(f"初始化CSV文件时出错: {str(e)}")

    def record_data(self, filename, metrics):
        """记录数据到CSV文件"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 准备数据行
            row_data = {
                'timestamp': timestamp,
                'filename': os.path.basename(filename),
                'n_sources': metrics.get('n_sources', ''),
                'fwhm': metrics.get('fwhm', '') if not np.isnan(metrics.get('fwhm', np.nan)) else '',
                'ellipticity': metrics.get('ellipticity', '') if not np.isnan(metrics.get('ellipticity', np.nan)) else '',
                'lm5sig': metrics.get('lm5sig', '') if not np.isnan(metrics.get('lm5sig', np.nan)) else '',
                'background_mean': metrics.get('background_mean', ''),
                'background_rms': metrics.get('background_rms', '')
            }

            # 写入CSV文件
            with open(self.csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'timestamp', 'filename', 'n_sources', 'fwhm', 'ellipticity',
                    'lm5sig', 'background_mean', 'background_rms'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writerow(row_data)

            self.logger.info(f"数据已记录到CSV: {os.path.basename(filename)}")

        except Exception as e:
            self.logger.error(f"记录数据到CSV时出错: {str(e)}")


class FITSQualityAnalyzer:
    """FITS图像质量分析器"""

    def __init__(self, config=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config

        # 从配置中读取分析设置
        if config:
            analysis_settings = config.get('analysis_settings', {})
            self.use_central_region = analysis_settings.get('use_central_region', True)
            self.central_region_size = analysis_settings.get('central_region_size', 200)
            self.min_image_size = analysis_settings.get('min_image_size', 300)
        else:
            # 默认设置
            self.use_central_region = True
            self.central_region_size = 200
            self.min_image_size = 300
    
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
    
    def extract_central_region(self, image_data):
        """
        抽取图像中央的指定尺寸区域

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
                # 确保整个图像也是C连续的
                if not image_data.flags['C_CONTIGUOUS']:
                    image_data = np.ascontiguousarray(image_data)
                return image_data, False, (width, height)

            # 如果图像尺寸小于最小要求，使用整个图像
            if height < self.min_image_size or width < self.min_image_size:
                self.logger.info(f"图像尺寸 ({width}×{height}) 小于最小要求 ({self.min_image_size}×{self.min_image_size})，使用整个图像")
                if not image_data.flags['C_CONTIGUOUS']:
                    image_data = np.ascontiguousarray(image_data)
                return image_data, False, (width, height)

            # 如果图像尺寸小于抽取区域，使用整个图像
            if height < self.central_region_size or width < self.central_region_size:
                self.logger.info(f"图像尺寸 ({width}×{height}) 小于抽取区域 ({self.central_region_size}×{self.central_region_size})，使用整个图像")
                if not image_data.flags['C_CONTIGUOUS']:
                    image_data = np.ascontiguousarray(image_data)
                return image_data, False, (width, height)

            # 计算中央区域的起始坐标
            center_y, center_x = height // 2, width // 2
            half_size = self.central_region_size // 2

            start_y = center_y - half_size
            end_y = center_y + half_size
            start_x = center_x - half_size
            end_x = center_x + half_size

            # 抽取中央区域并确保内存连续性
            central_region = image_data[start_y:end_y, start_x:end_x].copy()

            # 确保数组是C连续的（sep库要求）
            if not central_region.flags['C_CONTIGUOUS']:
                central_region = np.ascontiguousarray(central_region)

            self.logger.info(f"抽取中央区域: {self.central_region_size}×{self.central_region_size} 像素 (原图: {width}×{height})")
            self.logger.info(f"抽取位置: [{start_x}:{end_x}, {start_y}:{end_y}]")

            return central_region, True, (width, height)

        except Exception as e:
            self.logger.error(f"抽取中央区域时出错: {str(e)}")
            return image_data, False, image_data.shape

    def calculate_quality_metrics(self, image_data):
        """
        计算图像质量指标

        Args:
            image_data (np.ndarray): 图像数据

        Returns:
            dict: 质量指标字典
        """
        try:
            # 抽取中央区域进行分析（根据配置设置）
            analysis_data, is_extracted, original_size = self.extract_central_region(image_data)

            # 背景估计和源检测
            bkg = sep.Background(analysis_data)
            data_sub = analysis_data - bkg.back()
            
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
                    'background_rms': float(bkg.globalrms),
                    'analysis_region': 'central_200x200' if is_extracted else 'full_image',
                    'original_size': f"{original_size[0]}x{original_size[1]}",
                    'analysis_size': f"{analysis_data.shape[1]}x{analysis_data.shape[0]}"
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
                'background_rms': float(bkg.globalrms),
                'analysis_region': 'central_200x200' if is_extracted else 'full_image',
                'original_size': f"{original_size[0]}x{original_size[1]}",
                'analysis_size': f"{analysis_data.shape[1]}x{analysis_data.shape[0]}"
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

        # 显示分析区域信息
        if 'analysis_region' in metrics:
            self.logger.info(f"原始图像尺寸:    {metrics['original_size']}")
            self.logger.info(f"分析区域尺寸:    {metrics['analysis_size']}")
            self.logger.info(f"分析区域类型:    {metrics['analysis_region']}")
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
                self.logger.info("[OK] FWHM: 优秀 (< 2.0 像素)")
            elif metrics['fwhm'] < 3.0:
                self.logger.info("[GOOD] FWHM: 良好 (2.0-3.0 像素)")
            elif metrics['fwhm'] < 5.0:
                self.logger.info("[FAIR] FWHM: 一般 (3.0-5.0 像素)")
            else:
                self.logger.info("[POOR] FWHM: 较差 (> 5.0 像素)")
                quality_issues.append("FWHM过大")
        
        # 椭圆度评估
        if not np.isnan(metrics['ellipticity']):
            if metrics['ellipticity'] < 0.1:
                self.logger.info("[OK] 椭圆度: 优秀 (< 0.1)")
            elif metrics['ellipticity'] < 0.2:
                self.logger.info("[GOOD] 椭圆度: 良好 (0.1-0.2)")
            elif metrics['ellipticity'] < 0.3:
                self.logger.info("[FAIR] 椭圆度: 一般 (0.2-0.3)")
            else:
                self.logger.info("[POOR] 椭圆度: 较差 (> 0.3)")
                quality_issues.append("椭圆度过高")
        
        # 源数量评估
        if metrics['n_sources'] < 10:
            self.logger.info("[POOR] 源数量: 较少 (< 10)")
            quality_issues.append("检测到的源数量过少")
        elif metrics['n_sources'] < 50:
            self.logger.info("[GOOD] 源数量: 一般 (10-50)")
        else:
            self.logger.info("[OK] 源数量: 充足 (> 50)")

        # 总体评估
        if len(quality_issues) == 0:
            self.logger.info("\n总体评估: 图像质量良好 [OK]")
        else:
            self.logger.info(f"\n总体评估: 发现质量问题 [WARNING]")
            for issue in quality_issues:
                self.logger.info(f"  - {issue}")


class FITSFileEventHandler(FileSystemEventHandler):
    """FITS文件事件处理器，使用watchdog监控文件系统事件"""

    def __init__(self, analyzer, recorder=None, enable_recording=True):
        super().__init__()
        self.analyzer = analyzer
        self.recorder = recorder
        self.enable_recording = enable_recording
        self.logger = logging.getLogger(self.__class__.__name__)
        self.processing_files = set()  # 正在处理的文件集合
        self.file_locks = {}  # 文件锁字典

    def on_created(self, event):
        """文件创建事件处理"""
        if not event.is_directory and event.src_path.lower().endswith('.fits'):
            self.logger.info(f"检测到新的FITS文件: {event.src_path}")
            # 使用线程处理文件，避免阻塞监控
            threading.Thread(
                target=self._process_file_delayed,
                args=(event.src_path,),
                daemon=True
            ).start()

    def on_moved(self, event):
        """文件移动事件处理"""
        if not event.is_directory and event.dest_path.lower().endswith('.fits'):
            self.logger.info(f"检测到移动的FITS文件: {event.dest_path}")
            # 使用线程处理文件，避免阻塞监控
            threading.Thread(
                target=self._process_file_delayed,
                args=(event.dest_path,),
                daemon=True
            ).start()

    def _process_file_delayed(self, file_path):
        """延迟处理文件，确保文件写入完成"""
        try:
            # 避免重复处理同一文件
            if file_path in self.processing_files:
                return

            self.processing_files.add(file_path)

            # 等待文件写入完成
            self._wait_for_file_complete(file_path)

            # 处理文件
            self._process_fits_file(file_path)

        except Exception as e:
            self.logger.error(f"处理文件时出错 {file_path}: {str(e)}")
        finally:
            # 清理处理状态
            self.processing_files.discard(file_path)

    def _wait_for_file_complete(self, file_path, timeout=30):
        """等待文件写入完成"""
        start_time = time.time()
        last_size = 0
        stable_count = 0

        while time.time() - start_time < timeout:
            try:
                current_size = os.path.getsize(file_path)
                if current_size == last_size and current_size > 0:
                    stable_count += 1
                    # 文件大小连续3次检查都稳定，认为写入完成
                    if stable_count >= 3:
                        break
                else:
                    stable_count = 0
                last_size = current_size
                time.sleep(0.5)
            except OSError:
                # 文件可能还在写入中或被锁定
                time.sleep(0.5)
                continue

    def _process_fits_file(self, file_path):
        """处理FITS文件"""
        try:
            self.logger.info(f"开始分析FITS文件: {file_path}")

            # 分析图像质量
            quality_metrics = self.analyzer.analyze_fits_quality(file_path)

            if quality_metrics:
                self.logger.info(f"FITS文件分析完成: {file_path}")

                # 记录数据到CSV文件
                if self.enable_recording and self.recorder:
                    try:
                        self.recorder.record_data(file_path, quality_metrics)
                    except Exception as e:
                        self.logger.error(f"记录数据时出错: {str(e)}")
            else:
                self.logger.error(f"FITS文件分析失败: {file_path}")

        except Exception as e:
            self.logger.error(f"处理FITS文件时出错 {file_path}: {str(e)}")


class FITSFileMonitor:
    """FITS文件监控器（使用watchdog事件驱动）"""

    def __init__(self, monitor_directory, enable_recording=True, config=None):
        self.monitor_directory = monitor_directory
        self.analyzer = FITSQualityAnalyzer(config)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.observer = None
        self.event_handler = None

        # 初始化数据记录器
        self.enable_recording = enable_recording

        if self.enable_recording:
            try:
                self.recorder = DataRecorder()
                self.logger.info("数据记录功能已启用")
            except Exception as e:
                self.logger.error(f"初始化数据记录器失败: {str(e)}")
                self.enable_recording = False
                self.recorder = None
        else:
            self.recorder = None

        # 创建事件处理器
        self.event_handler = FITSFileEventHandler(
            self.analyzer,
            self.recorder,
            self.enable_recording
        )

        # 处理现有文件（可选）
        self.process_existing_files = False  # 默认不处理现有文件

    def process_existing_files_on_startup(self):
        """启动时处理现有文件（可选功能）"""
        if not self.process_existing_files:
            return

        try:
            fits_pattern = os.path.join(self.monitor_directory, "**", "*.fits")
            existing_files = glob.glob(fits_pattern, recursive=True)

            if existing_files:
                self.logger.info(f"发现 {len(existing_files)} 个现有FITS文件")

                # 检查是否在交互环境中
                try:
                    import sys
                    if sys.stdin.isatty():
                        choice = input("是否处理现有文件？(y/N): ").strip().lower()
                    else:
                        choice = 'n'  # 非交互环境默认跳过
                        self.logger.info("非交互环境，跳过现有文件处理")
                except:
                    choice = 'n'  # 出错时默认跳过
                    self.logger.info("无法获取用户输入，跳过现有文件处理")

                if choice == 'y':
                    self.logger.info("开始处理现有文件...")
                    for file_path in existing_files:
                        try:
                            self.event_handler._process_fits_file(file_path)
                        except Exception as e:
                            self.logger.error(f"处理现有文件时出错 {file_path}: {str(e)}")
                    self.logger.info("现有文件处理完成")
                else:
                    self.logger.info("跳过现有文件处理")
            else:
                self.logger.info("未发现现有FITS文件")

        except Exception as e:
            self.logger.error(f"处理现有文件时出错: {str(e)}")

    def start_monitoring(self, scan_interval=None):
        """开始监控（scan_interval参数保留兼容性，但不再使用）"""
        self.logger.info(f"开始监控目录: {self.monitor_directory}")
        self.logger.info("使用watchdog事件驱动监控（实时响应）")

        if self.enable_recording:
            self.logger.info("数据记录功能已启用")
            self.logger.info("提示: 使用 'python plot_viewer.py' 查看图表")

        # 处理现有文件
        self.process_existing_files_on_startup()

        # 创建观察者
        self.observer = Observer()
        self.observer.schedule(
            self.event_handler,
            self.monitor_directory,
            recursive=True
        )

        try:
            # 启动观察者
            self.observer.start()
            self.logger.info("文件监控已启动，等待FITS文件...")
            self.logger.info("按 Ctrl+C 停止监控")

            # 保持主线程运行
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            self.logger.info("收到停止信号，正在关闭监控...")
        except Exception as e:
            self.logger.error(f"监控过程中出错: {str(e)}")
        finally:
            if self.observer:
                self.observer.stop()
                self.observer.join()
                self.logger.info("文件监控已停止")

    def stop_monitoring(self):
        """停止监控"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.logger.info("文件监控已停止")


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

    # 创建监控器（启用数据记录）
    monitor = FITSFileMonitor(
        monitor_directory,
        enable_recording=True  # 启用数据记录
    )

    # 启动监控（不再需要scan_interval参数）
    monitor.start_monitoring()


if __name__ == "__main__":
    main()
