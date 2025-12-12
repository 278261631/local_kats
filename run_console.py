#!/usr/bin/env python3
"""
无GUI版本的FITS网页下载 + ASTAP + diff 批处理脚本

目标：在无图形界面环境下，实现与 gui/run_gui.py 中 --date/--telescope/--region
自动模式等价的核心功能（全天 / 全天单系统 / 单天区），但不依赖 Tkinter。

	当前版本实现内容：
	- 基于 ConfigManager 与 url_config_manager 构建 URL
	- 使用自带的网页解析逻辑 + DirectoryScanner/WebFitsScanner 扫描可用天区和 FITS 列表（不依赖 Tk）
	- 使用 FitsDownloader 下载 FITS 文件，并按 GUI 中的目录结构组织
	- 使用 DiffOrbIntegration 直接调用 diff_orb 核心算法执行对齐 + diff

注意：
- 本脚本不导入任何 Tk / GUI 组件，可在无 DISPLAY 的服务器上运行。
- 依赖项目已有的 diff_orb、simple_noise、astap_processor 等模块。
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from typing import List, Tuple

# 保证可以像 GUI 一样导入相关模块
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
GUI_DIR = os.path.join(PROJECT_ROOT, "gui")
DIFF_ORB_DIR = os.path.join(PROJECT_ROOT, "diff_orb")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")

if GUI_DIR not in sys.path:
    sys.path.insert(0, GUI_DIR)
if DIFF_ORB_DIR not in sys.path:
    sys.path.insert(0, DIFF_ORB_DIR)
if CONFIG_DIR not in sys.path:
    sys.path.insert(0, CONFIG_DIR)

from gui.config_manager import ConfigManager  # type: ignore
from gui.web_scanner import WebFitsScanner, DirectoryScanner  # type: ignore
from gui.diff_orb_integration import DiffOrbIntegration  # type: ignore
from data_collect.data_02_download import FitsDownloader  # type: ignore


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FITS网页下载器控制台版（无GUI）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "\n示例:\n"
            "  # 全天全系统 diff\n"
            "  python run_console.py --date 20241031\\n\n"
            "  # 单系统全天 diff\n"
            "  python run_console.py --date 20241031 --telescope GY1\\n\n"
            "  # 单天区扫描 + 下载 + diff\n"
            "  python run_console.py --date 20241031 --telescope GY1 --region K019\n"
        ),
    )

    parser.add_argument("--date", type=str, required=True, help="日期，格式为YYYYMMDD")
    parser.add_argument("--telescope", type=str, help="望远镜系统名，例如 GY1")
    parser.add_argument("--region", type=str, help="天区名，例如 K019")

    parser.add_argument("--download-dir", type=str, help="下载根目录（默认使用 GUI 配置）")
    parser.add_argument("--template-dir", type=str, help="模板目录（默认使用 GUI 配置）")
    parser.add_argument("--diff-output-dir", type=str, help="diff 输出根目录（默认使用 GUI 配置）")

    parser.add_argument("--thread-count", type=int, help="流水线线程数（默认使用 GUI 配置的 thread_count）")
    parser.add_argument("--max-workers", type=int, default=4, help="下载线程数（传给 FitsDownloader，默认4)")
    parser.add_argument("--retry-times", type=int, default=3, help="下载重试次数（默认3）")
    parser.add_argument("--timeout", type=int, default=30, help="单文件下载超时时间（秒，默认30）")

    parser.add_argument("--no-astap", action="store_true", help="跳过 ASTAP 处理，仅下载 + diff")

    return parser.parse_args()


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def ensure_directory(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def build_base_paths(cfg: ConfigManager, args: argparse.Namespace) -> Tuple[str, str, str]:
    last = cfg.get_last_selected()

    download_root = args.download_dir or last.get("download_directory") or os.path.join(PROJECT_ROOT, "downloads")
    template_dir = args.template_dir or last.get("template_directory") or os.path.join(PROJECT_ROOT, "templates")
    diff_root = args.diff_output_dir or last.get("diff_output_directory") or os.path.join(PROJECT_ROOT, "diff_output")

    download_root = ensure_directory(download_root)
    diff_root = ensure_directory(diff_root)

    return download_root, template_dir, diff_root


def validate_args(cfg: ConfigManager, args: argparse.Namespace) -> None:
    if not cfg.validate_date(args.date):
        raise SystemExit(f"无效日期格式: {args.date}，期望 YYYYMMDD")

    if args.telescope and not cfg.validate_telescope_name(args.telescope):
        raise SystemExit(f"未知的望远镜系统: {args.telescope}")

    if args.region and not cfg.validate_k_number(args.region.upper()):
        raise SystemExit(f"未知的天区名称: {args.region}")


def build_region_url(cfg: ConfigManager, tel_name: str, date: str, k_number: str) -> str:
    """使用 ConfigManager/url_config_manager 与 GUI 一致的 URL 模板构建天区 URL。"""
    url_template = cfg.get_url_template()

    params = {"tel_name": tel_name, "date": date, "k_number": k_number}
    if "{year_of_date}" in url_template:
        params["year_of_date"] = date[:4]

    return url_template.format(**params).rstrip("/")


def scan_regions_for_telescope(cfg: ConfigManager, tel_name: str, date: str) -> List[str]:
    """在不依赖Tk的前提下，直接从网页扫描该系统在某日的所有天区列表。"""
    import requests
    import re
    from bs4 import BeautifulSoup
    import urllib3

    url_template = cfg.get_url_template()
    params = {"tel_name": tel_name, "date": date, "k_number": ""}
    if "{year_of_date}" in url_template:
        params["year_of_date"] = date[:4]
    base_url = url_template.format(**params).rstrip("/")

    logging.info("扫描天区列表: %s", base_url)

    # 参照 RegionScanner 的实现，禁用证书校验和代理
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })
    session.proxies = {"http": None, "https": None}
    session.verify = False
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        resp = session.get(base_url, timeout=10)
        resp.raise_for_status()
        content = resp.text
    except Exception as e:
        logging.error("扫描天区时网络请求失败: %s", e)
        return []

    soup = BeautifulSoup(content, "html.parser")
    regions: List[str] = []

    for link in soup.find_all("a", href=True):
        href = link["href"].split("?")[0].split("#")[0]
        dir_name = href.strip("/").split("/")[-1]
        if re.match(r"^K\d{3}$", dir_name, re.IGNORECASE):
            region = dir_name.upper()
            if region not in regions:
                regions.append(region)

    regions.sort()
    logging.info("系统 %s 在 %s 共找到 %d 个天区", tel_name, date, len(regions))
    return regions


def scan_files_for_region(region_url: str) -> List[Tuple[str, str]]:
    """返回 [(filename, url)] 列表。"""
    dir_scanner = DirectoryScanner()
    web_scanner = WebFitsScanner()

    files: List[Tuple[str, str]] = []

    # 先尝试目录列表
    try:
        listing = dir_scanner.scan_directory_listing(region_url)
        if listing:
            for name, url, _size in listing:
                files.append((name, url))
            return files
    except Exception as e:
        logging.warning("DirectoryScanner 失败，将尝试 WebFitsScanner: %s", e)

    # 回退到通用网页扫描
    try:
        results = web_scanner.scan_fits_files(region_url)
        for name, url, _size in results:
            files.append((name, url))
    except Exception as e:
        logging.error("WebFitsScanner 扫描失败: %s", e)

    return files


def run_pipeline_for_files(
    tel_name: str,
    date: str,
    region: str,
    files: List[Tuple[str, str]],
    download_root: str,
    template_dir: str,
    diff_root: str,
    args: argparse.Namespace,
    diff_integration: DiffOrbIntegration,
    cfg: ConfigManager,
) -> None:
    if not files:
        logging.info("[{} {} {}] 无可处理文件，跳过", tel_name, date, region)
        return

    # 下载目录：与 GUI 一致：download_root/tel_name/date/region
    download_dir = ensure_directory(os.path.join(download_root, tel_name, date, region))
    diff_output_root = ensure_directory(os.path.join(diff_root, tel_name, date))

    downloader = FitsDownloader(
        max_workers=args.max_workers,
        retry_times=args.retry_times,
        timeout=args.timeout,
        enable_astap=not args.no_astap,
    )

    urls = [url for _name, url in files]
    logging.info("[{} {} {}] 开始下载 {} 个文件到 {}", tel_name, date, region, len(urls), download_dir)
    downloader.download_files(urls, download_dir)

    # 下载完成后，对下载目录中的所有 FITS 做 diff
    for entry in os.scandir(download_dir):
        if not entry.is_file():
            continue
        if not entry.name.lower().endswith((".fits", ".fit", ".fts")):
            continue

        download_file = entry.path
        filename = entry.name
        logging.info("[Diff] 开始处理: %s", filename)

        template_file = diff_integration.find_template_file(download_file, template_dir)
        if not template_file:
            logging.info("[Diff] 未找到模板，跳过: %s", filename)
            continue

        # 输出目录结构与 GUI 中 _get_thread_safe_diff_output_directory 一致：
        # diff_root/tel_name/date/region/文件名无扩展
        name_wo_ext = os.path.splitext(filename)[0]
        output_dir = ensure_directory(os.path.join(diff_output_root, region, name_wo_ext))

        # 如果已有 detection_ 目录，认为处理完成，跳过
        existed = False
        for d in os.listdir(output_dir):
            full = os.path.join(output_dir, d)
            if d.startswith("detection_") and os.path.isdir(full):
                existed = True
                break
        if existed:
            logging.info("[Diff] 结果已存在，跳过: %s", filename)
            continue

        # 这里直接使用 ConfigManager 中 batch_process_settings 的默认参数
        batch_cfg = cfg.get_batch_process_settings()
        noise_methods = []
        if batch_cfg.get("noise_method") == "median":
            noise_methods.append("adaptive_median")
        elif batch_cfg.get("noise_method") in ("gaussian", "gaussian_hot_cold"):
            noise_methods.append("outlier")

        alignment_method = {
            "orb": "rigid",
            "ecc": "wcs",
            "astropy_reproject": "astropy_reproject",
            "swarp": "swarp",
        }.get(batch_cfg.get("alignment_method", "ecc"), "wcs")

        remove_bright_lines = bool(batch_cfg.get("remove_bright_lines", True))
        stretch_method = "percentile" if batch_cfg.get("stretch_method", "percentile") == "percentile" else "peak"
        percentile_low = float(batch_cfg.get("percentile_low", 99.95))
        fast_mode = bool(batch_cfg.get("fast_mode", True))
        sort_by = batch_cfg.get("sort_by", "aligned_snr")
        wcs_use_sparse = bool(batch_cfg.get("wcs_use_sparse", False))
        generate_gif = bool(batch_cfg.get("generate_gif", False))

        result = diff_integration.process_diff(
            download_file,
            template_file,
            output_dir=output_dir,
            noise_methods=noise_methods,
            alignment_method=alignment_method,
            remove_bright_lines=remove_bright_lines,
            stretch_method=stretch_method,
            percentile_low=percentile_low,
            fast_mode=fast_mode,
            max_jaggedness_ratio=float(batch_cfg.get("max_jaggedness_ratio", 2.0)),
            detection_method=batch_cfg.get("detection_method", "contour"),
            sort_by=sort_by,
            wcs_use_sparse=wcs_use_sparse,
            generate_gif=generate_gif,
        )

        if result and result.get("success"):
            logging.info("[Diff] 成功: %s - 新亮点 %s 个", filename, result.get("new_bright_spots", 0))
        else:
            logging.warning("[Diff] 失败: %s", filename)


def main():
    setup_logging()
    args = parse_arguments()

    cfg = ConfigManager()
    validate_args(cfg, args)

    download_root, template_dir, diff_root = build_base_paths(cfg, args)
    logging.info("下载根目录: %s", download_root)
    logging.info("模板目录: %s", template_dir)
    logging.info("diff 输出根目录: %s", diff_root)

    # 保存当前选择到 GUI 配置，便于 GUI 和 CLI 共用
    cfg.update_last_selected(
        telescope_name=args.telescope or cfg.get_last_selected().get("telescope_name"),
        date=args.date,
        k_number=args.region or cfg.get_last_selected().get("k_number"),
        download_directory=download_root,
        template_directory=template_dir,
        diff_output_directory=diff_root,
    )

    diff_integration = DiffOrbIntegration(gui_callback=None)
    if not diff_integration.is_available():
        logging.error("diff_orb 模块不可用，请检查 diff_orb 依赖是否安装正确")
        raise SystemExit(1)

    # 决定处理模式
    if args.region and args.telescope:
        # 单天区
        regions = [args.region.upper()]
        telescopes = [args.telescope]
    elif args.telescope:
        # 单系统全天
        telescopes = [args.telescope]
        regions = None  # 稍后针对每个系统扫描
    else:
        # 全天全系统
        telescopes = cfg.get_telescope_names()
        regions = None

    date = args.date

    total_regions = 0
    for tel in telescopes:
        if regions is None:
            # 为该系统扫描所有天区
            region_list = scan_regions_for_telescope(cfg, tel, date)
        else:
            region_list = regions

        logging.info("系统 %s 在 %s 的天区数: %d", tel, date, len(region_list))
        for region in region_list:
            total_regions += 1
            region_url = build_region_url(cfg, tel, date, region)
            logging.info("[%s/%s/%s] 扫描 URL: %s", tel, date, region, region_url)
            files = scan_files_for_region(region_url)
            logging.info("[%s/%s/%s] 找到 %d 个 FITS", tel, date, region, len(files))
            run_pipeline_for_files(
                tel_name=tel,
                date=date,
                region=region,
                files=files,
                download_root=download_root,
                template_dir=template_dir,
                diff_root=diff_root,
                args=args,
                diff_integration=diff_integration,
                cfg=cfg,
            )

    logging.info("处理完成。共处理天区数: %d", total_regions)


if __name__ == "__main__":
    main()

