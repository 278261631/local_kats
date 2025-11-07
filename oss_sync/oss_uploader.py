"""
阿里云 OSS 文件上传工具
用于将本地文件上传到阿里云 OSS 存储，按照 yyyy/yyyymmdd/ 的路径结构组织
"""

import os
import sys
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
try:
    import oss2
except Exception as e:
    print("✗ 缺少依赖或导入 oss2 失败。请先安装依赖: pip install -r oss_sync/requirements.txt")
    print(f"详细错误: {e}")
    import sys
    sys.exit(1)
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import subprocess
import shutil



class OSSUploader:
    """阿里云 OSS 上传器"""

    def __init__(self, config_file: str = "oss_config.json"):
        """
        初始化上传器

        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self._load_config()
        self.logger = self._setup_logging()

        # 初始化 OSS 客户端
        self.auth = None
        self.bucket = None
        self._init_oss_client()

    def _load_config(self) -> Dict:
        """加载配置文件"""
        if not os.path.exists(self.config_file):
            # 如果配置文件不存在，尝试从模板创建
            template_file = self.config_file + ".template"
            if os.path.exists(template_file):
                print(f"配置文件不存在，正在从模板创建: {self.config_file}")
                with open(template_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                print(f"请编辑配置文件 {self.config_file} 并填写必要的信息")
                sys.exit(1)
            else:
                raise FileNotFoundError(f"配置文件不存在: {self.config_file}")

        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 验证必要的配置项
        required_fields = ['access_key_id', 'access_key_secret', 'bucket_name']
        for field in required_fields:
            if not config['aliyun_oss'].get(field):
                raise ValueError(f"配置文件中缺少必要字段: aliyun_oss.{field}")

        if not config['upload_settings'].get('oss_root'):
            raise ValueError("配置文件中缺少必要字段: upload_settings.oss_root")

        return config

    def _setup_logging(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger('OSSUploader')
        logger.setLevel(logging.INFO)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 文件处理器
        log_file = Path(__file__).parent / 'oss_upload.log'
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        # 格式化
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        return logger

    def _init_oss_client(self):
        """初始化 OSS 客户端"""
        try:
            oss_config = self.config['aliyun_oss']
            self.auth = oss2.Auth(
                oss_config['access_key_id'],
                oss_config['access_key_secret']
            )
            self.bucket = oss2.Bucket(
                self.auth,
                oss_config['endpoint'],
                oss_config['bucket_name']
            )
            self.logger.info(f"OSS 客户端初始化成功: {oss_config['bucket_name']}")
        except Exception as e:
            self.logger.error(f"OSS 客户端初始化失败: {str(e)}")
            raise

    def _get_file_md5(self, file_path: str) -> str:
        """计算文件 MD5"""
        md5_hash = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()

    def _extract_date_from_path(self, file_path: Path) -> Optional[datetime]:
        """
        从文件路径中提取日期
        优先从文件名中的 UTC 时间戳提取，如果失败则从路径中的日期目录提取

        Args:
            file_path: 文件路径

        Returns:
            提取的日期，如果提取失败则返回 None
        """
        # 方法1: 从文件名中提取 UTC 时间戳
        # 格式: GY5_K052-1_No%20Filter_60S_Bin2_UTC20251102_131726_-19.9C_
        path_str = str(file_path)

        # 匹配 UTC 后面的日期 (YYYYMMDD)
        utc_match = re.search(r'UTC(\d{8})_', path_str)
        if utc_match:
            date_str = utc_match.group(1)
            try:
                return datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                pass

        # 方法2: 从路径中的日期目录提取
        # 格式: GY5/20251102/K052/...
        parts = file_path.parts
        for part in parts:
            # 检查是否是8位数字的日期格式
            if re.match(r'^\d{8}$', part):
                try:
                    return datetime.strptime(part, "%Y%m%d")
                except ValueError:
                    pass

        # 方法3: 如果都失败，返回 None
        return None

    def _get_batch_date(self, oss_root: Path) -> Optional[datetime]:
        """
        从oss_root目录中提取批次日期
        优先从HTML文件名提取，其次从目录结构提取

        Args:
            oss_root: OSS 根目录

        Returns:
            批次日期，如果提取失败则返回 None
        """
        # 方法1: 从HTML文件名提取日期
        # 格式: detection_results_20251102.html
        html_files = list(oss_root.glob("detection_results_*.html"))
        if html_files:
            html_file = html_files[0]
            match = re.search(r'detection_results_(\d{8})\.html', html_file.name)
            if match:
                date_str = match.group(1)
                try:
                    return datetime.strptime(date_str, "%Y%m%d")
                except ValueError:
                    pass

        # 方法2: 从目录结构中提取日期
        # 遍历所有文件，找到第一个包含日期的路径
        for file_path in oss_root.rglob("*"):
            if file_path.is_file():
                file_date = self._extract_date_from_path(file_path)
                if file_date:
                    return file_date

        return None

    def _get_oss_path(self, local_file: Path, oss_root: Path, batch_date: datetime) -> str:
        """
        根据文件路径生成 OSS 路径
        格式: yyyy/yyyymmdd/相对路径（原样保留，不再移除相对路径中的日期目录）

        Args:
            local_file: 本地文件路径
            oss_root: OSS 根目录
            batch_date: 批次日期(所有文件使用同一个日期)

        Returns:
            OSS 对象路径
        """
        # 获取相对于 oss_root 的路径
        try:
            relative_path = local_file.relative_to(oss_root)
        except ValueError:
            # 如果文件不在 oss_root 下，使用文件名
            relative_path = Path(local_file.name)

        # 使用批次日期
        year = batch_date.strftime("%Y")
        date_str = batch_date.strftime("%Y%m%d")

        # 这里不再移除相对路径中的日期目录，保持导出目录结构：GY5/20251102/K021/...
        cleaned_relative_path = relative_path

        oss_path = f"{year}/{date_str}/{cleaned_relative_path.as_posix()}"

        return oss_path

    def _find_7z_executable(self) -> Optional[str]:
        """查找 7z 可执行程序"""
        try:
            path = shutil.which("7z") or shutil.which("7z.exe")
        except Exception:
            path = None
        if path:
            return path
        common = Path("C:/Program Files/7-Zip/7z.exe")
        if common.exists():
            return str(common)
        return None

    def _create_7z_archive(self, oss_root: Path, batch_date: datetime) -> Path:
        """
        将 oss_root 目录打包为 7z 压缩包，文件名: oss_root_yyyymmdd.7z，存放在其父目录
        """
        date_str = batch_date.strftime("%Y%m%d")
        archive_name = f"{oss_root.name}_{date_str}.7z"
        archive_path = oss_root.parent / archive_name

        # 如果已存在则删除以便重建
        try:
            if archive_path.exists():
                self.logger.info(f"目标压缩包已存在，删除后重新生成: {archive_path}")
                archive_path.unlink()
        except Exception as e:
            self.logger.warning(f"无法删除已存在压缩包，将覆盖创建: {archive_path} - {e}")

        self.logger.info("=" * 60)
        self.logger.info(f"开始打包为 7z: {archive_path}")
        self.logger.info(f"打包源目录: {oss_root}")

        # 首选使用 py7zr
        try:
            import py7zr  # type: ignore
            with py7zr.SevenZipFile(str(archive_path), 'w') as archive:
                # 确保压缩包内包含顶层目录名 oss_root.name
                archive.writeall(str(oss_root), arcname=oss_root.name)
            self.logger.info(f"✓ 7z 打包完成 (py7zr): {archive_path}")
        except Exception as py7zr_err:
            self.logger.info(f"未能使用 py7zr 打包，将尝试系统 7z 命令行。原因: {py7zr_err}")
            sevenz = self._find_7z_executable()
            if not sevenz:
                raise RuntimeError(
                    "未找到 py7zr 或 7z 可执行程序。请安装任一其一后重试：\n"
                    "  pip install py7zr\n"
                    "或安装 7-Zip 并将 7z 加入 PATH"
                ) from py7zr_err
            # 在父目录下执行: 7z a -t7z archive.7z oss_root_name
            cmd = [sevenz, 'a', '-t7z', str(archive_path), oss_root.name]
            try:
                completed = subprocess.run(
                    cmd, cwd=str(oss_root.parent), capture_output=True, text=True
                )
                if completed.returncode != 0:
                    raise RuntimeError(f"7z 命令执行失败: {completed.stderr or completed.stdout}")
                self.logger.info(f" 7z 打包完成 (7z CLI): {archive_path}")
            except Exception as cli_err:
                raise RuntimeError(f"7z 打包失败: {cli_err}") from cli_err

        # 日志记录打包后大小
        try:
            size_mb = archive_path.stat().st_size / (1024 * 1024)
            self.logger.info(f"压缩包大小: {size_mb:.2f} MB")
        except Exception:
            pass

        self.logger.info("=" * 60)
        return archive_path

    def _upload_file(self, local_file: Path, oss_path: str, retry_times: int = 3) -> Dict:
        """
        上传单个文件到 OSS

        Args:
            local_file: 本地文件路径
            oss_path: OSS 对象路径
            retry_times: 重试次数

        Returns:
            上传结果字典: {'success': bool, 'skipped': bool, 'file': str, 'oss_path': str}
        """
        result = {
            'success': False,
            'skipped': False,
            'file': str(local_file),
            'oss_path': oss_path
        }

        for attempt in range(retry_times):
            try:
                # 检查文件是否已存在
                try:
                    remote_meta = self.bucket.get_object_meta(oss_path)
                    remote_size = int(remote_meta.headers.get('Content-Length', 0))
                    local_size = os.path.getsize(local_file)

                    if remote_size == local_size:
                        self.logger.info(f"⊙ 跳过(已存在): {local_file.name}")
                        result['success'] = True
                        result['skipped'] = True
                        return result
                except oss2.exceptions.NoSuchKey:
                    # 文件不存在，继续上传
                    pass

                # 显示上传开始信息
                file_size_mb = os.path.getsize(local_file) / (1024 * 1024)
                self.logger.info(f"↑ 正在上传: {local_file.name} ({file_size_mb:.2f} MB)")

                # 上传文件
                timeout = self.config['upload_settings'].get('timeout', 300)
                self.bucket.put_object_from_file(oss_path, str(local_file),
                                                  headers={'x-oss-storage-class': 'Standard'})

                # 验证上传
                remote_meta = self.bucket.get_object_meta(oss_path)
                remote_size = int(remote_meta.headers.get('Content-Length', 0))
                local_size = os.path.getsize(local_file)

                if remote_size == local_size:
                    self.logger.info(f"✓ 上传成功: {local_file.name} -> {oss_path}")
                    result['success'] = True
                    return result
                else:
                    self.logger.warning(f"⚠ 文件大小不匹配: 本地={local_size}, 远程={remote_size}")

            except Exception as e:
                self.logger.warning(f"✗ 上传失败 (尝试 {attempt + 1}/{retry_times}): {local_file.name} - {str(e)}")
                if attempt == retry_times - 1:
                    self.logger.error(f"✗ 最终失败: {local_file.name}")
                    return result

        return result

    def scan_files(self, root_dir: Path, extensions: List[str]) -> List[Path]:
        """
        扫描目录下的所有文件

        Args:
            root_dir: 根目录
            extensions: 文件扩展名列表

        Returns:
            文件路径列表
        """
        files = []
        self.logger.info("=" * 60)
        self.logger.info(f"开始扫描目录: {root_dir}")
        self.logger.info(f"扫描文件类型: {', '.join(extensions)}")
        self.logger.info("=" * 60)

        for ext in extensions:
            pattern = f"**/*{ext}"
            self.logger.info(f"正在扫描 {ext} 文件...")
            matched_files = list(root_dir.glob(pattern))
            files.extend(matched_files)
            if matched_files:
                # 计算总大小
                total_size = sum(f.stat().st_size for f in matched_files)
                total_size_mb = total_size / (1024 * 1024)
                self.logger.info(f"  找到 {len(matched_files)} 个 {ext} 文件 (总大小: {total_size_mb:.2f} MB)")
            else:
                self.logger.info(f"  未找到 {ext} 文件")

        if files:
            total_size = sum(f.stat().st_size for f in files)
            total_size_mb = total_size / (1024 * 1024)
            self.logger.info("=" * 60)
            self.logger.info(f"扫描完成: 总共找到 {len(files)} 个文件 (总大小: {total_size_mb:.2f} MB)")
            self.logger.info("=" * 60)
        else:
            self.logger.warning("=" * 60)
            self.logger.warning("未找到任何文件")
            self.logger.warning("=" * 60)

        return files

    def upload_files(self, files: List[Path], oss_root: Path, max_workers: int = 4):
        """
        批量上传文件

        Args:
            files: 文件列表
            oss_root: OSS 根目录
            max_workers: 最大并发数
        """
        if not files:
            self.logger.warning("没有文件需要上传")
            return

        # 获取批次日期
        batch_date = self._get_batch_date(oss_root)
        if batch_date is None:
            self.logger.error("✗ 无法从目录中提取批次日期，上传终止")
            return

        self.logger.info("=" * 60)
        self.logger.info(f"批次日期: {batch_date.strftime('%Y%m%d')}")
        self.logger.info(f"开始上传 {len(files)} 个文件")
        self.logger.info(f"并发数: {max_workers}")
        self.logger.info("=" * 60)

        success_count = 0
        failed_count = 0
        skipped_count = 0

        retry_times = self.config['upload_settings'].get('retry_times', 3)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有上传任务
            future_to_file = {}
            for file in files:
                try:
                    oss_path = self._get_oss_path(file, oss_root, batch_date)
                    future = executor.submit(self._upload_file, file, oss_path, retry_times)
                    future_to_file[future] = (file, oss_path)
                except Exception as e:
                    # 生成OSS路径失败，记录错误并跳过该文件
                    self.logger.error(f"✗ 跳过文件(生成OSS路径失败): {file.name} - {str(e)}")
                    failed_count += 1

            # 处理完成的任务
            for i, future in enumerate(as_completed(future_to_file), 1):
                file, oss_path = future_to_file[future]
                try:
                    result = future.result()
                    if result['success']:
                        if result['skipped']:
                            skipped_count += 1
                        else:
                            success_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    self.logger.error(f"✗ 上传异常: {file.name} - {str(e)}")
                    failed_count += 1

                # 显示进度 - 每处理一个文件都显示进度
                progress_percent = (i / len(files)) * 100
                self.logger.info(f"进度: {i}/{len(files)} ({progress_percent:.1f}%) - 新上传: {success_count}, 跳过: {skipped_count}, 失败: {failed_count}")

        # 输出统计
        self.logger.info("=" * 60)
        self.logger.info("上传完成")
        self.logger.info(f"总文件数: {len(files)}")
        self.logger.info(f"新上传: {success_count}")
        self.logger.info(f"跳过(已存在): {skipped_count}")
        self.logger.info(f"失败: {failed_count}")
        self.logger.info("=" * 60)

    def run(self):
        """运行上传任务"""
        try:
            # 获取配置
            upload_settings = self.config['upload_settings']
            oss_root = Path(upload_settings['oss_root'])

            self.logger.info("=" * 60)
            self.logger.info("OSS 上传任务配置")
            self.logger.info(f"上传根目录: {oss_root}")
            self.logger.info(f"OSS Bucket: {self.config['aliyun_oss']['bucket_name']}")
            self.logger.info(f"OSS Endpoint: {self.config['aliyun_oss']['endpoint']}")
            self.logger.info("=" * 60)

            if not oss_root.exists():
                self.logger.error(f"✗ OSS 根目录不存在: {oss_root}")
                return

            # 统一确定批次日期用于归档和上传路径
            batch_date = self._get_batch_date(oss_root)
            if batch_date is None:
                self.logger.error("✗ 无法从目录中提取批次日期，上传终止")
                return

            # 先将目录打包成 7z 压缩包：oss_root_yyyymmdd.7z
            archive_path = self._create_7z_archive(oss_root, batch_date)

            # 上传压缩包（按 yyyy/yyyymmdd/oss_root_yyyymmdd.7z 存放）
            self.upload_files([archive_path], oss_root, max_workers=1)

        except Exception as e:
            self.logger.error("=" * 60)
            self.logger.error(f"✗ 上传任务失败: {str(e)}", exc_info=True)
            self.logger.error("=" * 60)


def main():
    """主函数"""
    print("=" * 60)
    print("阿里云 OSS 文件上传工具")
    print("=" * 60)
    print()

    try:
        # 创建上传器
        uploader = OSSUploader()

        # 运行上传
        uploader.run()

        print()
        print("=" * 60)
        print("✓ 上传任务完成")
        print("详细日志请查看: oss_upload.log")
        print("=" * 60)
    except Exception as e:
        print()
        print("=" * 60)
        print(f"✗ 上传任务失败: {str(e)}")
        print("详细日志请查看: oss_upload.log")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()

