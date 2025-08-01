import datetime
import re
import subprocess


def scan_by_day_path(year_in_path, ymd_in_paht, recent_data, sys_name_root='GY6-DATA', file_limit=0):
    # 最后的斜线很重要，否则wget np参数会不识别，造成下载其他不必要的数据
    # download_url_root = f'https://download.china-vo.org/psp/east/{year_in_path}/{ymd_in_paht}/'
    if recent_data:
        download_url_root = f'https://download.china-vo.org/psp/KATS/{sys_name_root}/{ymd_in_paht}/'
    else:
        download_url_root = f'https://download.china-vo.org/psp/KATS/{sys_name_root}/{year_in_path}/{ymd_in_paht}/'
    # download_url_root = r'https://download.china-vo.org/psp/east/2023/20230511/P033_22.22%2B35.0/'
    temp_path = r'E:/test_download'
    print(f'path: {temp_path}')
    print(f'path: {download_url_root}')
    # 运行wget命令的spider功能，检查网站的链接，而不下载任何文件，并返回一个进程对象
    process = subprocess.Popen(["wget", "-N",
                                # ###   no download no dir creat
                                "--spider", "-nd",
                                '--user-agent', 'MyCustomUserAgent',
                                "-r", "-np", "-nH", "-R", "index.html", "-P", temp_path, "--level=0",
                                # https 证书过期处理
                                "--no-check-certificate",
                                download_url_root], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("the commandline is {}".format(process.args))
    # 创建一个空的文件url列表
    file_url_list = []
    download_file_counter = 0
    skip_counter = 0
    # 迭代进程对象的输出，提取文件url
    for line in process.stderr:
        # 如果输出行以“--”开头，说明是一个文件url
        line = line.strip()
        # print(f'??{line.strip()}')
        if line.startswith(b"--") and (line.endswith(b".fts") or line.endswith(b".fit") or line.endswith(b".fits")):
            # 去掉开头和结尾的空格和换行符，得到文件url
            file_url = line.strip()
            urls = re.findall(b'https?://\\S+', file_url)
            urls = [url.decode('utf-8') for url in urls]
            assert len(urls) == 1
            # skip east Calibration
            if urls[0].__contains__("Calibration"):
                skip_counter = skip_counter + 1
                # print(f' skip Calibration {line}')
                continue
            if urls[0].__contains__("_FZ"):
                skip_counter = skip_counter + 1
                # print(f' skip Calibration {line}')
                continue
            # skip Kats Flat and fiel
            if urls[0].__contains__("Flat"):
                skip_counter = skip_counter + 1
                print(f' skip Flat {line}')
                continue
            if urls[0].__contains__("fiel"):
                skip_counter = skip_counter + 1
                print(f' skip fiel {line}')
                continue
            # 把文件url添加到文件url列表中
            file_url_list.append(urls[0])

            # print(urls)
            download_file_counter = download_file_counter + 1
            if 0 < file_limit <= download_file_counter:
                break

        # print(line)

    # 将匹配到的URL从bytes转换为strings

    print(f'path>>: {len(file_url_list)}   /   {download_file_counter}    skip:{skip_counter}')
    return file_url_list

