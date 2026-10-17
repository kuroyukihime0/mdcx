#!/usr/bin/env python3
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


def getCoverAndFanart(html, search_html, number):  # 获取封面与预览图
    cover = ""
    extrafanart = []
    # From search html
    if search_html is not None:
        search_imgs = search_html.xpath(f"//img[contains(@src, '{number}')]/@src")
        if search_imgs and "http" in search_imgs[0]:
            cover = search_imgs[0]

    # From detail html
    imgs = html.xpath("//img/@src")
    for img in imgs:
        if not cover and number in img and "http" in img:
            cover = img
        elif "contents.fc2.com" in img or "storage" in img:
            if "http" in img and img not in extrafanart:
                extrafanart.append(img)
    return cover, extrafanart


def getMetaInfo(html):  # 从 meta description 中提取标签、日期、时长
    desc_node = html.xpath("//meta[@name='description']/@content")
    desc = desc_node[0] if desc_node else ""
    release = ""
    runtime = ""
    tags = []

    m_date = re.search(r"日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})", desc)
    if m_date:
        release = m_date.group(1).replace("/", "-")

    m_time = re.search(r"时长[：:]\s*([0-9:]+)", desc)
    if m_time:
        runtime = m_time.group(1)

    m_tags = re.search(r"标签[：:]\s*([^\r\n]+)", desc)
    if m_tags:
        raw_tags = m_tags.group(1).replace("｜", "|").split("|")
        tags = [t.strip() for t in raw_tags if t.strip() and t.strip().upper() not in ["FC2", "FC2PPV"]]

    tag_str = ",".join(dict.fromkeys(tags))
    return release, runtime, tag_str, desc


async def main(
    number,
    appoint_url="",
    **kwargs,
):
    start_time = time.time()
    website_name = "javstore"
    LogBuffer.req().write(f"-> {website_name}")
    real_url = appoint_url
    number = number.upper().replace("FC2PPV", "").replace("FC2-PPV-", "").replace("FC2-", "").replace("-", "").strip()
    dic = {}
    web_info = "\n       "
    LogBuffer.info().write(" \n    🌐 javstore")

    try:
        search_html = None
        if not real_url:
            search_url = f"https://javstore.net/search?q={number}"
            debug_info = f"搜索地址: {search_url}"
            LogBuffer.info().write(web_info + debug_info)

            search_content, error = await manager.computed.async_client.get_text(search_url)
            if search_content is None:
                debug_info = f"搜索网络请求错误: {error}"
                LogBuffer.info().write(web_info + debug_info)
                raise Exception(debug_info)

            search_html = etree.fromstring(search_content, etree.HTMLParser())
            links = search_html.xpath(f"//a[contains(@href, '{number}')]/@href")
            if not links:
                debug_info = "搜索结果: 未匹配到番号！"
                LogBuffer.info().write(web_info + debug_info)
                raise Exception(debug_info)

            target_link = links[0]
            if not target_link.startswith("http"):
                target_link = "https://javstore.net" + target_link
            real_url = target_link

        debug_info = f"番号地址: {real_url}"
        LogBuffer.info().write(web_info + debug_info)

        html_content, error = await manager.computed.async_client.get_text(real_url)
        if html_content is None:
            debug_info = f"网络请求错误: {error}"
            LogBuffer.info().write(web_info + debug_info)
            raise Exception(debug_info)

        html_info = etree.fromstring(html_content, etree.HTMLParser())
        title = getTitle(html_info)
        if not title:
            debug_info = "数据获取失败: 未获取到title！"
            LogBuffer.info().write(web_info + debug_info)
            raise Exception(debug_info)

        full_title = f"FC2-{number} {title}"
        cover_url, extrafanart = getCoverAndFanart(html_info, search_html, number)
        release, runtime, tag, outline = getMetaInfo(html_info)
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
                "runtime": runtime,
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
                "extrafanart": extrafanart,
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
