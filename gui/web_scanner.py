#!/usr/bin/env python3
"""
网页FITS文件扫描器
扫描指定URL获取可下载的FITS文件列表
"""

import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging
from typing import List, Tuple


class WebFitsScanner:
    """网页FITS文件扫描器"""
    
    def __init__(self, timeout=30, user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'):
        self.timeout = timeout
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})

        # 禁用代理
        self.session.proxies = {
            'http': None,
            'https': None
        }

        # 禁用SSL验证以避免证书问题
        self.session.verify = False

        # 禁用SSL警告
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # 设置更宽松的SSL适配器
        from requests.adapters import HTTPAdapter
        import ssl

        # 创建自定义的HTTPAdapter
        class SSLAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                kwargs['ssl_context'] = context
                return super().init_poolmanager(*args, **kwargs)

        # 挂载适配器
        self.session.mount('https://', SSLAdapter())
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        
    def scan_fits_files(self, base_url: str) -> List[Tuple[str, str, int]]:
        """
        扫描指定URL获取FITS文件列表
        
        Args:
            base_url (str): 要扫描的基础URL
            
        Returns:
            List[Tuple[str, str, int]]: [(文件名, 完整URL, 文件大小)]
        """
        try:
            self.logger.info(f"开始扫描URL: {base_url}")

            # 尝试使用requests，如果失败则使用urllib
            try:
                response = self.session.get(base_url, timeout=self.timeout)
                response.raise_for_status()
                content = response.text
            except Exception as e:
                self.logger.warning(f"requests失败，尝试urllib: {str(e)}")
                content = self._get_content_with_urllib(base_url)

            # 解析HTML内容
            soup = BeautifulSoup(content, 'html.parser')
            
            fits_files = []
            
            # 查找所有链接
            for link in soup.find_all('a', href=True):
                href = link['href']
                
                # 检查是否是FITS文件
                if self._is_fits_file(href):
                    # 构建完整URL
                    full_url = urljoin(base_url, href)
                    filename = self._extract_filename(href)
                    
                    # 尝试获取文件大小
                    file_size = self._get_file_size(full_url)
                    
                    fits_files.append((filename, full_url, file_size))
                    self.logger.debug(f"找到FITS文件: {filename}")
            
            self.logger.info(f"扫描完成，找到 {len(fits_files)} 个FITS文件")
            return fits_files
            
        except requests.RequestException as e:
            self.logger.error(f"网络请求失败: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"扫描过程出错: {str(e)}")
            raise
    
    def _is_fits_file(self, filename: str) -> bool:
        """检查文件是否是FITS文件"""
        filename_lower = filename.lower()
        fits_extensions = ['.fits', '.fit', '.fts']
        
        # 检查文件扩展名
        for ext in fits_extensions:
            if filename_lower.endswith(ext):
                # 排除一些不需要的文件类型
                exclude_patterns = ['calibration', '_fz', 'flat', 'fiel']
                for pattern in exclude_patterns:
                    if pattern in filename_lower:
                        return False
                return True
        return False
    
    def _extract_filename(self, href: str) -> str:
        """从href中提取文件名"""
        # 移除查询参数
        filename = href.split('?')[0]
        # 获取最后一部分作为文件名
        return filename.split('/')[-1]
    
    def _get_file_size(self, url: str) -> int:
        """获取文件大小（字节）"""
        try:
            # 发送HEAD请求获取文件信息
            response = self.session.head(url, timeout=10)
            if response.status_code == 200:
                content_length = response.headers.get('content-length')
                if content_length:
                    return int(content_length)
        except Exception as e:
            self.logger.debug(f"无法获取文件大小 {url}: {str(e)}")
        
        return 0  # 未知大小
    
    def format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小显示"""
        if size_bytes == 0:
            return "未知"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _get_content_with_urllib(self, url: str) -> str:
        """使用urllib获取网页内容（作为requests的备用方案）"""
        import urllib.request
        import urllib.error
        import ssl

        # 创建SSL上下文
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # 创建无代理的opener
        proxy_handler = urllib.request.ProxyHandler({})
        https_handler = urllib.request.HTTPSHandler(context=context)
        opener = urllib.request.build_opener(proxy_handler, https_handler)

        # 设置请求头
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive'
        }

        req = urllib.request.Request(url, headers=headers)

        with opener.open(req, timeout=self.timeout) as response:
            return response.read().decode('utf-8', errors='ignore')


class DirectoryScanner:
    """目录式网页扫描器（类似Apache目录列表）"""
    
    def __init__(self, timeout=30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # 禁用代理
        self.session.proxies = {
            'http': None,
            'https': None
        }

        # 禁用SSL验证以避免证书问题
        self.session.verify = False

        # 禁用SSL警告
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # 设置更宽松的SSL适配器
        from requests.adapters import HTTPAdapter
        import ssl

        # 创建自定义的HTTPAdapter
        class SSLAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                kwargs['ssl_context'] = context
                return super().init_poolmanager(*args, **kwargs)

        # 挂载适配器
        self.session.mount('https://', SSLAdapter())

        self.logger = logging.getLogger(__name__)
    
    def scan_directory_listing(self, url: str) -> List[Tuple[str, str, int]]:
        """
        扫描目录列表页面获取FITS文件
        
        Args:
            url (str): 目录列表URL
            
        Returns:
            List[Tuple[str, str, int]]: [(文件名, 完整URL, 文件大小)]
        """
        try:
            # 尝试使用requests，如果失败则使用urllib
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                content = response.text
            except Exception as e:
                self.logger.warning(f"requests失败，尝试urllib: {str(e)}")
                content = self._get_content_with_urllib(url)

            # 尝试解析Apache风格的目录列表
            fits_files = []

            # 使用正则表达式匹配文件链接
            # 匹配类似 <a href="filename.fits">filename.fits</a> 的模式
            pattern = r'<a\s+href="([^"]*\.fits?)"[^>]*>([^<]*)</a>'
            matches = re.findall(pattern, content, re.IGNORECASE)
            
            for href, display_name in matches:
                if self._should_include_file(href):
                    full_url = urljoin(url, href)
                    filename = self._extract_filename(href)
                    file_size = self._extract_size_from_listing(content, href)

                    fits_files.append((filename, full_url, file_size))

            # 如果正则表达式没有找到，尝试BeautifulSoup
            if not fits_files:
                fits_files = self._parse_with_beautifulsoup(url, content)
            
            self.logger.info(f"目录扫描完成，找到 {len(fits_files)} 个FITS文件")
            return fits_files
            
        except Exception as e:
            self.logger.error(f"目录扫描失败: {str(e)}")
            raise
    
    def _should_include_file(self, filename: str) -> bool:
        """判断是否应该包含该文件"""
        filename_lower = filename.lower()
        
        # 检查扩展名
        if not any(filename_lower.endswith(ext) for ext in ['.fits', '.fit', '.fts']):
            return False
        
        # 排除不需要的文件
        exclude_patterns = ['calibration', '_fz', 'flat', 'fiel']
        return not any(pattern in filename_lower for pattern in exclude_patterns)
    
    def _extract_filename(self, href: str) -> str:
        """提取文件名"""
        return href.split('/')[-1].split('?')[0]
    
    def _extract_size_from_listing(self, html_content: str, filename: str) -> int:
        """从目录列表HTML中提取文件大小"""
        try:
            # 查找包含文件名的行
            lines = html_content.split('\n')
            for line in lines:
                if filename in line:
                    # 尝试提取大小信息（通常在文件名后面）
                    size_match = re.search(r'(\d+(?:\.\d+)?)\s*([KMGT]?B)', line, re.IGNORECASE)
                    if size_match:
                        size_str, unit = size_match.groups()
                        size = float(size_str)
                        
                        # 转换为字节
                        multipliers = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
                        return int(size * multipliers.get(unit.upper(), 1))
        except Exception:
            pass
        
        return 0
    
    def _parse_with_beautifulsoup(self, base_url: str, html_content: str) -> List[Tuple[str, str, int]]:
        """使用BeautifulSoup解析目录列表"""
        soup = BeautifulSoup(html_content, 'html.parser')
        fits_files = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            if self._should_include_file(href):
                full_url = urljoin(base_url, href)
                filename = self._extract_filename(href)
                file_size = 0  # BeautifulSoup方式暂时不提取大小
                
                fits_files.append((filename, full_url, file_size))
        
        return fits_files

    def _get_content_with_urllib(self, url: str) -> str:
        """使用urllib获取网页内容（作为requests的备用方案）"""
        import urllib.request
        import urllib.error
        import ssl

        # 创建SSL上下文
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # 创建无代理的opener
        proxy_handler = urllib.request.ProxyHandler({})
        https_handler = urllib.request.HTTPSHandler(context=context)
        opener = urllib.request.build_opener(proxy_handler, https_handler)

        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive'
        }

        req = urllib.request.Request(url, headers=headers)

        with opener.open(req, timeout=self.timeout) as response:
            return response.read().decode('utf-8', errors='ignore')
