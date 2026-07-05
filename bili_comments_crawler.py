import os
import re
import json
import time
import csv
import hashlib
import random
import datetime as dt
from urllib.parse import quote

import requests
import pandas as pd
from tqdm import tqdm

# ===================== 你需要改的配置 =====================
EXCEL_PATH = r"台风桦加沙.xlsx"      # ← 改成你的Excel路径（也可绝对路径）
OUT_DIR = r"bili_comment_export"  # ← 输出目录
COOKIE = ""                       # ← 强烈建议填：浏览器里复制的整段 Cookie 字符串
# ========================================================

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

# WBI 混淆表（来自社区整理的算法描述）
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52
]

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def iso_time(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

def safe_sleep():
    time.sleep(random.uniform(0.35, 0.9))

def build_session(cookie: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.bilibili.com",
    })
    if cookie:
        s.headers["Cookie"] = cookie
    return s

def req_json(s: requests.Session, url: str, params: dict, retries=5):
    for i in range(retries):
        try:
            r = s.get(url, params=params, timeout=15)
            # 常见风控/失败：403/412 等
            if r.status_code in (403, 412):
                time.sleep(1.5 + i)
                continue
            r.raise_for_status()
            j = r.json()
            return j
        except Exception:
            time.sleep(1.0 + i)
    return None

# -------- WBI 签名（按社区公开整理的流程实现：nav取key + 拼mixin_key + md5 w_rid）--------
def get_wbi_keys(s: requests.Session):
    nav_url = "https://api.bilibili.com/x/web-interface/nav"
    j = req_json(s, nav_url, params={})
    if not j or "data" not in j or "wbi_img" not in j["data"]:
        return None, None
    img_url = j["data"]["wbi_img"]["img_url"]
    sub_url = j["data"]["wbi_img"]["sub_url"]
    img_key = os.path.splitext(os.path.basename(img_url))[0]
    sub_key = os.path.splitext(os.path.basename(sub_url))[0]
    return img_key, sub_key

def get_mixin_key(img_key: str, sub_key: str) -> str:
    raw = (img_key + sub_key)
    return "".join(raw[i] for i in MIXIN_KEY_ENC_TAB)[:32]

def enc_wbi(params: dict, mixin_key: str) -> dict:
    # 1) 加 wts
    wts = int(time.time())
    params = {k: str(v) for k, v in params.items()}
    params["wts"] = str(wts)

    # 2) 过滤 value 中的 "!'()*"
    bad = set("!'()*")
    for k, v in list(params.items()):
        params[k] = "".join(ch for ch in v if ch not in bad)

    # 3) key 升序 + encodeURIComponent 风格编码（quote 默认就是 %20，且十六进制大写）
    items = sorted(params.items(), key=lambda x: x[0])
    query = "&".join(f"{k}={quote(v, safe='-_.~')}" for k, v in items)

    # 4) w_rid = md5(query + mixin_key)
    w_rid = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    signed = dict(params)
    signed["w_rid"] = w_rid
    return signed

# -------- 视频信息：bvid -> aid + stat.reply --------
def get_video_info(s: requests.Session, bvid: str):
    url = "https://api.bilibili.com/x/web-interface/view"
    j = req_json(s, url, params={"bvid": bvid})
    if not j or j.get("code") != 0:
        return None
    data = j["data"]
    aid = data.get("aid")
    stat_reply = None
    if isinstance(data.get("stat"), dict):
        stat_reply = data["stat"].get("reply")
    return {
        "bvid": bvid,
        "aid": aid,
        "title": data.get("title"),
        "stat_reply": stat_reply
    }

# -------- 一级评论：wbi/main 游标分页（pagination_str = {"offset": next_offset}）--------
def iter_main_comments_wbi(s: requests.Session, aid: int, mixin_key: str, mode=3, plat=1, web_location=1315873, ps=20):
    """
    说明：
    - 接口：https://api.bilibili.com/x/v2/reply/wbi/main  :contentReference[oaicite:3]{index=3}
    - 返回里通常能拿到：
      cursor.is_end / cursor.all_count / cursor.pagination_reply.next_offset，
      下一页用 pagination_str={"offset": next_offset}  :contentReference[oaicite:4]{index=4}
    """
    url = "https://api.bilibili.com/x/v2/reply/wbi/main"

    pagination_str = ""  # 首页空
    while True:
        base_params = {
            "type": 1,
            "oid": aid,
            "mode": mode,
            "plat": plat,
            "web_location": web_location,
            "ps": ps,
        }
        if pagination_str:
            base_params["pagination_str"] = pagination_str

        signed = enc_wbi(base_params, mixin_key)
        j = req_json(s, url, params=signed)
        if not j or j.get("code") != 0 or not j.get("data"):
            break

        data = j["data"]
        cursor = data.get("cursor") or {}
        replies = data.get("replies") or []
        yield replies, cursor

        if cursor.get("is_end") is True:
            break

        next_offset = (((cursor.get("pagination_reply") or {}).get("next_offset")) or "")
        if not next_offset:
            break
        pagination_str = json.dumps({"offset": next_offset}, ensure_ascii=False)

        safe_sleep()

# -------- 二级回复：reply/reply 固定分页 pn/ps --------
def iter_sub_replies(s: requests.Session, aid: int, root_rpid: int, ps=20):
    url = "https://api.bilibili.com/x/v2/reply/reply"
    pn = 1
    while True:
        params = {
            "type": 1,
            "oid": aid,
            "root": root_rpid,
            "pn": pn,
            "ps": ps,
        }
        j = req_json(s, url, params=params)
        if not j or j.get("code") != 0 or not j.get("data"):
            break
        data = j["data"]
        replies = data.get("replies") or []
        if not replies:
            break
        yield replies

        page = data.get("page") or {}
        count = page.get("count")
        size = page.get("size", ps)
        if count is not None and pn * size >= count:
            break

        pn += 1
        safe_sleep()

def extract_text(reply_obj: dict) -> str:
    # 主体文本在 content.message
    c = reply_obj.get("content") or {}
    return c.get("message") or ""

def extract_user(reply_obj: dict):
    m = reply_obj.get("member") or {}
    return m.get("mid"), m.get("uname")

def extract_location(reply_obj: dict):
    # 有些返回会带 reply_control.location，比如“IP属地：...”
    rc = reply_obj.get("reply_control") or {}
    return rc.get("location")

def crawl_one_video(s: requests.Session, bvid: str, out_dir: str, mixin_key: str):
    info = get_video_info(s, bvid)
    if not info or not info.get("aid"):
        return {"bvid": bvid, "ok": False, "error": "video_info_failed"}

    aid = int(info["aid"])
    per_csv = os.path.join(out_dir, f"{bvid}.csv")

    fieldnames = [
        "bvid", "aid", "level", "rpid", "root_rpid", "parent_rpid",
        "ctime", "ctime_iso", "mid", "uname", "like", "reply_count",
        "location", "message"
    ]
    fetched = 0
    fetched_root = 0
    fetched_sub = 0
    all_count_cursor = None

    with open(per_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()

        for replies, cursor in iter_main_comments_wbi(s, aid, mixin_key):
            if all_count_cursor is None:
                all_count_cursor = cursor.get("all_count")
            for r in replies:
                fetched += 1
                fetched_root += 1
                rpid = r.get("rpid")
                ctime = int(r.get("ctime", 0))
                mid, uname = extract_user(r)
                row = {
                    "bvid": bvid,
                    "aid": aid,
                    "level": 1,
                    "rpid": rpid,
                    "root_rpid": rpid,
                    "parent_rpid": rpid,
                    "ctime": ctime,
                    "ctime_iso": iso_time(ctime) if ctime else "",
                    "mid": mid,
                    "uname": uname,
                    "like": r.get("like"),
                    "reply_count": r.get("rcount"),
                    "location": extract_location(r),
                    "message": extract_text(r),
                }
                w.writerow(row)

                # 二级回复（楼中楼）
                if r.get("rcount", 0) and rpid:
                    for sub_list in iter_sub_replies(s, aid, int(rpid), ps=20):
                        for sr in sub_list:
                            fetched += 1
                            fetched_sub += 1
                            srpid = sr.get("rpid")
                            sctime = int(sr.get("ctime", 0))
                            smid, suname = extract_user(sr)
                            w.writerow({
                                "bvid": bvid,
                                "aid": aid,
                                "level": 2,
                                "rpid": srpid,
                                "root_rpid": rpid,
                                "parent_rpid": sr.get("parent") or rpid,
                                "ctime": sctime,
                                "ctime_iso": iso_time(sctime) if sctime else "",
                                "mid": smid,
                                "uname": suname,
                                "like": sr.get("like"),
                                "reply_count": sr.get("rcount"),
                                "location": extract_location(sr),
                                "message": extract_text(sr),
                            })

    return {
        "bvid": bvid,
        "aid": aid,
        "title": info.get("title"),
        "stat_reply": info.get("stat_reply"),       # 视频信息里的评论数
        "cursor_all_count": all_count_cursor,       # 评论接口返回的 all_count
        "fetched_total": fetched,
        "fetched_root": fetched_root,
        "fetched_sub": fetched_sub,
        "ok": True,
        "error": ""
    }

def guess_bvid_column(df: pd.DataFrame) -> str:
    # 尽量自动找包含“BV”的列
    cols = list(df.columns)
    for c in cols:
        if re.search(r"\bBV\b|bvid|bv号|BV号", str(c), flags=re.IGNORECASE):
            return c
    return cols[0]

def normalize_bvid(x: str) -> str:
    if not isinstance(x, str):
        x = str(x)
    x = x.strip()
    # 允许你Excel里是链接，提取BV号
    m = re.search(r"(BV[0-9A-Za-z]{10,})", x)
    return m.group(1) if m else x

def main():
    ensure_dir(OUT_DIR)
    per_dir = os.path.join(OUT_DIR, "per_video")
    ensure_dir(per_dir)

    s = build_session(COOKIE)

    # 读 Excel
    df = pd.read_excel(EXCEL_PATH)
    col = guess_bvid_column(df)
    bvids = [normalize_bvid(v) for v in df[col].dropna().tolist()]

    # 去重 + 记录重复项
    seen = set()
    dup = []
    uniq = []
    for b in bvids:
        if b in seen:
            dup.append(b)
        else:
            seen.add(b)
            uniq.append(b)

    if dup:
        with open(os.path.join(OUT_DIR, "duplicate_bvids.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(dup))

    # 准备 WBI key
    img_key, sub_key = get_wbi_keys(s)
    if not img_key or not sub_key:
        raise RuntimeError("拿不到 WBI keys（nav接口无 wbi_img）。建议：填 Cookie 后重试。")
    mixin_key = get_mixin_key(img_key, sub_key)

    summary_path = os.path.join(OUT_DIR, "video_summary.csv")
    summary_fields = [
        "bvid", "aid", "title", "stat_reply", "cursor_all_count",
        "fetched_total", "fetched_root", "fetched_sub", "ok", "error"
    ]
    with open(summary_path, "w", encoding="utf-8-sig", newline="") as fsum:
        sw = csv.DictWriter(fsum, fieldnames=summary_fields)
        sw.writeheader()

        for bvid in tqdm(uniq, desc="Crawling"):
            out_csv = os.path.join(per_dir, f"{bvid}.csv")
            if os.path.exists(out_csv) and os.path.getsize(out_csv) > 200:
                # 已经爬过就跳过（避免重复写）
                sw.writerow({
                    "bvid": bvid, "aid": "", "title": "", "stat_reply": "", "cursor_all_count": "",
                    "fetched_total": "", "fetched_root": "", "fetched_sub": "", "ok": True, "error": "skipped_existing"
                })
                continue

            res = crawl_one_video(s, bvid, per_dir, mixin_key)
            sw.writerow({k: res.get(k, "") for k in summary_fields})
            safe_sleep()

    print("Done. Output:", os.path.abspath(OUT_DIR))

if __name__ == "__main__":
    main()
