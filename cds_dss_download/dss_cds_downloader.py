import requests
import shutil
import urllib3
import certifi
import os
import ssl
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 设置SSL证书环境变量
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# 创建自定义SSL适配器，支持更多SSL版本
class SSLAdapter(HTTPAdapter):
    def __init__(self, verify_ssl=True, *args, **kwargs):
        self.verify_ssl = verify_ssl
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        if self.verify_ssl:
            context.load_default_certs()
        else:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        context = create_urllib3_context()
        if self.verify_ssl:
            context.load_default_certs()
        else:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        proxy_kwargs['ssl_context'] = context
        return super().proxy_manager_for(proxy, **proxy_kwargs)

def download_dss_rot(ra: float, dec: float, rotation: float, out_file: str = "dss_rot.jpg",
                     use_proxy: bool = False, proxy_host: str = "127.0.0.1",
                     proxy_port: int = 10550, proxy_type: str = "socks5h",
                     verify_ssl: bool = False):
    """
    ra, dec     : 天区中心（度）
    rotation    : 旋转角（度，逆时针为正）
    out_file    : 保存文件名
    use_proxy   : 是否使用代理
    proxy_host  : 代理主机地址
    proxy_port  : 代理端口
    proxy_type  : 代理类型 (http, socks5, socks5h) - socks5h会通过代理进行DNS解析
    verify_ssl  : 是否验证SSL证书
    """
    url = "https://alasky.cds.unistra.fr/hips-image-services/hips2fits"
    params = {
        "hips": "CDS/P/DSS2/color",   # 也可换成 CDS/P/2MASS/color 等
        "width": 100,
        "height": 100,
        "ra": ra,
        "dec": dec,
        "fov": 0.1,             # 0.1° 视场，100 px 时 ~3.6″/px
        "projection": "TAN",
        "coordsys": "icrs",     # 必须小写
        "rotation_angle": rotation,
        "format": "jpg"
    }

    # 创建Session对象
    session = requests.Session()
    session.trust_env = False  # 不使用系统环境变量中的代理设置

    # 使用自定义SSL适配器，使用代理时禁用SSL验证
    ssl_verify = verify_ssl and not use_proxy
    session.mount('https://', SSLAdapter(verify_ssl=ssl_verify))
    session.mount('http://', SSLAdapter(verify_ssl=ssl_verify))

    if use_proxy:
        # 根据代理类型构建代理URL
        if proxy_type.lower().startswith("socks"):
            proxy_url = f"{proxy_type}://{proxy_host}:{proxy_port}"
        else:
            proxy_url = f"http://{proxy_host}:{proxy_port}"

        session.proxies = {
            "http": proxy_url,
            "https": proxy_url
        }
        print(f"Using {proxy_type} proxy: {proxy_url}")
    else:
        # 明确设置为空，避免使用系统代理
        session.proxies = {}

    try:
        print(f"Downloading from: {url}")
        # 使用代理时通常需要禁用SSL验证，否则使用certifi证书
        if use_proxy:
            verify_param = False
        else:
            verify_param = certifi.where() if verify_ssl else False
        r = session.get(url, params=params, stream=True, verify=verify_param, timeout=30)
        r.raise_for_status()

        # 确保目录存在
        import os
        out_dir = os.path.dirname(out_file)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir)

        with open(out_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"Saved: {out_file}")
        return True
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        return False

# === 调用示例 ===
if __name__ == "__main__":
    # 示例：下载猎户座大星云 (M42) 区域的DSS2彩色图像
    # RA=83.8221度, Dec=-5.3911度, 旋转30度
    success = download_dss_rot(
        ra=83.8221,
        dec=-5.3911,
        rotation=30,
        out_file="dss_rot.jpg",
        use_proxy=False  # 如果需要代理，设置为True
    )

    if success:
        print("下载成功！")
    else:
        print("下载失败，请检查网络连接或尝试使用代理")