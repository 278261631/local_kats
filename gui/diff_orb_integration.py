#!/usr/bin/env python3
"""
diff_orb集成模块
用于在GUI中集成diff_orb的FITS图像差异检测功能
"""

import os
import sys
import logging
import tempfile
import shutil
import time
from typing import Optional, Dict, Tuple
from pathlib import Path

# 添加diff_orb目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
diff_orb_dir = os.path.join(os.path.dirname(current_dir), 'diff_orb')
if os.path.exists(diff_orb_dir):
    sys.path.insert(0, diff_orb_dir)

try:
    from fits_alignment_comparison import FITSAlignmentComparison
    from compare_aligned_fits import AlignedFITSComparator
except ImportError as e:
    logging.error(f"无法导入diff_orb模块: {e}")
    FITSAlignmentComparison = None
    AlignedFITSComparator = None

from filename_parser import FITSFilenameParser
from error_logger import ErrorLogger

# 导入噪点处理模块
try:
    # 添加simple_noise目录到路径
    simple_noise_dir = os.path.join(os.path.dirname(current_dir), 'simple_noise')
    if os.path.exists(simple_noise_dir):
        sys.path.insert(0, simple_noise_dir)
    from simple_pixel_detector import process_fits_simple
except ImportError as e:
    logging.warning(f"无法导入噪点处理模块: {e}")
    process_fits_simple = None


class DiffOrbIntegration:
    """diff_orb集成类"""

    def __init__(self, gui_callback=None):
        """
        初始化diff_orb集成

        Args:
            gui_callback: GUI回调函数，用于显示错误信息
        """
        self.logger = logging.getLogger(__name__)
        self.filename_parser = FITSFilenameParser()
        self.gui_callback = gui_callback
        self.error_logger = None  # 将在处理时创建
        
        # 检查diff_orb是否可用
        self.diff_orb_available = FITSAlignmentComparison is not None and AlignedFITSComparator is not None

        if not self.diff_orb_available:
            self.logger.error("diff_orb模块不可用，请检查安装")

        # 创建diff_orb比较器
        if self.diff_orb_available:
            # 用于图像对齐的比较器
            self.alignment_comparator = FITSAlignmentComparison(
                use_central_region=False,  # 不使用中央区域，处理完整图像
                alignment_method='rigid'   # 刚体变换，适合天文图像
            )
            # 用于已对齐文件比较的比较器
            self.aligned_comparator = AlignedFITSComparator()
    
    def is_available(self) -> bool:
        """检查diff_orb是否可用"""
        return self.diff_orb_available
    
    def can_process_file(self, file_path: str, template_dir: str) -> Tuple[bool, str]:
        """
        检查文件是否可以进行diff操作
        
        Args:
            file_path (str): 下载文件路径
            template_dir (str): 模板目录路径
            
        Returns:
            Tuple[bool, str]: (是否可以处理, 状态信息)
        """
        if not self.diff_orb_available:
            return False, "diff_orb模块不可用"
        
        if not os.path.exists(file_path):
            return False, "文件不存在"
        
        if not os.path.exists(template_dir):
            return False, "模板目录不存在"
        
        # 解析文件名
        parsed_info = self.filename_parser.parse_filename(file_path)
        if not parsed_info:
            return False, "无法解析文件名"
        
        # 检查是否有必要的信息
        if 'tel_name' not in parsed_info:
            return False, "文件名中缺少望远镜信息"
        
        # 查找对应的模板文件
        tel_name = parsed_info['tel_name']
        k_number = parsed_info.get('k_full', parsed_info.get('k_number', ''))  # 优先使用完整的天区加索引格式

        template_file = self.filename_parser.find_template_file(template_dir, tel_name, k_number)
        if not template_file:
            return False, f"未找到匹配的模板文件 (tel_name: {tel_name}, k_number: {k_number})"
        
        return True, f"找到模板文件: {os.path.basename(template_file)}"
    
    def find_template_file(self, download_file: str, template_dir: str) -> Optional[str]:
        """
        为下载文件查找对应的模板文件
        
        Args:
            download_file (str): 下载文件路径
            template_dir (str): 模板目录路径
            
        Returns:
            Optional[str]: 模板文件路径，如果没找到返回None
        """
        try:
            # 解析下载文件名
            parsed_info = self.filename_parser.parse_filename(download_file)
            if not parsed_info or 'tel_name' not in parsed_info:
                self.logger.error(f"无法从文件名中提取信息: {download_file}")
                return None
            
            tel_name = parsed_info['tel_name']
            k_number = parsed_info.get('k_full', parsed_info.get('k_number', ''))  # 优先使用完整的天区加索引格式

            # 查找模板文件
            template_file = self.filename_parser.find_template_file(template_dir, tel_name, k_number)
            
            if template_file:
                self.logger.info(f"为 {os.path.basename(download_file)} 找到模板文件: {os.path.basename(template_file)}")
            else:
                self.logger.warning(f"未找到匹配的模板文件: tel_name={tel_name}, k_number={k_number}")
            
            return template_file
            
        except Exception as e:
            self.logger.error(f"查找模板文件时出错: {str(e)}")
            return None
    
    def process_diff(self, download_file: str, template_file: str, output_dir: str = None, noise_methods: list = None, alignment_method: str = 'rigid', remove_bright_lines: bool = True, stretch_method: str = 'peak', percentile_low: float = 99.95, fast_mode: bool = False, max_jaggedness_ratio: float = 2.0, detection_method: str = 'contour', sort_by: str = 'aligned_snr') -> Optional[Dict]:
        """
        执行diff操作

        Args:
            download_file (str): 下载文件路径（作为待比较文件）
            template_file (str): 模板文件路径（作为参考文件）
            output_dir (str): 输出目录，如果为None则自动创建
            noise_methods (list): 降噪方式列表，可选值：['outlier', 'hot_cold', 'adaptive_median']
            alignment_method (str): 对齐方式，可选值：['rigid', 'wcs']
            remove_bright_lines (bool): 是否去除亮线，默认True
            stretch_method (str): 拉伸方法，'peak'=峰值拉伸, 'percentile'=百分位数拉伸
            percentile_low (float): 百分位数起点，默认99.95
            fast_mode (bool): 快速模式，减少中间文件输出，默认False
            max_jaggedness_ratio (float): 最大锯齿比率，默认2.0
            detection_method (str): 检测方法，'contour'=轮廓检测（默认）, 'simple_blob'=SimpleBlobDetector
            sort_by (str): 排序方式，'quality_score'=综合得分（默认）, 'aligned_snr'=Aligned中心7x7 SNR, 'snr'=差异图像SNR

        Returns:
            Optional[Dict]: 处理结果字典，包含输出文件路径等信息
        """
        if not self.diff_orb_available:
            self.logger.error("diff_orb模块不可用")
            return None

        # 创建输出目录
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="diff_orb_results_")
        else:
            os.makedirs(output_dir, exist_ok=True)

        # 创建错误日志记录器
        error_log_path = os.path.join(output_dir, "diff_error_log.txt")
        self.error_logger = ErrorLogger(error_log_path, self.gui_callback)

        try:
            # 记录总体开始时间
            total_start_time = time.time()
            timing_stats = {}

            self.error_logger.log_info("开始diff操作", {
                "参考文件": os.path.basename(template_file),
                "待比较文件": os.path.basename(download_file),
                "输出目录": output_dir,
                "对齐方式": alignment_method,
                "降噪方式": str(noise_methods),
                "快速模式": fast_mode
            })

            # 验证输入文件
            validation_start = time.time()
            if not os.path.exists(download_file):
                error_msg = f"下载文件不存在"
                self.logger.error(f"{error_msg}: {download_file}")
                self.error_logger.log_error(error_msg, context={"文件路径": download_file})
                return None

            if not os.path.exists(template_file):
                error_msg = f"模板文件不存在"
                self.logger.error(f"{error_msg}: {template_file}")
                self.error_logger.log_error(error_msg, context={"文件路径": template_file})
                return None

            timing_stats['文件验证'] = time.time() - validation_start
            self.logger.info(f"⏱️  文件验证耗时: {timing_stats['文件验证']:.3f}秒")

            self.logger.info(f"开始diff操作:")
            self.logger.info(f"  参考文件 (模板): {os.path.basename(template_file)}")
            self.logger.info(f"  待比较文件 (下载): {os.path.basename(download_file)}")
            self.logger.info(f"  输出目录: {output_dir}")

            # 步骤0: 噪点处理
            noise_start = time.time()
            processed_download_file, processed_template_file = self._preprocess_noise_removal(
                download_file, template_file, output_dir, noise_methods
            )
            timing_stats['噪点处理'] = time.time() - noise_start
            self.logger.info(f"⏱️  步骤0 噪点处理耗时: {timing_stats['噪点处理']:.3f}秒")

            # 步骤1: 根据选择的对齐方式进行图像对齐
            alignment_start = time.time()
            self.logger.info(f"步骤1: 执行图像对齐（方式: {alignment_method}）...")

            if alignment_method == 'wcs':
                # 使用WCS对齐
                alignment_result = self._align_using_wcs(
                    processed_template_file, processed_download_file, output_dir
                )
            else:
                # 使用特征点对齐（只支持rigid方式）
                alignment_result = self.alignment_comparator.process_fits_comparison(
                    processed_template_file,      # 参考文件（处理后的模板）
                    processed_download_file,      # 待比较文件（处理后的下载文件）
                    output_dir=output_dir,
                    show_visualization=False  # 在GUI中不显示matplotlib窗口
                )

            timing_stats['图像对齐'] = time.time() - alignment_start
            self.logger.info(f"⏱️  步骤1 图像对齐耗时: {timing_stats['图像对齐']:.3f}秒")

            if not alignment_result or not alignment_result.get('alignment_success'):
                error_msg = "图像对齐失败"
                self.logger.error(error_msg)
                self.error_logger.log_error(error_msg, context={
                    "对齐方式": alignment_method,
                    "参考文件": os.path.basename(processed_template_file),
                    "待比较文件": os.path.basename(processed_download_file)
                })
                return None

            self.error_logger.log_info("图像对齐成功")

            # 步骤2: 使用已对齐文件进行差异比较
            diff_comparison_start = time.time()
            self.logger.info("步骤2: 执行已对齐文件差异比较...")
            self.error_logger.log_info("开始差异比较")

            result = self.aligned_comparator.process_aligned_fits_comparison(
                output_dir,  # 输入目录（包含对齐后的文件）
                output_dir,  # 输出目录（同一目录）
                remove_bright_lines=remove_bright_lines,  # 传递去除亮线参数
                stretch_method=stretch_method,  # 传递拉伸方法参数
                percentile_low=percentile_low,  # 传递百分位数参数
                fast_mode=fast_mode,  # 传递快速模式参数
                max_jaggedness_ratio=max_jaggedness_ratio,  # 传递锯齿比率参数
                detection_method=detection_method,  # 传递检测方法参数
                sort_by=sort_by  # 传递排序方式参数
            )

            timing_stats['差异比较'] = time.time() - diff_comparison_start
            self.logger.info(f"⏱️  步骤2 差异比较耗时: {timing_stats['差异比较']:.3f}秒")

            if result:
                # 快速模式：删除中间文件
                cleanup_start = time.time()
                if fast_mode:
                    self._cleanup_intermediate_files(output_dir, template_file, download_file)
                    timing_stats['清理中间文件'] = time.time() - cleanup_start
                    self.logger.info(f"⏱️  清理中间文件耗时: {timing_stats['清理中间文件']:.3f}秒")

                # 收集输出文件信息
                collect_start = time.time()
                output_files = self._collect_output_files(output_dir)
                timing_stats['收集输出文件'] = time.time() - collect_start
                self.logger.info(f"⏱️  收集输出文件耗时: {timing_stats['收集输出文件']:.3f}秒")

                # 计算总耗时
                total_time = time.time() - total_start_time
                timing_stats['总耗时'] = total_time

                # 输出耗时统计摘要
                self.logger.info("=" * 60)
                self.logger.info("⏱️  耗时统计摘要:")
                self.logger.info(f"  文件验证: {timing_stats.get('文件验证', 0):.3f}秒")
                self.logger.info(f"  步骤0 噪点处理: {timing_stats.get('噪点处理', 0):.3f}秒")
                self.logger.info(f"  步骤1 图像对齐: {timing_stats.get('图像对齐', 0):.3f}秒")
                self.logger.info(f"  步骤2 差异比较: {timing_stats.get('差异比较', 0):.3f}秒")
                if fast_mode:
                    self.logger.info(f"  清理中间文件: {timing_stats.get('清理中间文件', 0):.3f}秒")
                self.logger.info(f"  收集输出文件: {timing_stats.get('收集输出文件', 0):.3f}秒")
                self.logger.info(f"  总耗时: {total_time:.3f}秒")
                self.logger.info("=" * 60)

                self.logger.info(f"diff操作成功完成")
                self.logger.info(f"  对齐成功: {result.get('alignment_success', False)}")
                self.logger.info(f"  检测到新亮点: {result.get('new_bright_spots', 0)} 个")

                self.error_logger.log_info("diff操作成功完成", {
                    "检测到新亮点": result.get('new_bright_spots', 0),
                    "总耗时": f"{total_time:.3f}秒"
                })

                # 关闭错误日志记录器
                self.error_logger.close()

                return {
                    'success': True,
                    'alignment_success': result.get('alignment_success', False),
                    'new_bright_spots': result.get('new_bright_spots', 0),
                    'output_directory': output_dir,
                    'output_files': output_files,
                    'reference_file': template_file,
                    'compared_file': download_file,
                    'fast_mode': fast_mode,
                    'error_log_file': error_log_path,
                    'timing_stats': timing_stats  # 添加耗时统计信息
                }
            else:
                error_msg = "diff操作失败"
                self.logger.error(error_msg)
                self.error_logger.log_error(error_msg)
                self.error_logger.close()
                return None

        except Exception as e:
            error_msg = "执行diff操作时出错"
            self.logger.error(f"{error_msg}: {str(e)}")
            self.error_logger.log_error(error_msg, exception=e, context={
                "参考文件": template_file,
                "待比较文件": download_file,
                "输出目录": output_dir
            })
            self.error_logger.close()
            return None
    
    def _cleanup_intermediate_files(self, output_dir: str, template_file: str, download_file: str):
        """
        快速模式：删除中间文件（保留noise_cleaned_aligned.fits）

        Args:
            output_dir: 输出目录
            template_file: 模板文件路径
            download_file: 下载文件路径
        """
        self.logger.info("快速模式：清理中间文件...")

        template_basename = os.path.splitext(os.path.basename(template_file))[0]
        download_basename = os.path.splitext(os.path.basename(download_file))[0]

        # 定义要删除的文件后缀（不包含noise_cleaned_aligned.fits）
        suffixes_to_remove = [
            '_adaptive_median_filtered.fits',
            '_adaptive_median_noise.fits',
            '_noise_cleaned.fits',
            # '_noise_cleaned_aligned.fits',  # 保留此文件
            '_aligned.fits',
            '_simple_repaired.fits'
        ]

        deleted_count = 0
        kept_count = 0

        # 删除模板文件的中间文件
        for suffix in suffixes_to_remove:
            file_path = os.path.join(output_dir, f"{template_basename}{suffix}")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    self.logger.debug(f"  已删除: {os.path.basename(file_path)}")
                    deleted_count += 1
                except Exception as e:
                    self.logger.warning(f"  无法删除 {os.path.basename(file_path)}: {e}")

        # 删除下载文件的中间文件
        for suffix in suffixes_to_remove:
            file_path = os.path.join(output_dir, f"{download_basename}{suffix}")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    self.logger.debug(f"  已删除: {os.path.basename(file_path)}")
                    deleted_count += 1
                except Exception as e:
                    self.logger.warning(f"  无法删除 {os.path.basename(file_path)}: {e}")

        # 检查保留的noise_cleaned_aligned.fits文件
        for basename in [template_basename, download_basename]:
            kept_file = os.path.join(output_dir, f"{basename}_noise_cleaned_aligned.fits")
            if os.path.exists(kept_file):
                self.logger.debug(f"  已保留: {os.path.basename(kept_file)}")
                kept_count += 1

        self.logger.info(f"快速模式：已删除 {deleted_count} 个中间文件，保留 {kept_count} 个noise_cleaned_aligned.fits文件")

    def _collect_output_files(self, output_dir: str) -> Dict[str, str]:
        """收集输出目录中的文件"""
        output_files = {}

        try:
            self.logger.info(f"扫描输出目录: {output_dir}")
            all_files = list(Path(output_dir).glob("*"))
            self.logger.info(f"找到 {len(all_files)} 个文件")

            for file_path in all_files:
                if file_path.is_file():
                    filename = file_path.name.lower()  # 转换为小写进行匹配
                    original_filename = file_path.name

                    self.logger.debug(f"检查文件: {original_filename}")

                    # 分类文件 - 使用更宽松的匹配模式
                    if ('difference' in filename or 'diff' in filename) and filename.endswith('.fits'):
                        output_files['difference_fits'] = str(file_path)
                        self.logger.info(f"找到差异FITS文件: {original_filename}")
                    elif ('difference' in filename or 'diff' in filename) and (filename.endswith('.jpg') or filename.endswith('.jpeg') or filename.endswith('.png')):
                        if filename.endswith('.png'):
                            output_files['difference_png'] = str(file_path)
                            self.logger.info(f"找到差异PNG文件: {original_filename}")
                        else:
                            output_files['difference_jpg'] = str(file_path)
                            self.logger.info(f"找到差异JPG文件: {original_filename}")
                    elif 'marked' in filename and filename.endswith('.fits'):
                        output_files['marked_fits'] = str(file_path)
                        self.logger.info(f"找到标记FITS文件: {original_filename}")
                    elif 'marked' in filename and (filename.endswith('.jpg') or filename.endswith('.jpeg') or filename.endswith('.png')):
                        if filename.endswith('.png'):
                            output_files['marked_png'] = str(file_path)
                            self.logger.info(f"找到标记PNG文件: {original_filename}")
                        else:
                            output_files['marked_jpg'] = str(file_path)
                            self.logger.info(f"找到标记JPG文件: {original_filename}")
                    elif 'reference' in filename and filename.endswith('.fits'):
                        output_files['reference_fits'] = str(file_path)
                        self.logger.info(f"找到参考FITS文件: {original_filename}")
                    elif 'aligned' in filename and filename.endswith('.fits'):
                        output_files['aligned_fits'] = str(file_path)
                        self.logger.info(f"找到对齐FITS文件: {original_filename}")
                    elif ('bright_spots' in filename or 'report' in filename) and filename.endswith('.txt'):
                        output_files['report_txt'] = str(file_path)
                        self.logger.info(f"找到报告文件: {original_filename}")
                    elif filename.endswith('.fits'):
                        # 如果是FITS文件但不匹配上述模式，记录下来
                        self.logger.info(f"未分类的FITS文件: {original_filename}")
                        # 如果还没有找到差异文件，将第一个未分类的FITS文件作为候选
                        if 'difference_fits' not in output_files:
                            output_files['candidate_fits'] = str(file_path)

            self.logger.info(f"收集到 {len(output_files)} 个输出文件: {list(output_files.keys())}")

            # 如果没有找到difference_fits但有candidate_fits，使用候选文件
            if 'difference_fits' not in output_files and 'candidate_fits' in output_files:
                output_files['difference_fits'] = output_files.pop('candidate_fits')
                self.logger.info(f"使用候选文件作为差异文件: {os.path.basename(output_files['difference_fits'])}")

        except Exception as e:
            self.logger.error(f"收集输出文件时出错: {str(e)}")

        return output_files
    
    def get_diff_summary(self, result: Dict) -> str:
        """
        生成diff操作的摘要信息
        
        Args:
            result (Dict): diff操作结果
            
        Returns:
            str: 摘要信息
        """
        if not result or not result.get('success'):
            return "diff操作失败"
        
        summary_lines = [
            f"diff操作完成",
            f"对齐状态: {'成功' if result.get('alignment_success') else '失败'}",
            f"检测到新亮点: {result.get('new_bright_spots', 0)} 个",
            f"参考文件: {os.path.basename(result.get('reference_file', ''))}",
            f"比较文件: {os.path.basename(result.get('compared_file', ''))}"
        ]

        output_files = result.get('output_files', {})
        if output_files:
            summary_lines.append(f"生成文件: {len(output_files)} 个")

            # 详细列出生成的文件类型
            file_types = []
            if 'difference_fits' in output_files:
                file_types.append("差异FITS")
            elif 'difference_png' in output_files:
                file_types.append("差异PNG")
            elif 'difference_jpg' in output_files:
                file_types.append("差异JPG")

            if 'marked_fits' in output_files:
                file_types.append("标记FITS")
            elif 'marked_png' in output_files:
                file_types.append("标记PNG")

            if 'aligned_fits' in output_files:
                file_types.append("对齐FITS")

            if 'reference_fits' in output_files:
                file_types.append("参考FITS")

            if 'report_txt' in output_files:
                file_types.append("检测报告")

            if file_types:
                summary_lines.append(f"文件类型: {', '.join(file_types)}")

        return "\n".join(summary_lines)

    def _preprocess_noise_removal(self, download_file: str, template_file: str, output_dir: str, noise_methods: list = None) -> Tuple[str, str]:
        """
        在diff操作之前对输入文件进行噪点处理

        Args:
            download_file (str): 下载文件路径
            template_file (str): 模板文件路径
            output_dir (str): 输出目录
            noise_methods (list): 降噪方式列表，可选值：['outlier', 'hot_cold', 'adaptive_median']

        Returns:
            Tuple[str, str]: (处理后的下载文件路径, 处理后的模板文件路径)
        """
        if process_fits_simple is None:
            self.logger.warning("噪点处理模块不可用，跳过噪点处理步骤")
            return download_file, template_file

        # 设置默认降噪方式
        if noise_methods is None:
            noise_methods = ['outlier']

        # 如果noise_methods是空列表，跳过降噪处理
        if not noise_methods:
            self.logger.info("步骤0: 跳过噪点处理（未启用降噪）")
            return download_file, template_file

        self.logger.info(f"步骤0: 执行噪点处理，使用方法: {', '.join(noise_methods)}")

        processed_download_file = download_file
        processed_template_file = template_file

        try:
            # 处理下载文件（观测文件）
            download_process_start = time.time()
            self.logger.info(f"处理观测文件: {os.path.basename(download_file)}")

            # 对每种降噪方式进行处理
            final_repaired_data = None
            final_noise_data = None
            final_noise_mask = None

            for method in noise_methods:
                method_start = time.time()
                self.logger.info(f"  使用 {method} 方法处理观测文件")
                download_result = process_fits_simple(
                    download_file,
                    method=method,
                    threshold=4.0,
                    output_dir=output_dir
                )
                method_time = time.time() - method_start
                self.logger.info(f"  ⏱️  {method} 方法处理观测文件耗时: {method_time:.3f}秒")

                if download_result and len(download_result) >= 3:
                    repaired_data, noise_data, noise_mask = download_result

                    if final_repaired_data is None:
                        # 第一次处理，直接使用结果
                        final_repaired_data = repaired_data.copy()
                        final_noise_data = noise_data.copy()
                        final_noise_mask = noise_mask.copy()
                    else:
                        # 后续处理，在前一次结果基础上继续处理
                        # 使用前一次的修复结果作为输入
                        from astropy.io import fits

                        # 创建临时文件保存中间结果
                        with tempfile.NamedTemporaryFile(suffix='.fits', delete=False) as temp_file:
                            temp_filename = temp_file.name

                        # 读取原始文件的header
                        with fits.open(download_file) as hdul:
                            header = hdul[0].header.copy()

                        # 保存中间结果到临时文件
                        fits.writeto(temp_filename, final_repaired_data, header=header, overwrite=True)

                        # 对临时文件进行下一轮处理
                        next_result = process_fits_simple(
                            temp_filename,
                            method=method,
                            threshold=4.0
                        )

                        # 清理临时文件
                        try:
                            os.unlink(temp_filename)
                        except:
                            pass

                        if next_result and len(next_result) >= 3:
                            final_repaired_data, next_noise_data, next_noise_mask = next_result
                            # 累积噪点数据和掩码
                            final_noise_data += next_noise_data
                            final_noise_mask |= next_noise_mask
                        else:
                            self.logger.warning(f"  {method} 方法处理失败，跳过")
                else:
                    self.logger.warning(f"  {method} 方法处理失败，跳过")

            download_result = (final_repaired_data, final_noise_data, final_noise_mask) if final_repaired_data is not None else None

            if download_result and len(download_result) >= 3:
                repaired_data, noise_data, noise_mask = download_result

                # 验证数据形状
                from astropy.io import fits
                with fits.open(download_file) as hdul:
                    original_data = hdul[0].data
                    original_shape = original_data.shape
                    header = hdul[0].header.copy()

                self.logger.debug(f"下载文件原始形状: {original_shape}")
                self.logger.debug(f"处理后数据形状: {repaired_data.shape}")

                # 检查数据形状是否一致
                if repaired_data.shape != original_shape:
                    self.logger.error("=" * 60)
                    self.logger.error("⚠️  降噪处理导致数据形状改变！")
                    self.logger.error(f"原始形状: {original_shape}")
                    self.logger.error(f"处理后形状: {repaired_data.shape}")
                    self.logger.error(f"下载文件: {download_file}")
                    self.logger.error("WCS信息可能不准确，使用原始文件代替")
                    self.logger.error("=" * 60)

                    # 删除process_fits_simple保存的错误文件
                    download_basename = os.path.splitext(os.path.basename(download_file))[0]
                    for suffix in ['_noise_cleaned.fits', '_adaptive_median_filtered.fits', '_simple_repaired.fits']:
                        error_file = os.path.join(output_dir, f"{download_basename}{suffix}")
                        if os.path.exists(error_file):
                            try:
                                os.remove(error_file)
                                self.logger.info(f"已删除错误的降噪文件: {os.path.basename(error_file)}")
                            except Exception as e:
                                self.logger.warning(f"无法删除文件 {error_file}: {str(e)}")

                    processed_download_file = download_file
                else:
                    # 保存处理后的观测文件
                    download_basename = os.path.splitext(os.path.basename(download_file))[0]
                    processed_download_file = os.path.join(output_dir, f"{download_basename}_noise_cleaned.fits")

                    # 保存处理后的数据
                    fits.writeto(processed_download_file, repaired_data, header=header, overwrite=True)
                    self.logger.info(f"观测文件噪点处理完成，保存到: {os.path.basename(processed_download_file)}")
            else:
                self.logger.warning("观测文件噪点处理失败，使用原始文件")

            download_process_time = time.time() - download_process_start
            self.logger.info(f"⏱️  观测文件噪点处理总耗时: {download_process_time:.3f}秒")

        except Exception as e:
            self.logger.error(f"处理观测文件时出错: {str(e)}")
            self.logger.warning("使用原始观测文件")
            processed_download_file = download_file  # 确保使用原始文件

        try:
            # 处理模板文件
            template_process_start = time.time()
            self.logger.info(f"处理模板文件: {os.path.basename(template_file)}")

            # 对每种降噪方式进行处理
            final_repaired_data = None
            final_noise_data = None
            final_noise_mask = None

            for method in noise_methods:
                method_start = time.time()
                self.logger.info(f"  使用 {method} 方法处理模板文件")
                self.logger.info(f"  输入文件: {template_file}")

                # 读取原始文件验证
                from astropy.io import fits
                with fits.open(template_file) as hdul_verify:
                    original_shape = hdul_verify[0].data.shape
                    original_crval1 = hdul_verify[0].header.get('CRVAL1', 'N/A')
                    original_crval2 = hdul_verify[0].header.get('CRVAL2', 'N/A')
                    self.logger.info(f"  调用process_fits_simple前 - 形状: {original_shape}, CRVAL1: {original_crval1}, CRVAL2: {original_crval2}")

                template_result = process_fits_simple(
                    template_file,
                    method=method,
                    threshold=4.0,
                    output_dir=output_dir
                )

                method_time = time.time() - method_start
                self.logger.info(f"  ⏱️  {method} 方法处理模板文件耗时: {method_time:.3f}秒")

                if template_result and len(template_result) >= 3:
                    repaired_data, noise_data, noise_mask = template_result
                    self.logger.info(f"  process_fits_simple返回 - 数据形状: {repaired_data.shape}")

                    if final_repaired_data is None:
                        # 第一次处理，直接使用结果
                        final_repaired_data = repaired_data.copy()
                        final_noise_data = noise_data.copy()
                        final_noise_mask = noise_mask.copy()
                        self.logger.debug(f"  第一次处理，数据形状: {final_repaired_data.shape}")
                    else:
                        # 后续处理，在前一次结果基础上继续处理
                        from astropy.io import fits

                        # 创建临时文件保存中间结果
                        with tempfile.NamedTemporaryFile(suffix='.fits', delete=False) as temp_file:
                            temp_filename = temp_file.name

                        # 读取原始文件的header
                        with fits.open(template_file) as hdul:
                            header = hdul[0].header.copy()

                        # 保存中间结果到临时文件
                        fits.writeto(temp_filename, final_repaired_data, header=header, overwrite=True)

                        # 对临时文件进行下一轮处理
                        next_result = process_fits_simple(
                            temp_filename,
                            method=method,
                            threshold=4.0,
                            output_dir=output_dir
                        )

                        # 清理临时文件
                        try:
                            os.unlink(temp_filename)
                        except:
                            pass

                        if next_result and len(next_result) >= 3:
                            final_repaired_data, next_noise_data, next_noise_mask = next_result
                            # 累积噪点数据和掩码
                            final_noise_data += next_noise_data
                            final_noise_mask |= next_noise_mask
                        else:
                            self.logger.warning(f"  {method} 方法处理失败，跳过")
                else:
                    self.logger.warning(f"  {method} 方法处理失败，跳过")

            template_result = (final_repaired_data, final_noise_data, final_noise_mask) if final_repaired_data is not None else None

            if template_result and len(template_result) >= 3:
                repaired_data, noise_data, noise_mask = template_result

                # 验证数据形状
                from astropy.io import fits
                with fits.open(template_file) as hdul:
                    original_data = hdul[0].data
                    original_shape = original_data.shape
                    header = hdul[0].header.copy()

                self.logger.debug(f"模板文件原始形状: {original_shape}")
                self.logger.debug(f"处理后数据形状: {repaired_data.shape}")

                # 检查数据形状是否一致
                if repaired_data.shape != original_shape:
                    self.logger.error("=" * 60)
                    self.logger.error("⚠️  降噪处理导致数据形状改变！")
                    self.logger.error(f"原始形状: {original_shape}")
                    self.logger.error(f"处理后形状: {repaired_data.shape}")
                    self.logger.error(f"模板文件: {template_file}")
                    self.logger.error("WCS信息可能不准确，使用原始文件代替")
                    self.logger.error("=" * 60)

                    # 删除process_fits_simple保存的错误文件
                    template_basename = os.path.splitext(os.path.basename(template_file))[0]
                    for suffix in ['_noise_cleaned.fits', '_adaptive_median_filtered.fits', '_simple_repaired.fits']:
                        error_file = os.path.join(output_dir, f"{template_basename}{suffix}")
                        if os.path.exists(error_file):
                            try:
                                os.remove(error_file)
                                self.logger.info(f"已删除错误的降噪文件: {os.path.basename(error_file)}")
                            except Exception as e:
                                self.logger.warning(f"无法删除文件 {error_file}: {str(e)}")

                    processed_template_file = template_file
                else:
                    # 保存处理后的模板文件
                    template_basename = os.path.splitext(os.path.basename(template_file))[0]
                    processed_template_file = os.path.join(output_dir, f"{template_basename}_noise_cleaned.fits")

                    # 调试：记录WCS关键信息
                    self.logger.debug(f"模板文件原始WCS - CRVAL1: {header.get('CRVAL1', 'N/A')}, CRVAL2: {header.get('CRVAL2', 'N/A')}")
                    self.logger.debug(f"模板文件原始WCS - CRPIX1: {header.get('CRPIX1', 'N/A')}, CRPIX2: {header.get('CRPIX2', 'N/A')}")

                    # 保存处理后的数据
                    fits.writeto(processed_template_file, repaired_data, header=header, overwrite=True)
                    self.logger.info(f"模板文件噪点处理完成，保存到: {os.path.basename(processed_template_file)}")

                    # 调试：验证保存后的WCS
                    with fits.open(processed_template_file) as hdul_check:
                        saved_header = hdul_check[0].header
                        saved_shape = hdul_check[0].data.shape
                        self.logger.debug(f"保存后的形状: {saved_shape}")
                        self.logger.debug(f"保存后的WCS - CRVAL1: {saved_header.get('CRVAL1', 'N/A')}, CRVAL2: {saved_header.get('CRVAL2', 'N/A')}")
                        self.logger.debug(f"保存后的WCS - CRPIX1: {saved_header.get('CRPIX1', 'N/A')}, CRPIX2: {saved_header.get('CRPIX2', 'N/A')}")
            else:
                self.logger.warning("模板文件噪点处理失败，使用原始文件")

            template_process_time = time.time() - template_process_start
            self.logger.info(f"⏱️  模板文件噪点处理总耗时: {template_process_time:.3f}秒")

        except Exception as e:
            self.logger.error(f"处理模板文件时出错: {str(e)}")
            self.logger.warning("使用原始模板文件")
            processed_template_file = template_file  # 确保使用原始文件

        self.logger.info("噪点处理步骤完成")
        return processed_download_file, processed_template_file

    def _validate_wcs_quality(self, wcs1: 'WCS', wcs2: 'WCS', data1: 'np.ndarray', data2: 'np.ndarray',
                              file1: str = "", file2: str = "") -> bool:
        """
        验证两个WCS的质量和兼容性

        Args:
            wcs1: 第一个WCS对象
            wcs2: 第二个WCS对象
            data1: 第一个图像数据
            data2: 第二个图像数据
            file1: 第一个文件路径（用于日志）
            file2: 第二个文件路径（用于日志）

        Returns:
            bool: True表示WCS质量良好，可以进行对齐
        """
        try:
            import numpy as np

            # 检查像素尺度差异
            scale1 = wcs1.proj_plane_pixel_scales()
            scale2 = wcs2.proj_plane_pixel_scales()
            scale_ratio_x = scale1[0] / scale2[0]
            scale_ratio_y = scale1[1] / scale2[1]

            self.logger.info(f"像素尺度比例: X={scale_ratio_x:.4f}, Y={scale_ratio_y:.4f}")

            if abs(scale_ratio_x - 1.0) > 0.2 or abs(scale_ratio_y - 1.0) > 0.2:  # 超过20%差异
                self.logger.warning(f"⚠️  像素尺度差异过大: X={scale_ratio_x:.3f}, Y={scale_ratio_y:.3f}")
                if file1 and file2:
                    self.logger.warning(f"模板文件: {file1}")
                    self.logger.warning(f"下载文件: {file2}")
                self.logger.warning("建议使用特征点对齐（Rigid）代替WCS对齐")
                return False

            # 检查中心坐标差异
            center1 = wcs1.pixel_to_world(data1.shape[1]/2, data1.shape[0]/2)
            center2 = wcs2.pixel_to_world(data2.shape[1]/2, data2.shape[0]/2)
            separation = center1.separation(center2).deg

            self.logger.info(f"中心坐标差异: {separation:.6f}度 = {separation*3600:.2f}角秒")

            if separation > 1.0:  # 超过1度
                self.logger.warning(f"⚠️  中心坐标差异过大: {separation:.3f}度")
                if file1 and file2:
                    self.logger.warning(f"模板文件: {file1}")
                    self.logger.warning(f"下载文件: {file2}")
                self.logger.warning("两个文件可能不是拍摄同一天区")
                return False

            # 记录旋转角度信息（仅用于调试，不影响对齐）
            try:
                # 获取PC矩阵（或CD矩阵）
                pc1 = wcs1.wcs.get_pc()
                pc2 = wcs2.wcs.get_pc()

                # 计算旋转角度
                rotation1 = np.arctan2(pc1[0, 1], pc1[0, 0]) * 180 / np.pi
                rotation2 = np.arctan2(pc2[0, 1], pc2[0, 0]) * 180 / np.pi

                # 计算角度差异（处理角度环绕）
                rotation_diff = abs(rotation1 - rotation2)
                if rotation_diff > 180:
                    rotation_diff = 360 - rotation_diff

                self.logger.info(f"旋转角度: 模板={rotation1:.2f}°, 下载={rotation2:.2f}°, 差异={rotation_diff:.2f}°")

                # 注意：旋转角度差异不应该影响WCS对齐，因为WCS信息本身就包含了旋转信息
                # WCS对齐是基于天球坐标系统的，可以处理任意旋转角度

            except Exception as e:
                self.logger.debug(f"无法计算旋转角度: {str(e)}")

            self.logger.info("✓ WCS质量验证通过")
            return True

        except Exception as e:
            self.logger.error(f"WCS质量验证失败: {str(e)}")
            return False

    def _align_using_wcs(self, template_file: str, download_file: str, output_dir: str) -> Optional[Dict]:
        """
        使用WCS信息进行图像对齐，失败时自动降级到特征点对齐

        Args:
            template_file (str): 模板文件路径
            download_file (str): 下载文件路径
            output_dir (str): 输出目录

        Returns:
            Optional[Dict]: 对齐结果字典
        """
        try:
            from astropy.io import fits
            from astropy.wcs import WCS
            from astropy.coordinates import SkyCoord
            from astropy import units as u
            import numpy as np
            from scipy.ndimage import map_coordinates

            wcs_align_start = time.time()
            self.logger.info("开始基于WCS信息的图像对齐...")
            self.logger.info(f"模板文件: {template_file}")
            self.logger.info(f"下载文件: {download_file}")

            # 读取两个文件的WCS信息
            read_template_start = time.time()
            self.logger.info("=" * 60)
            self.logger.info("步骤1.1: 读取模板文件WCS信息")
            self.logger.info("=" * 60)
            with fits.open(template_file) as hdul_template:
                template_header = hdul_template[0].header
                template_data = hdul_template[0].data.astype(np.float64)
                template_wcs = WCS(template_header)

                # 输出模板文件WCS关键信息
                self.logger.info(f"模板文件形状: {template_data.shape}")
                self.logger.info(f"模板CRVAL1 (RA参考点): {template_header.get('CRVAL1', 'N/A')}")
                self.logger.info(f"模板CRVAL2 (DEC参考点): {template_header.get('CRVAL2', 'N/A')}")
                self.logger.info(f"模板CRPIX1 (X参考像素): {template_header.get('CRPIX1', 'N/A')}")
                self.logger.info(f"模板CRPIX2 (Y参考像素): {template_header.get('CRPIX2', 'N/A')}")
                self.logger.info(f"模板CD1_1: {template_header.get('CD1_1', 'N/A')}")
                self.logger.info(f"模板CD2_2: {template_header.get('CD2_2', 'N/A')}")

                # 计算中心坐标
                center_x = template_data.shape[1] / 2
                center_y = template_data.shape[0] / 2
                center_coord = template_wcs.pixel_to_world(center_x, center_y)
                self.logger.info(f"模板中心像素: ({center_x:.1f}, {center_y:.1f})")
                self.logger.info(f"模板中心天球坐标: RA={center_coord.ra.deg:.6f}°, DEC={center_coord.dec.deg:.6f}°")

            read_template_time = time.time() - read_template_start
            self.logger.info(f"⏱️  读取模板文件WCS信息耗时: {read_template_time:.3f}秒")

            read_download_start = time.time()
            self.logger.info("=" * 60)
            self.logger.info("步骤1.2: 读取下载文件WCS信息")
            self.logger.info("=" * 60)
            with fits.open(download_file) as hdul_download:
                download_header = hdul_download[0].header
                download_data = hdul_download[0].data.astype(np.float64)
                download_wcs = WCS(download_header)

                # 输出下载文件WCS关键信息
                self.logger.info(f"下载文件形状: {download_data.shape}")
                self.logger.info(f"下载CRVAL1 (RA参考点): {download_header.get('CRVAL1', 'N/A')}")
                self.logger.info(f"下载CRVAL2 (DEC参考点): {download_header.get('CRVAL2', 'N/A')}")
                self.logger.info(f"下载CRPIX1 (X参考像素): {download_header.get('CRPIX1', 'N/A')}")
                self.logger.info(f"下载CRPIX2 (Y参考像素): {download_header.get('CRPIX2', 'N/A')}")
                self.logger.info(f"下载CD1_1: {download_header.get('CD1_1', 'N/A')}")
                self.logger.info(f"下载CD2_2: {download_header.get('CD2_2', 'N/A')}")

                # 计算中心坐标
                center_x = download_data.shape[1] / 2
                center_y = download_data.shape[0] / 2
                center_coord = download_wcs.pixel_to_world(center_x, center_y)
                self.logger.info(f"下载中心像素: ({center_x:.1f}, {center_y:.1f})")
                self.logger.info(f"下载中心天球坐标: RA={center_coord.ra.deg:.6f}°, DEC={center_coord.dec.deg:.6f}°")

            read_download_time = time.time() - read_download_start
            self.logger.info(f"⏱️  读取下载文件WCS信息耗时: {read_download_time:.3f}秒")

            # 检查WCS信息是否有效
            if not template_wcs.has_celestial or not download_wcs.has_celestial:
                self.logger.error("=" * 60)
                self.logger.error("WCS对齐失败：文件缺少有效的WCS天体坐标信息")
                self.logger.error(f"模板文件: {template_file}")
                self.logger.error(f"下载文件: {download_file}")
                self.logger.error("建议使用特征点对齐（Rigid）代替WCS对齐")
                self.logger.error("=" * 60)
                return None

            # 验证WCS质量
            validate_start = time.time()
            self.logger.info("=" * 60)
            self.logger.info("步骤1.3: 验证WCS质量和兼容性")
            self.logger.info("=" * 60)
            if not self._validate_wcs_quality(template_wcs, download_wcs, template_data, download_data,
                                               template_file, download_file):
                self.logger.error("=" * 60)
                self.logger.error("WCS对齐失败：WCS质量验证失败")
                self.logger.error(f"模板文件: {template_file}")
                self.logger.error(f"下载文件: {download_file}")
                self.logger.error("建议使用特征点对齐（Rigid）代替WCS对齐")
                self.logger.error("=" * 60)
                return None

            validate_time = time.time() - validate_start
            self.logger.info(f"⏱️  WCS质量验证耗时: {validate_time:.3f}秒")

            transform_start = time.time()
            self.logger.info("WCS信息验证通过，开始坐标变换...")

            # 创建模板图像的像素坐标网格
            template_shape = template_data.shape
            y_indices, x_indices = np.mgrid[0:template_shape[0], 0:template_shape[1]]

            # 将模板图像的像素坐标转换为天体坐标
            template_coords = template_wcs.pixel_to_world(x_indices, y_indices)

            # 将天体坐标转换为下载图像的像素坐标
            download_x, download_y = download_wcs.world_to_pixel(template_coords)

            transform_time = time.time() - transform_start
            self.logger.info(f"⏱️  坐标变换耗时: {transform_time:.3f}秒")

            # 检查有效坐标范围
            valid_mask = (
                (download_x >= 0) & (download_x < download_data.shape[1]) &
                (download_y >= 0) & (download_y < download_data.shape[0]) &
                np.isfinite(download_x) & np.isfinite(download_y)
            )

            valid_ratio = np.sum(valid_mask) / valid_mask.size
            self.logger.info(f"有效重叠区域比例: {valid_ratio:.2%}")

            if valid_ratio < 0.1:  # 重叠区域小于10%
                self.logger.warning(f"重叠区域过小 ({valid_ratio:.2%})，WCS对齐可能不准确")
                self.logger.warning("自动降级到特征点对齐（Rigid）")
                return self._align_using_features(template_file, download_file, output_dir)

            # 使用插值将下载图像重采样到模板图像的坐标系
            resample_start = time.time()
            self.logger.info("执行图像重采样...")

            # 创建坐标数组用于插值
            coords = np.array([download_y.flatten(), download_x.flatten()])

            # 使用双线性插值重采样下载图像
            aligned_download_data = map_coordinates(
                download_data,
                coords,
                order=1,  # 双线性插值
                cval=0.0,  # 边界外的值设为0
                prefilter=False
            ).reshape(template_shape)

            resample_time = time.time() - resample_start
            self.logger.info(f"⏱️  图像重采样耗时: {resample_time:.3f}秒")

            save_start = time.time()
            self.logger.info("WCS对齐完成，保存对齐后的文件...")

            # 保存对齐后的文件
            template_basename = os.path.splitext(os.path.basename(template_file))[0]
            download_basename = os.path.splitext(os.path.basename(download_file))[0]

            # 保存对齐后的模板文件（实际上就是原文件的副本）
            aligned_template_file = os.path.join(output_dir, f"{template_basename}_aligned.fits")
            fits.writeto(aligned_template_file, template_data, header=template_header, overwrite=True)

            # 保存对齐后的下载文件
            aligned_download_file = os.path.join(output_dir, f"{download_basename}_aligned.fits")
            # 使用模板文件的WCS信息作为对齐后文件的header
            aligned_header = template_header.copy()
            # 更新一些关键信息
            aligned_header['HISTORY'] = 'Aligned using WCS information'
            fits.writeto(aligned_download_file, aligned_download_data, header=aligned_header, overwrite=True)

            save_time = time.time() - save_start
            self.logger.info(f"⏱️  保存对齐文件耗时: {save_time:.3f}秒")

            # 创建结果字典
            total_wcs_time = time.time() - wcs_align_start

            result = {
                'alignment_success': True,
                'alignment_method': 'wcs',
                'template_aligned_file': aligned_template_file,
                'download_aligned_file': aligned_download_file,
                'output_directory': output_dir,
                'wcs_info': {
                    'template_wcs_valid': True,
                    'download_wcs_valid': True,
                    'coordinate_system': template_wcs.wcs.ctype[0] if hasattr(template_wcs.wcs, 'ctype') else 'Unknown'
                }
            }

            self.logger.info("=" * 60)
            self.logger.info("⏱️  WCS对齐耗时统计:")
            self.logger.info(f"  读取模板WCS: {read_template_time:.3f}秒")
            self.logger.info(f"  读取下载WCS: {read_download_time:.3f}秒")
            self.logger.info(f"  WCS质量验证: {validate_time:.3f}秒")
            self.logger.info(f"  坐标变换: {transform_time:.3f}秒")
            self.logger.info(f"  图像重采样: {resample_time:.3f}秒")
            self.logger.info(f"  保存对齐文件: {save_time:.3f}秒")
            self.logger.info(f"  WCS对齐总耗时: {total_wcs_time:.3f}秒")
            self.logger.info("=" * 60)

            self.logger.info(f"WCS对齐成功完成")
            self.logger.info(f"对齐后的模板文件: {os.path.basename(aligned_template_file)}")
            self.logger.info(f"对齐后的下载文件: {os.path.basename(aligned_download_file)}")

            return result

        except ImportError as e:
            self.logger.error("=" * 60)
            self.logger.error(f"WCS对齐失败：需要astropy库 - {str(e)}")
            self.logger.error(f"模板文件: {template_file}")
            self.logger.error(f"下载文件: {download_file}")
            self.logger.error("建议使用特征点对齐（Rigid）代替WCS对齐")
            self.logger.error("=" * 60)
            return None
        except Exception as e:
            self.logger.error("=" * 60)
            self.logger.error(f"WCS对齐失败：{str(e)}")
            self.logger.error(f"模板文件: {template_file}")
            self.logger.error(f"下载文件: {download_file}")
            self.logger.error("建议使用特征点对齐（Rigid）代替WCS对齐")
            self.logger.error("=" * 60)
            return None


# 测试代码
if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    integration = DiffOrbIntegration()
    
    print("diff_orb集成测试")
    print("=" * 50)
    print(f"diff_orb可用: {integration.is_available()}")
    
    if integration.is_available():
        # 测试文件名解析
        test_file = "download_GY5_20250718_K096_001.fits"
        test_template_dir = "/path/to/templates"
        
        can_process, status = integration.can_process_file(test_file, test_template_dir)
        print(f"可以处理文件: {can_process}")
        print(f"状态: {status}")
    else:
        print("diff_orb模块不可用，请检查安装")
