#!/usr/bin/env python3
import datetime
import re
import time

from lxml import etree

from ..config.manager import manager
from ..models.log_buffer import LogBuffer


def getTitle(html):  # 获取标题
    result = html.xpath("//h1/text() | //meta[@property='og:title']/@content")
    if result:
        title = result[0].strip()
        title = re.sub(r"^FC2[-_]?PPV[-_]?\d+\s*", "", title, flags=re.I)
        return title.strip()
    return ""


def getCover(html):  # 获取封面
    result = html.xpath("//meta[@property='og:image']/@content")
    return result[0].strip() if result and "http" in result[0] else ""


def parseDate(date_str):  # 解析日期
    if not date_str:
        return ""
    date_str = date_str.strip()
    m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", date_str)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    try:
        clean = date_str.replace(".", "")
        dt = datetime.datetime.strptime(clean, "%b %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return ""


def getDetails(html):  # 提取详情区字段
    info_map = {}
    items = html.xpath("//div[contains(@class, 'detail') or contains(@class, 'info')]//div | //div[contains(@class, 'detail') or contains(@class, 'info')]//p")
    for item in items:
        text = " ".join(item.xpath(".//text()")).strip()
        if ":" in text:
            k, v = text.split(":", 1)
            info_map[k.strip().lower()] = v.strip()
    return info_map


async def main(
    number,
    appoint_url="",
    **kwargs,
):
    start_time = time.time()
    website_name = "sextb"
    LogBuffer.req().write(f"-> {website_name}")
    real_url = appoint_url
    number = number.upper().replace("FC2PPV", "").replace("FC2-PPV-", "").replace("FC2-", "").replace("-", "").strip()
    dic = {}
    web_info = "\n       "
    LogBuffer.info().write(" \n    🌐 sextb")

    try:
        if not real_url:
            real_url = f"https://sextb.net/fc2ppv-{number}"

        debug_info = f"番号地址: {real_url}"
        LogBuffer.info().write(web_info + debug_info)

        html_content, error = await manager.computed.async_client.get_text(real_url)
        if html_content is None or "404 Page Not Found" in html_content:
            debug_info = f"未找到内容: {error or '404'}"
            LogBuffer.info().write(web_info + debug_info)
            raise Exception(debug_info)

        html_info = etree.fromstring(html_content, etree.HTMLParser())
        title = getTitle(html_info)
        if not title:
            debug_info = "数据获取失败: 未获取到title！"
            LogBuffer.info().write(web_info + debug_info)
            raise Exception(debug_info)

        full_title = f"FC2-{number} {title}"
        cover_url = getCover(html_info)
        details = getDetails(html_info)

        raw_date = details.get("release date", "")
        if not raw_date:
            desc = html_info.xpath("//meta[@property='og:description']/@content")
            if desc:
                m = re.search(r"release date ([A-Za-z]{3}\.?\s*\d{1,2},\s*\d{4})", desc[0])
                if m:
                    raw_date = m.group(1)
        release = parseDate(raw_date)

        raw_runtime = details.get("runtimes", "")
        runtime_m = re.search(r"\d+", raw_runtime)
        runtime = runtime_m.group(0) if runtime_m else ""

        raw_genres = details.get("genre(s)", "")
        if not raw_genres:
            genres_list = html_info.xpath("//a[contains(@href, '/search/')]/text()")
            raw_genres = ",".join(genres_list)
        tags = [t.strip() for t in raw_genres.split(",") if t.strip() and t.strip().lower() not in ["fc2", "fc2ppv"]]
        tag = ",".join(dict.fromkeys(tags))

        studio = details.get("studio", "FC2")
        mosaic = "无码" if "uncensored" in tag.lower() or "無修正" in title or "无修正" in title else "有码"

        outline_nodes = html_info.xpath("//div[contains(@class, 'description')]//text() | //meta[@name='description']/@content")
        outline = " ".join([t.strip() for t in outline_nodes if t.strip()]) if outline_nodes else ""

        try:
            dic = {
                "number": f"FC2-{number}",
                "title": full_title,
                "originaltitle": full_title,
                "actor": "",
                "outline": outline,
                "originalplot": outline,
                "tag": tag,
                "release": release,
                "year": release[:4] if release else "",
                "runtime": runtime,
                "score": "",
                "series": "FC2系列",
                "director": "",
                "studio": studio,
                "publisher": studio,
                "source": website_name,
                "website": real_url,
                "actor_photo": {},
                "thumb": cover_url,
                "poster": cover_url,
                "extrafanart": [],
                "trailer": "",
                "image_download": False,
                "image_cut": "center",
                "mosaic": mosaic,
                "wanted": "",
            }
            debug_info = "数据获取成功！"
            LogBuffer.info().write(web_info + debug_info)
        except Exception as e:
            debug_info = f"数据生成出错: {str(e)}"
            LogBuffer.info().write(web_info + debug_info)
            raise Exception(debug_info)

    except Exception as e:
        LogBuffer.error().write(str(e))
        dic = {
            "title": "",
            "thumb": "",
            "website": "",
        }

    dic = {website_name: {"zh_cn": dic, "zh_tw": dic, "jp": dic}}
    LogBuffer.req().write(f"({round(time.time() - start_time)}s) ")
    return dic
