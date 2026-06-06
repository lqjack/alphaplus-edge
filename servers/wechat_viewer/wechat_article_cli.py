import click
import itchat
from itchat.content import TEXT
import time
import requests
from typing import Dict, List, Optional

# 全局变量：存储微信登录状态和公众号缓存
WECHAT_LOGGED_IN = False
OFFICIAL_ACCOUNTS_CACHE: Dict[str, str] = {}  # 公众号名称: 公众号ID


def login_wechat(hot_reload: bool = True) -> bool:
    """
    微信扫码登录，初始化itchat
    :param hot_reload: 热重载，避免重复扫码
    :return: 登录是否成功
    """
    global WECHAT_LOGGED_IN
    if WECHAT_LOGGED_IN:
        return True

    try:
        itchat.auto_login(
            hotReload=hot_reload,
            qrCallback=show_qr_code,
            exitCallback=lambda: setattr(globals(), "WECHAT_LOGGED_IN", False)
        )
        WECHAT_LOGGED_IN = True
        # 缓存公众号列表（名称->ID）
        load_official_accounts()
        return True
    except Exception as e:
        click.echo(f"微信登录失败: {str(e)}")
        return False


def show_qr_code(uuid: str, status: int) -> None:
    """
    生成并显示微信登录二维码
    :param uuid: 登录UUID
    :param status: 二维码状态（0: 新二维码, 1: 已扫码, 2: 已登录, 3: 登录失败）
    """
    if status == 0:
        qr_code = pyqrcode.create(f"https://login.weixin.qq.com/l/{uuid}")
        click.echo("请扫描以下二维码登录微信：")
        print(qr_code.terminal(module_color='red', background='white'))
    elif status == 1:
        click.echo("已扫码，请在手机上确认登录...")
    elif status == 2:
        click.echo("微信登录成功！")
    elif status == 3:
        click.echo("微信登录失败，请重新扫码！")


def load_official_accounts() -> None:
    """加载已关注的公众号列表，缓存名称和ID映射"""
    global OFFICIAL_ACCOUNTS_CACHE
    if not WECHAT_LOGGED_IN:
        click.echo("未登录微信，无法加载公众号列表")
        return

    try:
        # 获取公众号列表（itchat.get_mps()）
        mp_list = itchat.get_mps(update=True)
        OFFICIAL_ACCOUNTS_CACHE = {mp['NickName']: mp['UserName'] for mp in mp_list}
        click.echo(f"已加载 {len(OFFICIAL_ACCOUNTS_CACHE)} 个已关注的公众号")
    except Exception as e:
        click.echo(f"加载公众号列表失败: {str(e)}")


def get_latest_article_by_mp_name(mp_name: str) -> Optional[Dict[str, str]]:
    """
    根据公众号名称获取最新一篇文章的标题和链接
    :param mp_name: 公众号名称（模糊匹配）
    :return: {"title": 标题, "link": 链接} 或 None
    """
    if not WECHAT_LOGGED_IN:
        click.echo("未登录微信，请先登录")
        return None

    # 模糊匹配公众号名称
    matched_mp = [
        (name, user_id) for name, user_id in OFFICIAL_ACCOUNTS_CACHE.items()
        if mp_name in name
    ]
    if not matched_mp:
        click.echo(f"未找到包含「{mp_name}」的公众号")
        return None
    if len(matched_mp) > 1:
        click.echo(f"找到多个匹配的公众号：{[name for name, _ in matched_mp]}，默认取第一个")
    target_mp_name, target_mp_id = matched_mp[0]

    try:
        # 获取公众号最新文章列表
        mp_articles = itchat.get_msg(userName=target_mp_id, update=True)
        if not mp_articles or 'Content' not in mp_articles[-1]:
            click.echo(f"公众号「{target_mp_name}」暂无最新文章")
            return None

        # 解析最新文章（itchat返回的Content是HTML，提取文章链接和标题）
        latest_msg = mp_articles[-1]
        content = latest_msg.get('Content', '')
        # 提取文章标题和链接（适配微信文章的HTML格式）
        import re
        # 匹配微信文章的标题和链接正则
        title_pattern = re.compile(r'<h1 class="rich_media_title " id="activity-name">(.*?)</h1>', re.S)
        link_pattern = re.compile(r'<a href="(https://mp.weixin.qq.com/s\?.*?)"', re.S)

        title = title_pattern.search(content)
        link = link_pattern.search(content)

        if title and link:
            return {
                "title": title.group(1).strip(),
                "link": link.group(1).strip(),
                "mp_name": target_mp_name
            }
        else:
            click.echo(f"解析「{target_mp_name}」最新文章失败，内容格式异常")
            return None
    except Exception as e:
        click.echo(f"获取「{target_mp_name}」最新文章失败: {str(e)}")
        return None


def get_all_latest_articles() -> List[Dict[str, str]]:
    """
    获取所有已关注公众号的最新一篇文章（仅返回有文章的公众号）
    :return: [{"mp_name": 公众号名称, "title": 标题, "link": 链接}, ...]
    """
    if not WECHAT_LOGGED_IN:
        click.echo("未登录微信，请先登录")
        return []

    result = []
    # 遍历所有公众号，获取最新文章
    for mp_name, mp_id in OFFICIAL_ACCOUNTS_CACHE.items():
        try:
            mp_articles = itchat.get_msg(userName=mp_id, update=True)
            if not mp_articles or 'Content' not in mp_articles[-1]:
                continue
            content = mp_articles[-1]['Content']
            import re
            title_pattern = re.compile(r'<h1 class="rich_media_title " id="activity-name">(.*?)</h1>', re.S)
            link_pattern = re.compile(r'<a href="(https://mp.weixin.qq.com/s\?.*?)"', re.S)
            title = title_pattern.search(content)
            link = link_pattern.search(content)
            if title and link:
                result.append({
                    "mp_name": mp_name,
                    "title": title.group(1).strip(),
                    "link": link.group(1).strip()
                })
        except Exception as e:
            click.echo(f"跳过公众号「{mp_name}」：{str(e)}")
            continue
    return result


# === CLI 命令定义 ===
@click.group()
@click.option('--no-hot-reload', is_flag=True, help="禁用微信登录热重载（每次启动都需扫码）")
def cli(no_hot_reload):
    """微信公众号文章CLI工具 - 需先扫码登录微信"""
    # 初始化微信登录
    login_wechat(hot_reload=not no_hot_reload)


@cli.command(name="list-latest")
def list_latest():
    """获取所有已关注公众号的最新一篇文章（标题+链接）"""
    click.echo("开始获取所有公众号最新文章...")
    articles = get_all_latest_articles()
    if not articles:
        click.echo("无可用的公众号文章")
        return
    # 格式化输出
    click.echo("\n=== 所有公众号最新文章列表 ===")
    for idx, article in enumerate(articles, 1):
        click.echo(f"\n{idx}. 公众号：{article['mp_name']}")
        click.echo(f"   标题：{article['title']}")
        click.echo(f"   链接：{article['link']}")


@cli.command(name="get-by-name")
@click.argument("mp_name")
def get_by_name(mp_name):
    """根据公众号名称（模糊匹配）获取最新一篇文章的标题+链接"""
    click.echo(f"开始获取包含「{mp_name}」的公众号最新文章...")
    article = get_latest_article_by_mp_name(mp_name)
    if article:
        click.echo("\n=== 匹配到的最新文章 ===")
        click.echo(f"公众号：{article['mp_name']}")
        click.echo(f"标题：{article['title']}")
        click.echo(f"链接：{article['link']}")


if __name__ == "__main__":
    # 修复pyqrcode导入（避免运行时报错）
    import pyqrcode
    cli()