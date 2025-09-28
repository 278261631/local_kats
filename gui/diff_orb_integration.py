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
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.filename_parser = FITSFilenameParser()
        
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
    
    def process_diff(self, download_file: str, template_file: str, output_dir: str = None, noise_methods: list = None, alignment_method: str = 'rigid') -> Optional[Dict]:
        """
        执行diff操作

        Args:
            download_file (str): 下载文件路径（作为待比较文件）
            template_file (str): 模板文件路径（作为参考文件）
            output_dir (str): 输出目录，如果为None则自动创建
            noise_methods (list): 降噪方式列表，可选值：['outlier', 'hot_cold', 'adaptive_median']
            alignment_method (str): 对齐方式，可选值：['rigid', 'wcs']

        Returns:
            Optional[Dict]: 处理结果字典，包含输出文件路径等信息
        """
        if not self.diff_orb_available:
            self.logger.error("diff_orb模块不可用")
            return None
        
        try:
            # 验证输入文件
            if not os.path.exists(download_file):
                self.logger.error(f"下载文件不存在: {download_file}")
                return None
            
            if not os.path.exists(template_file):
                self.logger.error(f"模板文件不存在: {template_file}")
                return None
            
            # 创建输出目录
            if output_dir is None:
                output_dir = tempfile.mkdtemp(prefix="diff_orb_results_")
            else:
                os.makedirs(output_dir, exist_ok=True)
            
            self.logger.info(f"开始diff操作:")
            self.logger.info(f"  参考文件 (模板): {os.path.basename(template_file)}")
            self.logger.info(f"  待比较文件 (下载): {os.path.basename(download_file)}")
            self.logger.info(f"  输出目录: {output_dir}")

            # 步骤0: 噪点处理
            processed_download_file, processed_template_file = self._preprocess_noise_removal(
                download_file, template_file, output_dir, noise_methods
            )

            # 步骤1: 根据选择的对齐方式进行图像对齐
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

            if not alignment_result or not alignment_result.get('alignment_success'):
                self.logger.error("图像对齐失败")
                return None

            # 步骤2: 使用已对齐文件进行差异比较
            self.logger.info("步骤2: 执行已对齐文件差异比较...")
            result = self.aligned_comparator.process_aligned_fits_comparison(
                output_dir,  # 输入目录（包含对齐后的文件）
                output_dir   # 输出目录（同一目录）
            )
            
            if result:
                self.logger.info(f"diff操作成功完成")
                self.logger.info(f"  对齐成功: {result.get('alignment_success', False)}")
                self.logger.info(f"  检测到新亮点: {result.get('new_bright_spots', 0)} 个")
                
                # 收集输出文件信息
                output_files = self._collect_output_files(output_dir)
                
                return {
                    'success': True,
                    'alignment_success': result.get('alignment_success', False),
                    'new_bright_spots': result.get('new_bright_spots', 0),
                    'output_directory': output_dir,
                    'output_files': output_files,
                    'reference_file': template_file,
                    'compared_file': download_file
                }
            else:
                self.logger.error("diff操作失败")
                return None
                
        except Exception as e:
            self.logger.error(f"执行diff操作时出错: {str(e)}")
            return None
    
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

        self.logger.info(f"步骤0: 执行噪点处理，使用方法: {', '.join(noise_methods)}")

        processed_download_file = download_file
        processed_template_file = template_file

        try:
            # 处理下载文件（观测文件）
            self.logger.info(f"处理观测文件: {os.path.basename(download_file)}")

            # 对每种降噪方式进行处理
            final_repaired_data = None
            final_noise_data = None
            final_noise_mask = None

            for method in noise_methods:
                self.logger.info(f"  使用 {method} 方法处理观测文件")
                download_result = process_fits_simple(
                    download_file,
                    method=method,
                    threshold=4.0,
                    output_dir=output_dir
                )

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

                # 保存处理后的观测文件
                download_basename = os.path.splitext(os.path.basename(download_file))[0]
                processed_download_file = os.path.join(output_dir, f"{download_basename}_noise_cleaned.fits")

                # 读取原始文件的header
                from astropy.io import fits
                with fits.open(download_file) as hdul:
                    header = hdul[0].header.copy()

                # 保存处理后的数据
                fits.writeto(processed_download_file, repaired_data, header=header, overwrite=True)
                self.logger.info(f"观测文件噪点处理完成，保存到: {os.path.basename(processed_download_file)}")
            else:
                self.logger.warning("观测文件噪点处理失败，使用原始文件")

        except Exception as e:
            self.logger.error(f"处理观测文件时出错: {str(e)}")
            self.logger.warning("使用原始观测文件")

        try:
            # 处理模板文件
            self.logger.info(f"处理模板文件: {os.path.basename(template_file)}")

            # 对每种降噪方式进行处理
            final_repaired_data = None
            final_noise_data = None
            final_noise_mask = None

            for method in noise_methods:
                self.logger.info(f"  使用 {method} 方法处理模板文件")
                template_result = process_fits_simple(
                    template_file,
                    method=method,
                    threshold=4.0,
                    output_dir=output_dir
                )

                if template_result and len(template_result) >= 3:
                    repaired_data, noise_data, noise_mask = template_result

                    if final_repaired_data is None:
                        # 第一次处理，直接使用结果
                        final_repaired_data = repaired_data.copy()
                        final_noise_data = noise_data.copy()
                        final_noise_mask = noise_mask.copy()
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

                # 保存处理后的模板文件
                template_basename = os.path.splitext(os.path.basename(template_file))[0]
                processed_template_file = os.path.join(output_dir, f"{template_basename}_noise_cleaned.fits")

                # 读取原始文件的header
                from astropy.io import fits
                with fits.open(template_file) as hdul:
                    header = hdul[0].header.copy()

                # 保存处理后的数据
                fits.writeto(processed_template_file, repaired_data, header=header, overwrite=True)
                self.logger.info(f"模板文件噪点处理完成，保存到: {os.path.basename(processed_template_file)}")
            else:
                self.logger.warning("模板文件噪点处理失败，使用原始文件")

        except Exception as e:
            self.logger.error(f"处理模板文件时出错: {str(e)}")
            self.logger.warning("使用原始模板文件")

        self.logger.info("噪点处理步骤完成")
        return processed_download_file, processed_template_file

    def _align_using_wcs(self, template_file: str, download_file: str, output_dir: str) -> Optional[Dict]:
        """
        使用WCS信息进行图像对齐

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

            self.logger.info("开始基于WCS信息的图像对齐...")

            # 读取两个文件的WCS信息
            with fits.open(template_file) as hdul_template:
                template_header = hdul_template[0].header
                template_data = hdul_template[0].data.astype(np.float64)
                template_wcs = WCS(template_header)

            with fits.open(download_file) as hdul_download:
                download_header = hdul_download[0].header
                download_data = hdul_download[0].data.astype(np.float64)
                download_wcs = WCS(download_header)

            # 检查WCS信息是否有效
            if not template_wcs.has_celestial or not download_wcs.has_celestial:
                self.logger.error("文件缺少有效的WCS天体坐标信息")
                return None

            self.logger.info("WCS信息验证通过，开始坐标变换...")

            # 创建模板图像的像素坐标网格
            template_shape = template_data.shape
            y_indices, x_indices = np.mgrid[0:template_shape[0], 0:template_shape[1]]

            # 将模板图像的像素坐标转换为天体坐标
            template_coords = template_wcs.pixel_to_world(x_indices, y_indices)

            # 将天体坐标转换为下载图像的像素坐标
            download_x, download_y = download_wcs.world_to_pixel(template_coords)

            # 使用插值将下载图像重采样到模板图像的坐标系
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

            # 创建结果字典
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

            self.logger.info(f"WCS对齐成功完成")
            self.logger.info(f"对齐后的模板文件: {os.path.basename(aligned_template_file)}")
            self.logger.info(f"对齐后的下载文件: {os.path.basename(aligned_download_file)}")

            return result

        except ImportError as e:
            self.logger.error(f"WCS对齐需要astropy库: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"WCS对齐失败: {str(e)}")
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
