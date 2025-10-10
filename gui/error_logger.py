#!/usr/bin/env python3
"""
错误日志记录模块
用于记录diff操作过程中的错误信息和调试信息
"""

import os
import logging
import traceback
from datetime import datetime
from typing import Optional, Callable


class ErrorLogger:
    """错误日志记录器"""
    
    def __init__(self, log_file_path: Optional[str] = None, gui_callback: Optional[Callable] = None):
        """
        初始化错误日志记录器
        
        Args:
            log_file_path (str): 日志文件路径，如果为None则自动生成
            gui_callback (Callable): GUI回调函数，用于在界面显示错误信息
        """
        self.logger = logging.getLogger(__name__)
        self.gui_callback = gui_callback
        
        # 如果没有指定日志文件路径，自动生成
        if log_file_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file_path = f"diff_error_log_{timestamp}.txt"
        
        self.log_file_path = log_file_path
        self.error_count = 0
        self.warning_count = 0
        
        # 创建日志文件
        self._init_log_file()
    
    def _init_log_file(self):
        """初始化日志文件"""
        try:
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"DIFF操作错误日志\n")
                f.write(f"创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
        except Exception as e:
            self.logger.error(f"无法创建日志文件 {self.log_file_path}: {e}")
    
    def _write_to_file(self, message: str):
        """写入日志文件"""
        try:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(message + "\n")
        except Exception as e:
            self.logger.error(f"写入日志文件失败: {e}")
    
    def _format_timestamp(self) -> str:
        """格式化时间戳"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def log_error(self, message: str, exception: Optional[Exception] = None, 
                  context: Optional[dict] = None):
        """
        记录错误信息
        
        Args:
            message (str): 错误消息
            exception (Exception): 异常对象
            context (dict): 上下文信息（文件路径、命令等）
        """
        self.error_count += 1
        
        # 构建完整的错误信息
        log_entry = f"\n{'=' * 80}\n"
        log_entry += f"[错误 #{self.error_count}] {self._format_timestamp()}\n"
        log_entry += f"{'=' * 80}\n"
        log_entry += f"消息: {message}\n"
        
        # 添加上下文信息
        if context:
            log_entry += "\n上下文信息:\n"
            for key, value in context.items():
                log_entry += f"  {key}: {value}\n"
        
        # 添加异常信息
        if exception:
            log_entry += f"\n异常类型: {type(exception).__name__}\n"
            log_entry += f"异常消息: {str(exception)}\n"
            log_entry += "\n异常堆栈:\n"
            log_entry += traceback.format_exc()
        
        log_entry += "=" * 80 + "\n"
        
        # 写入文件
        self._write_to_file(log_entry)
        
        # 输出到标准日志
        self.logger.error(message)
        if exception:
            self.logger.error(f"异常: {str(exception)}")
        
        # 调用GUI回调（红色显示）
        if self.gui_callback:
            gui_message = f"[错误] {message}"
            if exception:
                gui_message += f" - {str(exception)}"
            self.gui_callback(gui_message, level="ERROR")
    
    def log_warning(self, message: str, context: Optional[dict] = None):
        """
        记录警告信息
        
        Args:
            message (str): 警告消息
            context (dict): 上下文信息
        """
        self.warning_count += 1
        
        log_entry = f"\n[警告 #{self.warning_count}] {self._format_timestamp()}\n"
        log_entry += f"消息: {message}\n"
        
        if context:
            log_entry += "上下文信息:\n"
            for key, value in context.items():
                log_entry += f"  {key}: {value}\n"
        
        # 写入文件
        self._write_to_file(log_entry)
        
        # 输出到标准日志
        self.logger.warning(message)
        
        # 调用GUI回调（橙色显示）
        if self.gui_callback:
            self.gui_callback(f"[警告] {message}", level="WARNING")
    
    def log_info(self, message: str, context: Optional[dict] = None):
        """
        记录信息
        
        Args:
            message (str): 信息消息
            context (dict): 上下文信息
        """
        log_entry = f"[信息] {self._format_timestamp()} - {message}\n"
        
        if context:
            log_entry += "  上下文: " + ", ".join([f"{k}={v}" for k, v in context.items()]) + "\n"
        
        # 写入文件
        self._write_to_file(log_entry)
        
        # 输出到标准日志
        self.logger.info(message)
        
        # 调用GUI回调（普通显示）
        if self.gui_callback:
            self.gui_callback(f"[信息] {message}", level="INFO")
    
    def log_command(self, command: str, cwd: Optional[str] = None):
        """
        记录执行的命令
        
        Args:
            command (str): 执行的命令
            cwd (str): 工作目录
        """
        log_entry = f"\n[命令] {self._format_timestamp()}\n"
        if cwd:
            log_entry += f"工作目录: {cwd}\n"
        log_entry += f"命令: {command}\n"
        
        # 写入文件
        self._write_to_file(log_entry)
        
        # 输出到标准日志
        self.logger.debug(f"执行命令: {command}")
        
        # 调用GUI回调
        if self.gui_callback:
            self.gui_callback(f"[命令] {command}", level="DEBUG")
    
    def log_file_operation(self, operation: str, file_path: str, success: bool = True, 
                          error_msg: Optional[str] = None):
        """
        记录文件操作
        
        Args:
            operation (str): 操作类型（读取、写入、删除等）
            file_path (str): 文件路径
            success (bool): 是否成功
            error_msg (str): 错误消息
        """
        status = "成功" if success else "失败"
        log_entry = f"[文件操作] {self._format_timestamp()} - {operation} {status}\n"
        log_entry += f"  文件: {file_path}\n"
        
        if not success and error_msg:
            log_entry += f"  错误: {error_msg}\n"
            self.error_count += 1
        
        # 写入文件
        self._write_to_file(log_entry)
        
        # 输出到标准日志
        if success:
            self.logger.debug(f"文件操作成功: {operation} - {file_path}")
        else:
            self.logger.error(f"文件操作失败: {operation} - {file_path} - {error_msg}")
        
        # 调用GUI回调
        if self.gui_callback:
            level = "INFO" if success else "ERROR"
            msg = f"[文件] {operation} {status}: {os.path.basename(file_path)}"
            if not success and error_msg:
                msg += f" - {error_msg}"
            self.gui_callback(msg, level=level)
    
    def get_summary(self) -> str:
        """
        获取错误日志摘要
        
        Returns:
            str: 摘要信息
        """
        summary = f"\n{'=' * 80}\n"
        summary += f"错误日志摘要\n"
        summary += f"{'=' * 80}\n"
        summary += f"日志文件: {self.log_file_path}\n"
        summary += f"错误数量: {self.error_count}\n"
        summary += f"警告数量: {self.warning_count}\n"
        summary += f"{'=' * 80}\n"
        
        # 写入文件
        self._write_to_file(summary)
        
        return summary
    
    def close(self):
        """关闭日志记录器"""
        summary = self.get_summary()
        self.logger.info(summary)
        
        if self.gui_callback:
            if self.error_count > 0:
                self.gui_callback(f"[摘要] 处理完成，发现 {self.error_count} 个错误，{self.warning_count} 个警告", level="ERROR")
            elif self.warning_count > 0:
                self.gui_callback(f"[摘要] 处理完成，发现 {self.warning_count} 个警告", level="WARNING")
            else:
                self.gui_callback(f"[摘要] 处理完成，无错误", level="INFO")

