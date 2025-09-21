import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich import print, print_json
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..browser import BrowserProvider
from ..config.manager import manager
from ..config.models import Language, Website
from ..crawler import Never
from ..crawlers import get_crawler_compat
from ..crawlers.base import GenericBaseCrawler, get_crawler
from ..crawlers.base.compat import LegacyCrawler
from ..manual import ManualConfig
from ..models.types import CrawlerInput
from ..utils import executor
from ..web_async import AsyncWebClient

app = typer.Typer(help="爬虫调试工具", context_settings={"help_option_names": ["-h", "--help"]})
console = Console()
os.environ["MDCX_SHOW_BROWSER"] = "1"  # 显示浏览器界面

proxy_help = "代理地址 (例如: http://127.0.0.1:7890). 如未指定将加载 config 设置"


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    sites: Annotated[list[Website] | None, typer.Option("--site", "-s", help="指定网站")] = None,
    # CrawlerInput
    number: Annotated[str, typer.Option("--number", "-n", rich_help_panel="CrawlerInput")] = "",
    appoint_url: Annotated[str, typer.Option("--appoint-url", "-u", rich_help_panel="CrawlerInput")] = "",
    file_path: Annotated[Path | None, typer.Option("--file-path", "-f", rich_help_panel="CrawlerInput")] = None,
    short_number: Annotated[str, typer.Option("--short-number", rich_help_panel="CrawlerInput")] = "",
    mosaic: Annotated[str, typer.Option("--mosaic", "-m", rich_help_panel="CrawlerInput")] = "",
    appoint_number: Annotated[str, typer.Option("--appoint-number", rich_help_panel="CrawlerInput")] = "",
    language: Annotated[str, typer.Option("--language", "-l", rich_help_panel="CrawlerInput")] = "",
    org_language: Annotated[str, typer.Option("--org-language", rich_help_panel="CrawlerInput")] = "",
    # 输出选项
    output: Annotated[str | None, typer.Option("--output", "-o", help="文件保存路径, 可使用 {site} 变量")] = None,
    # 网络选项
    proxy: Annotated[str | None, typer.Option("--proxy", "-p", help=proxy_help)] = None,
    timeout: Annotated[int, typer.Option("--timeout", "-t", help="请求超时时间（秒）")] = 5,
    retry: Annotated[int, typer.Option("--retry", "-r", help="重试次数")] = 1,
):
    """调用指定网站获取数据并保存到文件."""

    # 如果有子命令被调用，不执行根命令逻辑
    if ctx.invoked_subcommand is not None:
        return

    # 检查是否提供了网站参数
    if sites is None:
        console.print("[red]错误: 必须指定网站类型，请使用 --site 参数[/red]")
        console.print("可用网站列表:")
        for i, available_site in enumerate(Website, 1):
            console.print(f"  {i:2d}. {available_site}")
        raise typer.Exit(1)

    crawler_input = CrawlerInput(
        number=number,
        appoint_url=appoint_url,
        file_path=file_path,
        short_number=short_number,
        mosaic=mosaic,
        appoint_number=appoint_number,
        language=Language(language or "undefined"),
        org_language=Language(org_language or "undefined"),
    )

    if not any((number, appoint_url)):
        console.print("[red]错误: number 和 appoint_url 至少需要提供一个[/red]")
        raise typer.Exit(1)

    _crawl(
        sites=sites,
        input=crawler_input,
        output=output,
        proxy=proxy,
        timeout=timeout,
        retry=retry,
    )


def _crawl(sites: list[Website], input: CrawlerInput, output: str | None, proxy: str | None, timeout: int, retry: int):
    classes = [get_crawler_compat(site) for site in sites]

    client = AsyncWebClient(
        loop=executor._loop,
        proxy=proxy or (manager.config.proxy if manager.config.use_proxy else None),
        retry=retry,
        timeout=timeout,
        log_fn=lambda msg: print(f"[dim][AsyncWebClient] {msg}[/dim]"),
    )

    browser_provider = BrowserProvider(manager.config)

    async def task(c: type[GenericBaseCrawler[Never]] | LegacyCrawler):
        crawler = c(
            client=client,
            base_url=manager.config.get_site_url(c.site()),
            browser=await browser_provider.get_browser(),
        )
        return await crawler.run(input)

    futures = [executor.submit(task(c)) for c in classes]
    executor.wait_all()

    for i, f in enumerate(futures):
        print(f"\n[blue]====== Res from site: [bold]{sites[i]}[/bold] ======[/blue]")
        if f.exception():
            print(f"[red]错误: {f.exception()}[/red]")
            continue

        res = f.result()
        print("[bold blue]Debug Info:[/bold blue]")
        print("\t" + "\n\t".join("\n".join(res.debug_info.logs).splitlines()))
        print(f"\n[bold]耗时: {res.debug_info.execution_time:.2f} 秒[/bold]\n")
        if res.data:
            print("[green]成功. 结果:[/green]\n")
            j = json.dumps(asdict(res.data), ensure_ascii=False, indent=2)
            print_json(j)
            if output:
                output_path = Path(output.replace("{site}", sites[i].value))
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(j, encoding="utf-8")
                print(f"[green]结果已保存到: {output_path}[/green]")
        else:
            print("[red]失败[/red]\n")
            if res.debug_info.error:
                print(f"[red]{res.debug_info.error}[/red]")


site_help = "指定网站类型. 若未指定, 将尝试从 URL 自动检测. 若有相应 GenericBaseCrawler 实现, 将调用其 _fetch_detail 方法, 否则将直接使用 AsyncWebClient.get_text"


@app.command()
def fetch(
    url: Annotated[str, typer.Argument(help="要获取的详情页URL")],
    site: Annotated[Website | None, typer.Option("--site", "-s", help=site_help)] = None,
    use_browser: Annotated[bool, typer.Option("--use-browser", "-b", help="是否使用浏览器")] = False,
    output: Annotated[str | None, typer.Option("--output", "-o", help="保存文件路径")] = None,
    number: Annotated[str | None, typer.Option("--number", "-n")] = None,
    base_dir: Annotated[str, typer.Option("--base-dir", "-d", help="基础输出目录")] = "tests/crawlers/data",
    proxy: Annotated[str | None, typer.Option("--proxy", "-p", help=proxy_help)] = None,
    timeout: Annotated[int, typer.Option("--timeout", "-t", help="请求超时时间（秒）")] = 5,
    retry: Annotated[int, typer.Option("--retry", "-r", help="重试次数")] = 1,
):
    """复用指定网站的 GenericBaseCrawler 详情页请求方法获取 URL 并保存到文件."""

    if not site:
        site = _detect_site_from_url(url)
        if site:
            console.print(f"[green]自动检测到网站类型: {site}[/green]")

    asyncio.run(
        _fetch_async(
            url=url,
            website=site,
            use_browser=use_browser,
            output_path=output,
            number=number,
            base_dir=base_dir,
            proxy=proxy,
            timeout=timeout,
            retry=retry,
        )
    )


@app.command()
def show_config():
    """显示当前配置信息"""
    console.print("[bold blue]当前配置信息:[/bold blue]")
    console.print()
    console.print(f"代理: {(manager.config.proxy if manager.config.use_proxy else None) or '未设置'}")
    console.print(f"超时时间: {manager.config.timeout} 秒")
    console.print(f"重试次数: {manager.config.retry}")
    console.print(f"配置文件路径: {manager.path}")


def _detect_site_from_url(url: str) -> Website | None:
    """从URL自动检测网站类型"""
    url_lower = url.lower()

    for keyword, site in ManualConfig.WEB_DIC.items():
        if keyword.lower() in url_lower:
            return site
    return None


async def _fetch_async(
    url: str,
    website: Website | None,
    use_browser: bool,
    output_path: str | None,
    number: str | None,
    base_dir: str,
    proxy: str | None,
    timeout: int,
    retry: int,
):
    """异步获取详情页内容"""

    # 配置网络客户端
    client_proxy = proxy or (manager.config.proxy if manager.config.use_proxy else None)
    client_timeout = timeout or manager.config.timeout
    client_retry = retry or manager.config.retry

    console.print(f"[cyan]正在获取: {url}[/cyan]")
    if website:
        console.print(f"[cyan]网站类型: {website.value}[/cyan]")
    if client_proxy:
        console.print(f"[cyan]代理: {client_proxy}[/cyan]")

    # 创建异步客户端
    async_client = AsyncWebClient(
        proxy=client_proxy,
        retry=client_retry,
        timeout=client_timeout,
        log_fn=lambda msg: console.print(f"[dim][AsyncWebClient] {msg}[/dim]"),
    )

    browser_provider = BrowserProvider(manager.config)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("正在获取详情页...", total=None)
            if website:
                crawler_class = get_crawler(website)
                if crawler_class is None:
                    console.print(f"[red]错误: 未找到 {website.value} Crawler[/red]")
                    exit(1)

                crawler = crawler_class(
                    client=async_client,
                    base_url=manager.config.get_site_url(website),
                    browser=await browser_provider.get_browser() if use_browser else None,
                )
                crawler_input = CrawlerInput.empty()
                crawler_input.appoint_url = url
                progress.update(task, description="正在请求详情页...")
                # 设为 None 以根据是否传入 browser 参数决定是否使用浏览器
                html, error = await crawler._fetch_detail(crawler.new_context(crawler_input), url, None)
            elif use_browser:
                progress.update(task, description="正在通过浏览器请求详情页...")
                browser = await browser_provider.get_browser()
                try:
                    async with await browser.new_page() as page:
                        await page.goto(url, wait_until="load")
                        html = await page.content()
                        error = ""
                except Exception as e:
                    html, error = None, str(e)
            else:
                progress.update(task, description="正在请求详情页...")
                html, error = await async_client.get_text(url)

            if html is None:
                console.print(f"[red]错误: 获取详情页失败 - {error}[/red]")
                return

            progress.update(task, description="请求成功，正在保存...")

            # 确定输出路径
            output_file = _determine_output_path(output_path, url, website, number, base_dir)

            # 创建输出目录
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # 保存HTML内容
            output_file.write_text(html, encoding="utf-8")

            progress.remove_task(task)

        console.print("[green]✅ 获取成功![/green]")
        console.print(f"[green]文件已保存到: {output_file}[/green]")
        console.print(f"[dim]文件大小: {len(html)} 字符[/dim]")

    except Exception as e:
        console.print(f"[red]错误: {str(e)}[/red]")
        raise typer.Exit(1)
    finally:
        await browser_provider.close()


def _determine_output_path(
    output_path: str | None, url: str, site: Website | None, number: str | None, base_dir: str
) -> Path:
    """确定输出文件路径"""
    if output_path:
        return Path(output_path)

    # 自动生成路径
    base_path = Path(base_dir)

    # 从URL提取可能的文件名
    if number:
        filename = f"{number}.html"
    else:
        # 尝试从URL提取标识符
        url_parts = url.strip("/").split("/")
        if url_parts:
            identifier = url_parts[-1]
            # 清理文件名
            identifier = identifier.replace("=", "_").replace("?", "_").replace("&", "_")
            filename = f"{identifier}.html"
        else:
            filename = "detail.html"

    if site:
        return base_path / site.value / filename
    return base_path / filename


if __name__ == "__main__":
    app()
