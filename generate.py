import os
import requests
import re
from joblib import Parallel, delayed

from src.config.lists import categories

# ================================
# 下载器（增强版）
# ================================

def download_list(url, path, retries=3, timeout=15):
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=timeout)

            if response.status_code != 200:
                print(f"[WARN] Status {response.status_code} for {url} (saving empty file: {path})")

            # 自动创建目录
            os.makedirs(os.path.dirname(path), exist_ok=True)

            with open(path, "w", encoding="utf-8", errors="ignore") as f:
                f.write(response.text)

            return  # 成功直接退出

        except Exception as e:
            print(f"[ERROR] Download failed ({attempt}/{retries}) for {url}: {e}")

    print(f"[FATAL] Failed after {retries} attempts → {url}")


# ================================
# 并行下载任务准备
# ================================

downloads_list = []
for category in categories.keys():
    os.makedirs(category, exist_ok=True)  # 代替 try/except
    for i in categories[category]:
        downloads_list.append([i["url"], f"{category}/{i['name']}.txt"])

# 并行执行下载任务（不会中断整个流程）
Parallel(n_jobs=16, prefer="threads")(
    delayed(download_list)(url, path) for url, path in downloads_list
)


# ================================
# Allowlist 读取
# ================================

with open("allowlist.txt", "r", encoding="utf-8", errors="ignore") as f:
    ALLOWLIST = f.read().splitlines()


# ================================
# 转换规则相关函数（与你原本一致）
# ================================

def convert_pihole_list(list):
    pihole_list = []
    for line in list:
        line = line.replace("^", "")
        if "||" in line and "*" not in line and "@@" not in line:
            line = line.replace("||", "")
            if "|" in line:
                continue
            pihole_list.append(line)
    return pihole_list


def convert_line(line):
    line = line.replace("0.0.0.0 ", "").replace("127.0.0.1 ", "")
    line = line.replace("^", "")
    line = line.split("$")[0]
    line += "^"
    if line.startswith("||") or line.startswith("@@"):
        return line
    else:
        return "||" + line


def skip_line(line):
    line = line.replace("||", "").replace("@@", "").replace("^", "")
    if any(x in line for x in ALLOWLIST):
        return True
    if line == "":
        return True
    if any(x in line for x in [" ", "#", "!", "/", "$"]):
        return True
    return False


def is_valid_string(line):
    s = line.replace("|", "").replace("@@", "").replace("*", "").replace("^", "")
    return re.fullmatch(r'^[-.\w]+$', s) is not None


def convert_list(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            output = []
            for line in f.read().splitlines():
                line = convert_line(line)
                if skip_line(line):
                    continue
                if not is_valid_string(line):
                    print("[INVALID]", line)
                output.append(line)
            return output
    except FileNotFoundError:
        print(f"[Missing File] {path}")
        return []


# ================================
# 输出文件写入
# ================================

def write_lists_to_file(filtered_out, adguard_out, pihole_out, path):
    with open(path + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(filtered_out))

    with open(path + ".adguard", "w", encoding="utf-8") as f:
        f.write("\n".join(adguard_out))

    with open(path + ".pihole", "w", encoding="utf-8") as f:
        f.write("\n".join(pihole_out))


# ================================
# 分类合并
# ================================

adguard_list = []
pihole_list = []

for category in categories.keys():
    adguard_category_list = []
    pihole_category_list = []

    for i in categories[category]:
        converted = convert_list(i["txt"])
        adguard_category_list += converted
        pihole_category_list += convert_pihole_list(converted)

    write_lists_to_file(pihole_category_list, adguard_category_list, pihole_category_list, category)

    adguard_list += adguard_category_list
    pihole_list += pihole_category_list

# 总输出
write_lists_to_file(pihole_list, adguard_list, pihole_list, "list")
