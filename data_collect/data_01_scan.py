import argparse
import datetime
import os
import re
from scan_by_days import scan_by_day_path

recent_data = True
day_count = 1

def save_fits_list(fits_url_list, date_ymd, base_data_path):
    temp_download_path = f'{base_data_path}/{date_ymd}/'
    file_name_txt_ok = "{}_urls.txt".format(date_ymd)
    save_file_path_ok = os.path.join(temp_download_path, file_name_txt_ok)

    save_file_dir = temp_download_path
    if not os.path.exists(save_file_path_ok):
        print(f'+{save_file_path_ok}')
        os.makedirs(save_file_dir, exist_ok=True)
        with open(save_file_path_ok, 'w', encoding='utf-8') as file:
            for url_item in fits_url_list:
                file.write(f'{url_item}\n')
    else:
        print(f'skip-{save_file_path_ok}')


def validate_date(date_str):
    try:
        datetime.datetime.strptime(date_str, '%Y%m%d')
        return True
    except ValueError:
        return False


def calc_days_list(yyyymmdd_str, day_count_param):
    # 创建开始日期
    year = int(yyyymmdd_str[:4])
    month = int(yyyymmdd_str[4:6])
    day = int(yyyymmdd_str[6:])
    start_date = datetime.datetime(year, month, day)
    scan_day_list = []
    # 遍历日期区间
    for single_date in range(day_count_param):
        # 获取当前日期
        current_date = start_date + datetime.timedelta(days=single_date)
        yyyy = current_date.strftime('%Y')
        yyyymmdd = current_date.strftime('%Y%m%d')
        scan_day_list.append([yyyy, yyyymmdd])
    return scan_day_list


def wget_scan(item_yyyy, item_ymd, base_data_path):
    file_url_list_all_days = []
    url_list_by_day = scan_by_day_path(item_yyyy, item_ymd, recent_data, sys_name_root='GY1-DATA', file_limit=3)
    file_url_list_all_days.extend(url_list_by_day)
    url_list_by_day = scan_by_day_path(item_yyyy, item_ymd, recent_data, sys_name_root='GY2-DATA', file_limit=3)
    file_url_list_all_days.extend(url_list_by_day)
    url_list_by_day = scan_by_day_path(item_yyyy, item_ymd, recent_data, sys_name_root='GY3-DATA', file_limit=3)
    file_url_list_all_days.extend(url_list_by_day)
    url_list_by_day = scan_by_day_path(item_yyyy, item_ymd, recent_data, sys_name_root='GY4-DATA', file_limit=3)
    file_url_list_all_days.extend(url_list_by_day)
    url_list_by_day = scan_by_day_path(item_yyyy, item_ymd, recent_data, sys_name_root='GY5-DATA', file_limit=3)
    file_url_list_all_days.extend(url_list_by_day)
    url_list_by_day = scan_by_day_path(item_yyyy, item_ymd, recent_data, sys_name_root='GY6-DATA', file_limit=3)
    file_url_list_all_days.extend(url_list_by_day)

    date_time_pattern = re.compile(r"UTC(\d{8})_(\d{6})_")
    gy_pattern = re.compile(r"GY(\d)")
    k_pattern = re.compile(r"K(\d+)")
    insert_counter = 0

    for idx, item in enumerate(file_url_list_all_days):

        print(f'--pass [  {item_ymd}  ]:{idx}/ {len(file_url_list_all_days)} {item}  ')
        # 使用正则表达式提取年月日时分秒
        match = date_time_pattern.search(item)
        year_month_day = ''
        hour_minute_second = ''
        if match:
            year_month_day = match.group(1)  # 年月日
            hour_minute_second = match.group(2)  # 时分秒

        # 提取"K011"和"GY1"
        match = gy_pattern.search(item)
        gy_sys_id = ''
        k_id = ''
        if match:
            gy_sys_id = match.group(1)  # "K011" 或者其他匹配的标识符

        else:
            print(f'---!!no gy')
        match = k_pattern.search(item)
        if match:
            k_id = match.group(1)
        else:
            print(f'---!!no kid')

        insert_counter = insert_counter+1
        print(f'--x [  {item_ymd}  ]:{idx}/ {len(file_url_list_all_days)} {year_month_day}{hour_minute_second}  {gy_sys_id} {k_id} ')

    save_fits_list(file_url_list_all_days, item_ymd, base_data_path)

    return insert_counter


def run_01_scan(start_day, folder_name, base_data_path):
    print(f'start from [{start_day}]')
    days_list = calc_days_list(start_day, day_count)
    for i, r_item in enumerate(days_list):
        wget_scan(r_item[0], r_item[1], base_data_path)


def parse_args():
    parser = argparse.ArgumentParser(description="Schedule job with optional time parameter.")
    parser.add_argument('--time', type=str, help='time in YYYYMMDD format', default = '20250714')
    parser.add_argument('--data-path', type=str, help='base data path for saving files', default='e:/fix_data')
    return parser.parse_args()

def main():
    current_time = datetime.datetime.now()
    args = parse_args()
    if args.time:
        try:
            current_time = datetime.datetime.strptime(args.time, '%Y%m%d')
        except ValueError:
            print("Invalid time format. Please use YYYYMMDD.")

    folder_name = current_time.strftime('%Y%m%d')
    run_01_scan(folder_name, folder_name, args.data_path)


if __name__ == "__main__":
    main()


