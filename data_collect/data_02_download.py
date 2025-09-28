import argparse
import os
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import threading

# 添加config目录到路径
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config'))
from url_config_manager import url_config_manager

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    # ASTAP处理器现在在gui目录中
    gui_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'gui')
    sys.path.append(gui_path)
    from astap_processor import ASTAPProcessor
except ImportError:
    ASTAPProcessor = None


class FitsDownloader:
    def __init__(self, max_workers=4, retry_times=3, timeout=30, enable_astap=False, astap_config_path=None):
        self.max_workers = max_workers
        self.retry_times = retry_times
        self.timeout = timeout
        self.enable_astap = enable_astap
        self.download_stats = {
            'total': 0,
            'completed': 0,
            'skipped': 0,
            'failed': 0
        }
        self.stats_lock = threading.Lock()

        # 初始化ASTAP处理器
        self.astap_processor = None
        if self.enable_astap and ASTAPProcessor:
            try:
                config_path = astap_config_path or "config/url_config.json"
                self.astap_processor = ASTAPProcessor(config_path)
                print(f"ASTAP处理器已启用，配置文件: {config_path}")
            except Exception as e:
                print(f"初始化ASTAP处理器失败: {str(e)}")
                self.astap_processor = None
    
    def read_url_list(self, url_file_path):
        """读取URL列表文件"""
        if not os.path.exists(url_file_path):
            raise FileNotFoundError(f"URL列表文件不存在: {url_file_path}")
        
        urls = []
        with open(url_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url and url.startswith('http'):
                    urls.append(url)
        
        print(f"从 {url_file_path} 读取到 {len(urls)} 个URL")
        return urls
    
    def get_filename_from_url(self, url):
        """从URL中提取文件名"""
        return os.path.basename(url.split('?')[0])
    
    def download_single_file(self, url, download_dir, progress_callback=None):
        """下载单个文件

        Args:
            url (str): 文件URL
            download_dir (str): 下载目录
            progress_callback (callable): 进度回调函数，接收参数 (downloaded_bytes, total_bytes, filename)
        """
        filename = self.get_filename_from_url(url)
        file_path = os.path.join(download_dir, filename)

        # 检查文件是否已存在
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            if file_size > 0:
                with self.stats_lock:
                    self.download_stats['skipped'] += 1
                return f"跳过已存在文件: {filename}"

        # 尝试下载文件
        for attempt in range(self.retry_times):
            try:
                # 创建请求对象，设置User-Agent
                req = urllib.request.Request(url)
                req.add_header('User-Agent', url_config_manager.get_setting('user_agent'))

                # 创建无代理的opener
                proxy_handler = urllib.request.ProxyHandler({})
                opener = urllib.request.build_opener(proxy_handler)

                # 下载文件
                with opener.open(req, timeout=self.timeout) as response:
                    # 获取文件总大小
                    total_size = response.headers.get('Content-Length')
                    total_size = int(total_size) if total_size else None

                    downloaded_bytes = 0

                    with open(file_path, 'wb') as f:
                        while True:
                            chunk = response.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded_bytes += len(chunk)

                            # 调用进度回调
                            if progress_callback:
                                progress_callback(downloaded_bytes, total_size, filename)

                # 验证下载的文件大小
                if os.path.getsize(file_path) > 0:
                    with self.stats_lock:
                        self.download_stats['completed'] += 1

                    # 如果启用了ASTAP处理，处理下载的FITS文件
                    if self.astap_processor and filename.lower().endswith(('.fits', '.fit', '.fts')):
                        try:
                            print(f"开始ASTAP处理: {filename}")
                            success = self.astap_processor.process_fits_file(file_path)
                            if success:
                                print(f"ASTAP处理成功: {filename}")
                            else:
                                print(f"ASTAP处理失败: {filename}")
                        except Exception as e:
                            print(f"ASTAP处理出错 {filename}: {str(e)}")

                    return f"下载成功: {filename}"
                else:
                    raise Exception("下载的文件大小为0")

            except Exception as e:
                if attempt < self.retry_times - 1:
                    print(f"下载失败，重试 {attempt + 1}/{self.retry_times}: {filename} - {str(e)}")
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    # 删除可能损坏的文件
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    with self.stats_lock:
                        self.download_stats['failed'] += 1
                    return f"下载失败: {filename} - {str(e)}"
    
    def download_files(self, urls, download_dir):
        """批量下载文件"""
        # 确保下载目录存在
        os.makedirs(download_dir, exist_ok=True)
        
        self.download_stats['total'] = len(urls)
        
        print(f"开始下载 {len(urls)} 个文件到目录: {download_dir}")
        print(f"使用 {self.max_workers} 个线程并发下载")
        
        # 使用线程池进行并发下载
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有下载任务
            future_to_url = {
                executor.submit(self.download_single_file, url, download_dir): url 
                for url in urls
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    print(f"[{self.download_stats['completed'] + self.download_stats['skipped'] + self.download_stats['failed']}/{self.download_stats['total']}] {result}")
                except Exception as e:
                    print(f"任务异常: {url} - {str(e)}")
                    with self.stats_lock:
                        self.download_stats['failed'] += 1
        
        # 打印统计信息
        self.print_stats()
    
    def print_stats(self):
        """打印下载统计信息"""
        print("\n" + "="*50)
        print("下载统计:")
        print(f"总计: {self.download_stats['total']}")
        print(f"成功: {self.download_stats['completed']}")
        print(f"跳过: {self.download_stats['skipped']}")
        print(f"失败: {self.download_stats['failed']}")
        print("="*50)


def parse_args():
    parser = argparse.ArgumentParser(description="下载FITS文件")
    parser.add_argument('url_file', help='URL列表文件路径')
    parser.add_argument('--download-dir', help='下载目录（默认为URL文件所在目录）')
    parser.add_argument('--max-workers', type=int, default=4, help='最大并发线程数（默认4）')
    parser.add_argument('--retry-times', type=int, default=3, help='重试次数（默认3）')
    parser.add_argument('--timeout', type=int, default=30, help='下载超时时间（秒，默认30）')
    return parser.parse_args()


def main():
    args = parse_args()
    
    # 检查URL文件是否存在
    if not os.path.exists(args.url_file):
        print(f"错误: URL文件不存在: {args.url_file}")
        sys.exit(1)
    
    # 确定下载目录
    if args.download_dir:
        download_dir = args.download_dir
    else:
        # 默认使用URL文件所在的目录
        download_dir = os.path.dirname(os.path.abspath(args.url_file))
    
    print(f"URL文件: {args.url_file}")
    print(f"下载目录: {download_dir}")
    
    # 创建下载器
    downloader = FitsDownloader(
        max_workers=args.max_workers,
        retry_times=args.retry_times,
        timeout=args.timeout
    )
    
    try:
        # 读取URL列表
        urls = downloader.read_url_list(args.url_file)
        
        if not urls:
            print("警告: URL列表为空")
            return
        
        # 开始下载
        downloader.download_files(urls, download_dir)
        
    except KeyboardInterrupt:
        print("\n用户中断下载")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
