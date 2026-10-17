#!/usr/bin/env python3
import re
import time

from lxml import etree

from ..config.manager import manager
from ..models.log_buffer import LogBuffer


def getTitle(html):  # 获取标题
    result = html.xpath("//h1/text() | //article//h2/a/text() | //meta[@property='og:title']/@content")
    if result:
        title = result[0].strip()
        title = re.sub(r" - JavPop.*$", "", title, flags=re.I)
        title = re.sub(r"^FC2[-_]?PPV[-_]?\d+\s*", "", title, flags=re.I)
        return title.strip()
    return ""


def getCover(html, number):  # 获取封面
    if html is not None:
        imgs = html.xpath("//div[contains(@class, 'content') or contains(@class, 'entry')]//img/@src")
        for img in imgs:
            if number in img or "poster" in img or "fc2" in img.lower():
                return img
    # Default direct poster URL on javpop
    return f"https://i0.wp.com/javpop.com/img/fc2/fc2_ppv-{number}_poster.jpg"


def getRelease(html_content):  # 获取发布日期
    m = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", html_content)
    return m.group(1).replace("/", "-") if m else ""


def getTags(html):  # 获取标签
    tags = html.xpath("//a[contains(@rel, 'tag')]/text() | //div[contains(@class, 'tag')]//a/text()")
    clean_tags = [t.strip() for t in tags if t.strip() and t.strip().upper() not in ["FC2", "FC2PPV"]]
    return ",".join(dict.fromkeys(clean_tags))


async def main(
    number,
    appoint_url="",
    **kwargs,
):
    start_time = time.time()
    website_name = "javpop"
    LogBuffer.req().write(f"-> {website_name}")
    real_url = appoint_url
    number = number.upper().replace("FC2PPV", "").replace("FC2-PPV-", "").replace("FC2-", "").replace("-", "").strip()
    dic = {}
    web_info = "\n       "
    LogBuffer.info().write(" \n    🌐 javpop")

    try:
        if not real_url:
            real_url = f"https://javpop.com/?s=FC2-PPV-{number}"

        debug_info = f"番号地址: {real_url}"
        LogBuffer.info().write(web_info + debug_info)

        html_content, error = await manager.computed.async_client.get_text(real_url)
        html_info = None
        if html_content and "404" not in html_content:
            try:
                html_info = etree.fromstring(html_content, etree.HTMLParser())
                post_links = html_info.xpath("//article//h2/a/@href | //div[contains(@class, 'post')]//h2/a/@href")
                if post_links:
                    for plink in post_links:
                        if number in plink:
                            real_url = plink
                            html_content, error = await manager.computed.async_client.get_text(real_url)
                            html_info = etree.fromstring(html_content, etree.HTMLParser())
                            break
            except Exception:
                pass

        title = ""
        cover_url = f"https://i0.wp.com/javpop.com/img/fc2/fc2_ppv-{number}_poster.jpg"
        release = ""
        tag = ""
        outline = ""

        if html_info is not None:
            title = getTitle(html_info)
            cover_url = getCover(html_info, number)
            release = getRelease(html_content)
            tag = getTags(html_info)
            outline_nodes = html_info.xpath("//div[contains(@class, 'entry-content')]//p//text()")
            outline = " ".join([t.strip() for t in outline_nodes if t.strip()]) if outline_nodes else ""

        if not title:
            title = f"FC2-PPV-{number}"

        full_title = f"FC2-{number} {title}" if title != f"FC2-PPV-{number}" else f"FC2-{number}"
        mosaic = "无码" if "無修正" in title or "无修正" in tag or "無修正" in tag else "有码"

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
                "runtime": "",
                "score": "",
                "series": "FC2系列",
                "director": "",
                "studio": "FC2",
                "publisher": "FC2",
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
