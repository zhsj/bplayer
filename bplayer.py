#!/usr/bin/env python3

import argparse
import io
import json
import logging
import os
import time
import urllib.request
import urllib.parse
import re
import shlex
import subprocess
import sys
import tempfile
from http import cookiejar, cookies
from os.path import abspath, join, dirname, realpath

sys.path.extend(
    [
        abspath(join(dirname(realpath(__file__)), "third_party", "danmaku2ass")),
        abspath(join(dirname(realpath(__file__)), "third_party", "you-get", "src")),
    ]
)


from danmaku2ass import Danmaku2ASS
from you_get.extractors import Bilibili, AcFun
from you_get import common


UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"


def get_cookie(name):
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), name + ".cookie")
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception as e:
        logging.debug("read cookie %s", e)
        return ""


def play_bilibili(url):
    cookie = get_cookie("bilibili")
    if cookie:
        c = cookies.SimpleCookie()
        c.load(cookie)
        common.cookies = cookiejar.MozillaCookieJar()
        for k, v in c.items():
            common.cookies.set_cookie(
                cookiejar.Cookie(
                    0,
                    k,
                    v.value,
                    None,
                    False,
                    "",
                    False,
                    False,
                    "",
                    False,
                    False,
                    False,
                    False,
                    None,
                    None,
                    {},
                )
            )

    downloader = Bilibili()
    downloader.url = url
    downloader.extract()
    while True:
        try:
            downloader.prepare()
            break
        except Exception as e:
            logging.debug(e, exc_info=True)
            time.sleep(1)

    headers = "Referer:{0},User-Agent:{1}".format(
        downloader.referer, downloader.ua.replace(",", "\,")
    )

    mpv = [
        "mpv",
        "--http-header-fields=" + headers,
        "--force-media-title=" + downloader.title,
    ]

    danmaku_file = tempfile.NamedTemporaryFile()
    danmaku = io.StringIO(downloader.danmaku)
    Danmaku2ASS(
        [danmaku],
        "autodetect",
        danmaku_file.name,
        1920,
        1080,
        reserve_blank=100,
        font_size=50,
        text_opacity=0.6,
        duration_marquee=20,
        is_reduce_comments=True,
    )

    mpv.append("--sub-file=" + danmaku_file.name)

    if hasattr(downloader, "subtitle"):

        def sec2time(sec):
            h = int(sec) // 3600
            m = int(sec) // 60 % 60
            s = sec % 60
            f = int(sec * 1000) % 1000
            return "%02d:%02d:%02d,%03d" % (h, m, int(s), f)

        sub_file = tempfile.NamedTemporaryFile()
        with open(sub_file.name, "w") as f:
            for idx, item in enumerate(json.loads(downloader.subtitle)["body"]):
                f.write(
                    "%d\n%s --> %s\n%s\n\n"
                    % (
                        idx + 1,
                        sec2time(item["from"]),
                        sec2time(item["to"]),
                        item["content"],
                    )
                )
        mpv.append("--sub-file=" + sub_file.name)
        mpv.append("--secondary-sid=2")

    quality = {v["id"]: v["quality"] for v in downloader.stream_qualities.values()}

    def replace_hk(url):
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc.startswith("cn-hk"):
            return parsed._replace(netloc="upos-sz-mirrorali.bilivideo.com").geturl()
        else:
            return url

    if downloader.streams:
        stream = downloader.streams[
            sorted(
                downloader.streams.keys(),
                key=lambda k: quality.get(k.replace("dash-", ""), 0),
            )[-1]
        ]
        logging.debug("stream quality %s", stream["quality"])
        src = stream["src"]
        mpv.append(replace_hk(src[0]))
    elif downloader.dash_streams:
        stream = downloader.dash_streams[
            sorted(
                downloader.dash_streams.keys(),
                key=lambda k: quality.get(k.replace("dash-", ""), 0),
            )[-1]
        ]
        logging.debug("stream quality %s", stream["quality"])
        src = stream["src"]
        mpv.append("--audio-file=" + replace_hk(src[1][0]))
        mpv.append(replace_hk(src[0][0]))

    logging.debug(shlex.join(mpv))
    subprocess.call(
        mpv,
        env={
            k: v
            for k, v in os.environ.items()
            if k not in ["http_proxy", "https_proxy"]
        },
    )


def play_acfun(url):
    downloader = AcFun()
    downloader.url = url
    downloader.prepare()
    for stream_type in downloader.stream_types:
        if stream_type["id"] in downloader.streams:
            mpv = [
                "mpv",
                "--force-media-title=" + downloader.title,
                downloader.streams[stream_type["id"]]["src"],
            ]
            logging.debug(shlex.join(mpv))
            subprocess.call(mpv)
            return


def play_weibo(url):
    cookie = get_cookie("bilibili")
    match = re.match(r"https://video.weibo.com/show\?fid=(\d{4}:\w+)", url)
    if match is None:
        return
    fid = match[1]
    req = urllib.request.Request(
        "https://weibo.com/tv/api/component?page=/tv/show/" + fid,
        method="POST",
        headers={"referer": "https://weibo.com/tv/show/" + fid, "cookie": cookie},
        data=("data=" + json.dumps({"Component_Play_Playinfo": {"oid": fid}})).encode(),
    )
    resp = urllib.request.urlopen(req)
    r = json.loads(resp.read())
    title = r["data"]["Component_Play_Playinfo"]["title"]
    urls = r["data"]["Component_Play_Playinfo"]["urls"]
    url = (
        "https:"
        + sorted(
            urls.items(), key=lambda x: int(re.findall("(\d+)", x[0])[0]), reverse=True
        )[0][1]
    )
    mpv = [
        "mpv",
        "--force-media-title=" + title,
        url,
    ]
    logging.debug(shlex.join(mpv))
    subprocess.call(mpv)


def play_weibo_live(url):
    cookie = get_cookie("bilibili")
    match = re.match(r"https://weibo.com/l/wblive/p/show/(\d{4}:\w+)", url)
    if match is None:
        return
    live_id = match[1]
    req = urllib.request.Request(
        "https://weibo.com/l/!/2/wblive/room/show_pc_live.json?live_id=" + live_id,
        method="GET",
        headers={"referer": url, "cookie": cookie},
    )
    resp = urllib.request.urlopen(req)
    r = json.loads(resp.read())
    title = r["data"]["title"]
    url = r["data"]["live_origin_hls_url"]
    if not url:
        url = r["data"]["replay_origin_url"]
    mpv = [
        "mpv",
        "--force-media-title=" + title,
        url,
    ]
    logging.debug(shlex.join(mpv))
    subprocess.call(mpv)


def play_anime1(url):
    cookie = get_cookie("anime1")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Cookie": cookie,
        },
    )
    logging.debug(req.__dict__)
    resp = urllib.request.urlopen(req).read().decode()
    title = re.findall(r'<meta property="og:title" content="([^"]+)">', resp)[0]
    apireq = re.findall(r'data-apireq="([^"]+)"', resp)[0]
    req = urllib.request.Request(
        "https://v.anime1.me/api",
        headers={"User-Agent": UA},
        data=b"d=" + apireq.encode(),
        method="POST",
    )
    logging.debug(req.__dict__)
    resp = urllib.request.urlopen(req)
    info = resp.read()
    logging.debug(info)
    resp = urllib.request.urlopen(req)
    m3u8 = "https:" + json.loads(info)["s"][0]["src"]
    c = cookies.SimpleCookie()
    for i in resp.headers.get_all("set-cookie"):
        c.load(i)
    cookie = c.output(header="", attrs=[], sep=";").strip()
    headers = "Cookie:{0},User-Agent:{1}".format(cookie, UA.replace(",", "\,"))
    mpv = [
        "mpv",
        "--http-header-fields=" + headers,
        "--force-media-title=" + title,
        m3u8,
    ]
    logging.debug(shlex.join(mpv))
    subprocess.call(mpv)


def main():
    def convert_short_url(url):
        class noRedirect(urllib.request.HTTPRedirectHandler):
            def http_error_302(self, req, fp, code, msg, headers):
                return headers

        if url.startswith("http://t.cn"):
            headers = urllib.request.build_opener(noRedirect).open(url)
            return headers.get("Location")

        return url

    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()
    logging.getLogger().setLevel(logging.DEBUG)
    url = convert_short_url(args.url)
    if re.match(r"https?://www.bilibili.com", url):
        play_bilibili(url)
    elif url.startswith("https://www.acfun.cn"):
        play_acfun(url)
    elif url.startswith("https://video.weibo.com"):
        play_weibo(url)
    elif url.startswith("https://weibo.com/l/wblive"):
        play_weibo_live(url)
    elif url.startswith("https://anime1.me/"):
        play_anime1(url)


if __name__ == "__main__":
    main()

# vim: et:ts=4:sts=4:sw=4
