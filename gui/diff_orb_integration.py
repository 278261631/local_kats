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
        k_number = parsed_info.get('k_number', '')
        
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
            k_number = parsed_info.get('k_number', '')
            
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
    
    def process_diff(self, download_file: str, template_file: str, output_dir: str = None) -> Optional[Dict]:
        """
        执行diff操作
        
        Args:
            download_file (str): 下载文件路径（作为待比较文件）
            template_file (str): 模板文件路径（作为参考文件）
            output_dir (str): 输出目录，如果为None则自动创建
            
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

            # 步骤1: 先进行图像对齐
            self.logger.info("步骤1: 执行图像对齐...")
            alignment_result = self.alignment_comparator.process_fits_comparison(
                template_file,      # 参考文件（模板）
                download_file,      # 待比较文件（下载）
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
