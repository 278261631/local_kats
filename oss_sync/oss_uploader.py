"""
阿里云 OSS 文件上传工具
用于将本地文件上传到阿里云 OSS 存储，按照 yyyy/yyyymmdd/ 的路径结构组织
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import oss2
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib


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
    
    def _get_oss_path(self, local_file: Path, oss_root: Path) -> str:
        """
        根据文件路径生成 OSS 路径
        格式: yyyy/yyyymmdd/原始相对路径
        
        Args:
            local_file: 本地文件路径
            oss_root: OSS 根目录
            
        Returns:
            OSS 对象路径
        """
        # 获取相对于 oss_root 的路径
        try:
            relative_path = local_file.relative_to(oss_root)
        except ValueError:
            # 如果文件不在 oss_root 下，使用文件名
            relative_path = Path(local_file.name)
        
        # 从文件修改时间获取日期
        mtime = os.path.getmtime(local_file)
        file_date = datetime.fromtimestamp(mtime)
        
        # 构建路径: yyyy/yyyymmdd/原始相对路径
        year = file_date.strftime("%Y")
        date_str = file_date.strftime("%Y%m%d")
        
        oss_path = f"{year}/{date_str}/{relative_path.as_posix()}"
        
        return oss_path
    
    def _upload_file(self, local_file: Path, oss_path: str, retry_times: int = 3) -> bool:
        """
        上传单个文件到 OSS
        
        Args:
            local_file: 本地文件路径
            oss_path: OSS 对象路径
            retry_times: 重试次数
            
        Returns:
            是否上传成功
        """
        for attempt in range(retry_times):
            try:
                # 检查文件是否已存在
                try:
                    remote_meta = self.bucket.get_object_meta(oss_path)
                    remote_size = int(remote_meta.headers.get('Content-Length', 0))
                    local_size = os.path.getsize(local_file)
                    
                    if remote_size == local_size:
                        self.logger.info(f"文件已存在且大小相同，跳过: {oss_path}")
                        return True
                except oss2.exceptions.NoSuchKey:
                    # 文件不存在，继续上传
                    pass
                
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
                    return True
                else:
                    self.logger.warning(f"文件大小不匹配: 本地={local_size}, 远程={remote_size}")
                    
            except Exception as e:
                self.logger.warning(f"上传失败 (尝试 {attempt + 1}/{retry_times}): {local_file.name} - {str(e)}")
                if attempt == retry_times - 1:
                    self.logger.error(f"✗ 上传失败: {local_file.name}")
                    return False
        
        return False
    
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
        self.logger.info(f"开始扫描目录: {root_dir}")
        
        for ext in extensions:
            pattern = f"**/*{ext}"
            matched_files = list(root_dir.glob(pattern))
            files.extend(matched_files)
            self.logger.info(f"找到 {len(matched_files)} 个 {ext} 文件")
        
        self.logger.info(f"总共找到 {len(files)} 个文件")
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
        
        self.logger.info("=" * 60)
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
                oss_path = self._get_oss_path(file, oss_root)
                future = executor.submit(self._upload_file, file, oss_path, retry_times)
                future_to_file[future] = (file, oss_path)
            
            # 处理完成的任务
            for i, future in enumerate(as_completed(future_to_file), 1):
                file, oss_path = future_to_file[future]
                try:
                    result = future.result()
                    if result:
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    self.logger.error(f"上传异常: {file.name} - {str(e)}")
                    failed_count += 1
                
                # 显示进度
                if i % 10 == 0 or i == len(files):
                    self.logger.info(f"进度: {i}/{len(files)} - 成功: {success_count}, 失败: {failed_count}")
        
        # 输出统计
        self.logger.info("=" * 60)
        self.logger.info("上传完成")
        self.logger.info(f"总文件数: {len(files)}")
        self.logger.info(f"成功: {success_count}")
        self.logger.info(f"失败: {failed_count}")
        self.logger.info("=" * 60)
    
    def run(self):
        """运行上传任务"""
        try:
            # 获取配置
            upload_settings = self.config['upload_settings']
            oss_root = Path(upload_settings['oss_root'])
            
            if not oss_root.exists():
                self.logger.error(f"OSS 根目录不存在: {oss_root}")
                return
            
            # 扫描文件
            extensions = upload_settings.get('file_extensions', ['.fits', '.fit', '.png', '.jpg', '.txt'])
            files = self.scan_files(oss_root, extensions)
            
            # 上传文件
            max_workers = upload_settings.get('max_workers', 4)
            self.upload_files(files, oss_root, max_workers)
            
        except Exception as e:
            self.logger.error(f"上传任务失败: {str(e)}", exc_info=True)


def main():
    """主函数"""
    print("=" * 60)
    print("阿里云 OSS 文件上传工具")
    print("=" * 60)
    
    # 创建上传器
    uploader = OSSUploader()
    
    # 运行上传
    uploader.run()
    
    print("\n上传任务完成，详细日志请查看 oss_upload.log")


if __name__ == "__main__":
    main()

