#!/usr/bin/env python3
"""
日历选择器组件
提供日历样式的日期选择功能
"""

import tkinter as tk
from tkinter import ttk
import calendar
from datetime import datetime, timedelta
from typing import Callable, Optional


class CalendarWidget:
    """日历选择器组件"""
    
    def __init__(self, parent, initial_date=None, on_date_select: Optional[Callable] = None):
        self.parent = parent
        self.on_date_select = on_date_select
        
        # 设置初始日期
        if initial_date:
            if isinstance(initial_date, str):
                self.current_date = datetime.strptime(initial_date, '%Y%m%d')
            else:
                self.current_date = initial_date
        else:
            self.current_date = datetime.now()
        
        self.selected_date = self.current_date
        
        # 创建界面
        self._create_widgets()
        self._update_calendar()
    
    def _create_widgets(self):
        """创建日历界面"""
        # 主框架
        self.main_frame = ttk.Frame(self.parent)
        
        # 标题栏（年月导航）
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 上一月按钮
        self.prev_button = ttk.Button(header_frame, text="◀", width=3, command=self._prev_month)
        self.prev_button.pack(side=tk.LEFT)
        
        # 年月显示
        self.month_year_label = ttk.Label(header_frame, font=('Arial', 12, 'bold'))
        self.month_year_label.pack(side=tk.LEFT, expand=True)
        
        # 下一月按钮
        self.next_button = ttk.Button(header_frame, text="▶", width=3, command=self._next_month)
        self.next_button.pack(side=tk.RIGHT)
        
        # 今天按钮
        self.today_button = ttk.Button(header_frame, text="今天", command=self._go_to_today)
        self.today_button.pack(side=tk.RIGHT, padx=(0, 5))
        
        # 星期标题
        weekdays_frame = ttk.Frame(self.main_frame)
        weekdays_frame.pack(fill=tk.X)
        
        weekdays = ['一', '二', '三', '四', '五', '六', '日']
        for day in weekdays:
            label = ttk.Label(weekdays_frame, text=day, width=4, anchor='center', 
                            font=('Arial', 9, 'bold'))
            label.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        # 日期网格
        self.calendar_frame = ttk.Frame(self.main_frame)
        self.calendar_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        
        # 创建6行7列的按钮网格
        self.day_buttons = []
        for week in range(6):
            week_buttons = []
            for day in range(7):
                btn = tk.Button(self.calendar_frame, width=4, height=2,
                              font=('Arial', 9), relief='flat', bd=1,
                              command=lambda w=week, d=day: self._on_day_click(w, d))
                btn.grid(row=week, column=day, padx=1, pady=1, sticky='nsew')
                week_buttons.append(btn)
            self.day_buttons.append(week_buttons)
        
        # 配置网格权重
        for i in range(7):
            self.calendar_frame.columnconfigure(i, weight=1)
        for i in range(6):
            self.calendar_frame.rowconfigure(i, weight=1)
    
    def _update_calendar(self):
        """更新日历显示"""
        # 更新年月标题
        year = self.current_date.year
        month = self.current_date.month
        month_name = calendar.month_name[month]
        self.month_year_label.config(text=f"{year}年 {month}月")
        
        # 获取当月日历
        cal = calendar.monthcalendar(year, month)
        
        # 获取今天的日期
        today = datetime.now()
        
        # 清空所有按钮
        for week_buttons in self.day_buttons:
            for btn in week_buttons:
                btn.config(text='', state='disabled', bg='SystemButtonFace')
        
        # 填充日期
        for week_idx, week in enumerate(cal):
            for day_idx, day in enumerate(week):
                if day == 0:
                    continue
                
                btn = self.day_buttons[week_idx][day_idx]
                btn.config(text=str(day), state='normal')
                
                # 设置按钮样式
                date_obj = datetime(year, month, day)
                
                # 今天的样式
                if (date_obj.year == today.year and 
                    date_obj.month == today.month and 
                    date_obj.day == today.day):
                    btn.config(bg='lightblue', fg='black', font=('Arial', 9, 'bold'))
                
                # 选中日期的样式
                elif (date_obj.year == self.selected_date.year and 
                      date_obj.month == self.selected_date.month and 
                      date_obj.day == self.selected_date.day):
                    btn.config(bg='darkblue', fg='white', font=('Arial', 9, 'bold'))
                
                # 普通日期样式
                else:
                    btn.config(bg='white', fg='black', font=('Arial', 9))
    
    def _prev_month(self):
        """上一月"""
        if self.current_date.month == 1:
            self.current_date = self.current_date.replace(year=self.current_date.year - 1, month=12)
        else:
            self.current_date = self.current_date.replace(month=self.current_date.month - 1)
        self._update_calendar()
    
    def _next_month(self):
        """下一月"""
        if self.current_date.month == 12:
            self.current_date = self.current_date.replace(year=self.current_date.year + 1, month=1)
        else:
            self.current_date = self.current_date.replace(month=self.current_date.month + 1)
        self._update_calendar()
    
    def _go_to_today(self):
        """跳转到今天"""
        today = datetime.now()
        self.current_date = today
        self.selected_date = today
        self._update_calendar()
        
        # 触发选择回调
        if self.on_date_select:
            self.on_date_select(self.selected_date.strftime('%Y%m%d'))
    
    def _on_day_click(self, week, day):
        """日期点击事件"""
        btn = self.day_buttons[week][day]
        day_text = btn.cget('text')
        
        if day_text and btn.cget('state') == 'normal':
            day_num = int(day_text)
            self.selected_date = datetime(self.current_date.year, self.current_date.month, day_num)
            self._update_calendar()
            
            # 触发选择回调
            if self.on_date_select:
                self.on_date_select(self.selected_date.strftime('%Y%m%d'))
    
    def get_selected_date(self) -> str:
        """获取选中的日期"""
        return self.selected_date.strftime('%Y%m%d')
    
    def set_date(self, date_str: str):
        """设置日期"""
        try:
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            self.current_date = date_obj
            self.selected_date = date_obj
            self._update_calendar()
        except ValueError:
            pass
    
    def pack(self, **kwargs):
        """打包显示"""
        self.main_frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        """网格显示"""
        self.main_frame.grid(**kwargs)
    
    def destroy(self):
        """销毁组件"""
        self.main_frame.destroy()


class CalendarDialog:
    """日历选择对话框"""
    
    def __init__(self, parent, title="选择日期", initial_date=None):
        self.parent = parent
        self.result = None
        
        # 创建对话框
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("300x250")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        
        # 创建日历组件
        self.calendar = CalendarWidget(self.dialog, initial_date, self._on_date_select)
        self.calendar.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 存储初始选择的日期
        self.result = self.calendar.get_selected_date()
        
        # 按钮框架
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # 确定和取消按钮
        ttk.Button(button_frame, text="确定", command=self._on_ok).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="取消", command=self._on_cancel).pack(side=tk.RIGHT)
        
        # 居中显示
        self._center_dialog()
        
        # 绑定ESC键
        self.dialog.bind('<Escape>', lambda e: self._on_cancel())
    
    def _center_dialog(self):
        """居中显示对话框"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def _on_date_select(self, date_str):
        """日期选择回调"""
        # 更新结果，这样即使用户不点确定也能获取到选择的日期
        self.result = date_str
    
    def _on_ok(self):
        """确定按钮"""
        self.result = self.calendar.get_selected_date()
        self.dialog.destroy()
    
    def _on_cancel(self):
        """取消按钮"""
        self.result = None
        self.dialog.destroy()
    
    def show(self) -> Optional[str]:
        """显示对话框并返回选择的日期"""
        self.dialog.wait_window()
        return self.result


# 测试代码
if __name__ == "__main__":
    def test_calendar():
        root = tk.Tk()
        root.title("日历测试")
        root.geometry("400x300")
        
        def on_date_change(date_str):
            print(f"选择的日期: {date_str}")
        
        calendar_widget = CalendarWidget(root, on_date_select=on_date_change)
        calendar_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        def show_dialog():
            dialog = CalendarDialog(root, "选择日期", "20250718")
            result = dialog.show()
            if result:
                print(f"对话框选择的日期: {result}")
                calendar_widget.set_date(result)
        
        ttk.Button(root, text="打开日历对话框", command=show_dialog).pack(pady=5)
        
        root.mainloop()
    
    test_calendar()
