#!/usr/bin/env python3
"""
FITS文件网页下载器GUI
用于扫描网页、下载FITS文件并显示图像
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import logging
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_scanner import WebFitsScanner, DirectoryScanner
from fits_viewer import FitsImageViewer
from data_collect.data_02_download import FitsDownloader


class FitsWebDownloaderGUI:
    """FITS文件网页下载器主界面"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("FITS文件网页下载器")
        self.root.geometry("1200x800")
        
        # 设置日志
        self._setup_logging()
        
        # 初始化组件
        self.scanner = WebFitsScanner()
        self.directory_scanner = DirectoryScanner()
        self.downloader = None
        
        # 数据存储
        self.fits_files_list = []  # [(filename, url, size)]
        self.download_directory = ""
        
        # 创建界面
        self._create_widgets()
        
        # 设置默认URL
        self.url_entry.insert(0, "https://download.china-vo.org/psp/KATS/GY5-DATA/20250701/K096/")
        
    def _setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def _create_widgets(self):
        """创建界面组件"""
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建笔记本控件（标签页）
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # 创建扫描和下载标签页
        self.scan_frame = ttk.Frame(notebook)
        notebook.add(self.scan_frame, text="扫描和下载")
        
        # 创建图像查看标签页
        self.viewer_frame = ttk.Frame(notebook)
        notebook.add(self.viewer_frame, text="图像查看")
        
        # 创建日志标签页
        self.log_frame = ttk.Frame(notebook)
        notebook.add(self.log_frame, text="日志")
        
        # 初始化各个标签页
        self._create_scan_widgets()
        self._create_viewer_widgets()
        self._create_log_widgets()
        
    def _create_scan_widgets(self):
        """创建扫描和下载界面"""
        # URL输入区域
        url_frame = ttk.LabelFrame(self.scan_frame, text="网页URL", padding=10)
        url_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(url_frame, text="URL:").pack(side=tk.LEFT)
        self.url_entry = ttk.Entry(url_frame, width=80)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        
        self.scan_button = ttk.Button(url_frame, text="扫描", command=self._start_scan)
        self.scan_button.pack(side=tk.RIGHT)
        
        # 文件列表区域
        list_frame = ttk.LabelFrame(self.scan_frame, text="FITS文件列表", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 创建Treeview显示文件列表
        columns = ("filename", "size", "url")
        self.file_tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", height=15)
        
        # 设置列标题
        self.file_tree.heading("#0", text="选择")
        self.file_tree.heading("filename", text="文件名")
        self.file_tree.heading("size", text="大小")
        self.file_tree.heading("url", text="URL")
        
        # 设置列宽
        self.file_tree.column("#0", width=60)
        self.file_tree.column("filename", width=300)
        self.file_tree.column("size", width=100)
        self.file_tree.column("url", width=400)
        
        # 添加滚动条
        tree_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 绑定点击事件
        self.file_tree.bind('<Button-1>', self._on_tree_click)
        
        # 选择控制按钮
        select_frame = ttk.Frame(list_frame)
        select_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(select_frame, text="全选", command=self._select_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(select_frame, text="全不选", command=self._deselect_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(select_frame, text="反选", command=self._invert_selection).pack(side=tk.LEFT)
        
        # 下载控制区域
        download_frame = ttk.LabelFrame(self.scan_frame, text="下载设置", padding=10)
        download_frame.pack(fill=tk.X)
        
        # 下载目录选择
        dir_frame = ttk.Frame(download_frame)
        dir_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(dir_frame, text="下载目录:").pack(side=tk.LEFT)
        self.download_dir_var = tk.StringVar()
        self.download_dir_entry = ttk.Entry(dir_frame, textvariable=self.download_dir_var, width=60)
        self.download_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        
        ttk.Button(dir_frame, text="浏览", command=self._select_download_dir).pack(side=tk.RIGHT)
        
        # 下载参数
        params_frame = ttk.Frame(download_frame)
        params_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(params_frame, text="并发数:").pack(side=tk.LEFT)
        self.max_workers_var = tk.IntVar(value=4)
        ttk.Spinbox(params_frame, from_=1, to=10, textvariable=self.max_workers_var, width=5).pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(params_frame, text="重试次数:").pack(side=tk.LEFT)
        self.retry_times_var = tk.IntVar(value=3)
        ttk.Spinbox(params_frame, from_=1, to=10, textvariable=self.retry_times_var, width=5).pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(params_frame, text="超时(秒):").pack(side=tk.LEFT)
        self.timeout_var = tk.IntVar(value=30)
        ttk.Spinbox(params_frame, from_=10, to=120, textvariable=self.timeout_var, width=5).pack(side=tk.LEFT, padx=(5, 0))
        
        # 下载按钮和进度条
        control_frame = ttk.Frame(download_frame)
        control_frame.pack(fill=tk.X)
        
        self.download_button = ttk.Button(control_frame, text="开始下载", command=self._start_download)
        self.download_button.pack(side=tk.LEFT)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(control_frame, variable=self.progress_var, length=300)
        self.progress_bar.pack(side=tk.LEFT, padx=(10, 10), fill=tk.X, expand=True)
        
        self.status_label = ttk.Label(control_frame, text="就绪")
        self.status_label.pack(side=tk.RIGHT)
        
    def _create_viewer_widgets(self):
        """创建图像查看界面"""
        # 文件选择区域
        file_frame = ttk.LabelFrame(self.viewer_frame, text="文件选择", padding=10)
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(file_frame, text="选择FITS文件", command=self._select_fits_file).pack(side=tk.LEFT)
        ttk.Button(file_frame, text="从下载目录选择", command=self._select_from_download_dir).pack(side=tk.LEFT, padx=(10, 0))
        
        # 创建FITS查看器
        self.fits_viewer = FitsImageViewer(self.viewer_frame)
        
    def _create_log_widgets(self):
        """创建日志界面"""
        # 日志显示区域
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=30, width=100)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 日志控制按钮
        log_control_frame = ttk.Frame(self.log_frame)
        log_control_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Button(log_control_frame, text="清除日志", command=self._clear_log).pack(side=tk.LEFT)
        ttk.Button(log_control_frame, text="保存日志", command=self._save_log).pack(side=tk.LEFT, padx=(10, 0))
        
    def _start_scan(self):
        """开始扫描"""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("警告", "请输入要扫描的URL")
            return
        
        # 禁用扫描按钮
        self.scan_button.config(state="disabled")
        self.status_label.config(text="正在扫描...")
        
        # 清空文件列表
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        # 在新线程中执行扫描
        thread = threading.Thread(target=self._scan_thread, args=(url,))
        thread.daemon = True
        thread.start()
        
    def _scan_thread(self, url):
        """扫描线程"""
        try:
            self._log(f"开始扫描URL: {url}")
            
            # 尝试目录扫描器
            try:
                fits_files = self.directory_scanner.scan_directory_listing(url)
            except Exception as e:
                self._log(f"目录扫描失败，尝试通用扫描器: {str(e)}")
                fits_files = self.scanner.scan_fits_files(url)
            
            self.fits_files_list = fits_files
            
            # 更新界面
            self.root.after(0, self._update_file_list)
            self._log(f"扫描完成，找到 {len(fits_files)} 个FITS文件")
            
        except Exception as e:
            error_msg = f"扫描失败: {str(e)}"
            self._log(error_msg)
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        finally:
            # 重新启用扫描按钮
            self.root.after(0, lambda: self.scan_button.config(state="normal"))
            self.root.after(0, lambda: self.status_label.config(text="就绪"))
            
    def _update_file_list(self):
        """更新文件列表显示"""
        for filename, url, size in self.fits_files_list:
            size_str = self.scanner.format_file_size(size)
            item = self.file_tree.insert("", "end", text="☐", values=(filename, size_str, url))

    def _on_tree_click(self, event):
        """处理树形控件点击事件"""
        region = self.file_tree.identify_region(event.x, event.y)
        if region == "tree":
            item = self.file_tree.identify_row(event.y)
            if item:
                # 切换选择状态
                current_text = self.file_tree.item(item, "text")
                new_text = "☑" if current_text == "☐" else "☐"
                self.file_tree.item(item, text=new_text)
            
    def _select_all(self):
        """全选"""
        for item in self.file_tree.get_children():
            self.file_tree.item(item, text="☑")
            
    def _deselect_all(self):
        """全不选"""
        for item in self.file_tree.get_children():
            self.file_tree.item(item, text="☐")
            
    def _invert_selection(self):
        """反选"""
        for item in self.file_tree.get_children():
            current_text = self.file_tree.item(item, "text")
            new_text = "☑" if current_text == "☐" else "☐"
            self.file_tree.item(item, text=new_text)
            
    def _select_download_dir(self):
        """选择下载目录"""
        directory = filedialog.askdirectory(title="选择下载目录")
        if directory:
            self.download_dir_var.set(directory)
            
    def _get_selected_files(self):
        """获取选中的文件"""
        selected_files = []
        for item in self.file_tree.get_children():
            if self.file_tree.item(item, "text") == "☑":
                values = self.file_tree.item(item, "values")
                filename, size_str, url = values
                selected_files.append((filename, url))
        return selected_files

    def _start_download(self):
        """开始下载"""
        selected_files = self._get_selected_files()
        if not selected_files:
            messagebox.showwarning("警告", "请选择要下载的文件")
            return

        download_dir = self.download_dir_var.get().strip()
        if not download_dir:
            messagebox.showwarning("警告", "请选择下载目录")
            return

        # 创建下载目录
        os.makedirs(download_dir, exist_ok=True)

        # 禁用下载按钮
        self.download_button.config(state="disabled")
        self.status_label.config(text="正在下载...")

        # 重置进度条
        self.progress_var.set(0)
        self.progress_bar.config(maximum=len(selected_files))

        # 在新线程中执行下载
        thread = threading.Thread(target=self._download_thread, args=(selected_files, download_dir))
        thread.daemon = True
        thread.start()

    def _download_thread(self, selected_files, download_dir):
        """下载线程"""
        try:
            # 创建下载器
            self.downloader = FitsDownloader(
                max_workers=self.max_workers_var.get(),
                retry_times=self.retry_times_var.get(),
                timeout=self.timeout_var.get()
            )

            # 准备URL列表
            urls = [url for filename, url in selected_files]

            self._log(f"开始下载 {len(urls)} 个文件到目录: {download_dir}")

            # 执行下载（这里需要修改原始下载器以支持进度回调）
            self._download_with_progress(urls, download_dir)

            self._log("下载完成！")
            self.root.after(0, lambda: messagebox.showinfo("成功", "文件下载完成！"))

        except Exception as e:
            error_msg = f"下载失败: {str(e)}"
            self._log(error_msg)
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        finally:
            # 重新启用下载按钮
            self.root.after(0, lambda: self.download_button.config(state="normal"))
            self.root.after(0, lambda: self.status_label.config(text="就绪"))

    def _download_with_progress(self, urls, download_dir):
        """带进度显示的下载"""
        completed = 0

        for i, url in enumerate(urls):
            try:
                result = self.downloader.download_single_file(url, download_dir)
                completed += 1

                # 更新进度条
                progress = (i + 1) / len(urls) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
                self.root.after(0, lambda c=completed, t=len(urls):
                               self.status_label.config(text=f"已完成: {c}/{t}"))

                self._log(f"[{i+1}/{len(urls)}] {result}")

            except Exception as e:
                self._log(f"下载失败 {url}: {str(e)}")

    def _select_fits_file(self):
        """选择FITS文件进行查看"""
        file_path = filedialog.askopenfilename(
            title="选择FITS文件",
            filetypes=[
                ("FITS files", "*.fits *.fit *.fts"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            self.fits_viewer.load_fits_file(file_path)

    def _select_from_download_dir(self):
        """从下载目录选择FITS文件"""
        download_dir = self.download_dir_var.get().strip()
        if not download_dir or not os.path.exists(download_dir):
            messagebox.showwarning("警告", "请先设置有效的下载目录")
            return

        # 查找FITS文件
        fits_files = []
        for ext in ['*.fits', '*.fit', '*.fts']:
            fits_files.extend(Path(download_dir).glob(ext))

        if not fits_files:
            messagebox.showinfo("信息", "下载目录中没有找到FITS文件")
            return

        # 创建文件选择对话框
        file_names = [f.name for f in fits_files]
        selected = self._show_file_selection_dialog(file_names)

        if selected:
            selected_path = os.path.join(download_dir, selected)
            self.fits_viewer.load_fits_file(selected_path)

    def _show_file_selection_dialog(self, file_names):
        """显示文件选择对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("选择FITS文件")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        # 文件列表
        listbox = tk.Listbox(dialog)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for name in file_names:
            listbox.insert(tk.END, name)

        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        selected_file = [None]

        def on_ok():
            selection = listbox.curselection()
            if selection:
                selected_file[0] = file_names[selection[0]]
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        ttk.Button(button_frame, text="确定", command=on_ok).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="取消", command=on_cancel).pack(side=tk.RIGHT)

        # 双击选择
        listbox.bind('<Double-Button-1>', lambda e: on_ok())

        dialog.wait_window()
        return selected_file[0]

    def _log(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        # 在主线程中更新日志显示
        self.root.after(0, lambda: self._append_log(log_message))

        # 同时输出到控制台
        print(log_message.strip())

    def _append_log(self, message):
        """在日志文本框中添加消息"""
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)

    def _clear_log(self):
        """清除日志"""
        self.log_text.delete(1.0, tk.END)

    def _save_log(self):
        """保存日志"""
        file_path = filedialog.asksaveasfilename(
            title="保存日志",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get(1.0, tk.END))
                messagebox.showinfo("成功", f"日志已保存到:\n{file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"保存日志失败:\n{str(e)}")

    def run(self):
        """运行GUI应用程序"""
        self.root.mainloop()


def main():
    """主函数"""
    app = FitsWebDownloaderGUI()
    app.run()


if __name__ == "__main__":
    main()
