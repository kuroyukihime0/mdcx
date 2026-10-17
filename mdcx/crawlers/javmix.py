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
        title = re.sub(r" - Javmix\.TV$", "", title)
        title = re.sub(r" エロ動画$", "", title)
        title = re.sub(r"^FC2PPV\s*\d+\s*", "", title)
        return title.strip()
    return ""


def getCover(html, number):  # 获取封面
    cover = html.xpath("//div[@id='iframe']/img/@src")
    if cover and "http" in cover[0]:
        return cover[0]
    cover = html.xpath("//meta[@property='og:image']/@content")
    if cover and "http" in cover[0]:
        return cover[0]
    cover = html.xpath(f"//img[contains(@src, '{number}') or contains(@src, 'fc2')]/@src")
    if cover and "http" in cover[0]:
        return cover[0]
    return ""


def getRelease(html_content):  # 获取发行日期
    date_match = re.search(r'"datePublished":\s*"(\d{4}-\d{2}-\d{2})', html_content)
    if date_match:
        return date_match.group(1)
    date_match = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", html_content)
    if date_match:
        return date_match.group(1).replace("/", "-")
    return ""


def getOutline(html):  # 获取简介
    result = html.xpath("//meta[@name='description']/@content | //meta[@property='og:description']/@content")
    return result[0].strip() if result else ""


def getTag(html):  # 获取标签
    tags = html.xpath("//div[contains(@class, 'tag')]//a/text() | //span[contains(@class, 'tag')]//a/text()")
    if not tags:
        tags_meta = html.xpath("//meta[@name='keywords']/@content")
        if tags_meta:
            tags = tags_meta[0].split(",")
    clean_tags = [t.strip() for t in tags if t.strip() and t.strip().upper() not in ["FC2", "FC2PPV", "FC2-PPV"]]
    return ",".join(dict.fromkeys(clean_tags))


def getMosaic(title, tag):
    return "无码" if "無修正" in title or "无修正" in tag or "無修正" in tag else "有码"


async def main(
    number,
    appoint_url="",
    **kwargs,
):
    start_time = time.time()
    website_name = "javmix"
    LogBuffer.req().write(f"-> {website_name}")
    real_url = appoint_url
    number = number.upper().replace("FC2PPV", "").replace("FC2-PPV-", "").replace("FC2-", "").replace("-", "").strip()
    dic = {}
    web_info = "\n       "
    LogBuffer.info().write(" \n    🌐 javmix")

    try:
        if not real_url:
            real_url = f"https://javmix.tv/fc2ppv/mx-fc2ppv-{number}/"

        debug_info = f"番号地址: {real_url}"
        LogBuffer.info().write(web_info + debug_info)

        html_content, error = await manager.computed.async_client.get_text(real_url)
        if html_content is None or "404 Not Found" in html_content:
            alt_url = f"https://javmix.tv/fc2ppv/fc2-ppv-{number}/"
            html_content, error = await manager.computed.async_client.get_text(alt_url)
            if html_content and "404 Not Found" not in html_content:
                real_url = alt_url

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
        cover_url = getCover(html_info, number)
        release = getRelease(html_content)
        outline = getOutline(html_info)
        tag = getTag(html_info)
        studio = "FC2"
        actor = ""
        mosaic = getMosaic(title, tag)

        try:
            dic = {
                "number": f"FC2-{number}",
                "title": full_title,
                "originaltitle": full_title,
                "actor": actor,
                "outline": outline,
                "originalplot": outline,
                "tag": tag,
                "release": release,
                "year": release[:4] if release else "",
                "runtime": "",
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
