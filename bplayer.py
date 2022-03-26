#!/usr/bin/env python3

import argparse
import io
import json
import logging
import os
import time
import urllib.request
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


def fake_download_urls(urls, title, *args, **kwargs):
    mpv = ["mpv", "--title=" + title, urls[0]]
    logging.debug(shlex.join(mpv))
    subprocess.call(mpv)


from you_get import common

common.download_urls = fake_download_urls

from you_get.extractors import Bilibili, AcFun, miaopai_download
from danmaku2ass import Danmaku2ASS


def play_bilibili(url):
    try:
        with open(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "bilibili.cookie")
        ) as f:
            c = cookies.SimpleCookie()
            c.load(f.read())
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
    except Exception as e:
        logging.debug("read cookie %s", e)

    downloader = Bilibili()
    downloader.stream_types.append(
        {
            "id": "hdflv2_8k",
            "quality": 127,
            "audio_quality": 30280,
            "container": "FLV",
            "video_resolution": "4320p",
            "desc": "8K 超高清",
        },
    )
    downloader.url = url
    downloader.extract()
    while True:
        try:
            downloader.prepare()
            break
        except Exception as e:
            logging.debug(e, exc_info=True)
            time.sleep(1)
    danmaku = io.StringIO(downloader.danmaku)
    sub_file = tempfile.NamedTemporaryFile()
    Danmaku2ASS(
        [danmaku],
        "autodetect",
        sub_file.name,
        1920,
        1080,
        reserve_blank=100,
        font_size=50,
        text_opacity=0.6,
        duration_marquee=20,
        is_reduce_comments=True,
    )
    quality = {v["id"]: v["quality"] for v in downloader.stream_qualities.values()}

    headers = "Referer:{0},User-Agent:{1}".format(
        downloader.referer, downloader.ua.replace(",", "\,")
    )

    if downloader.dash_streams:
        src = downloader.dash_streams[
            sorted(
                downloader.dash_streams.keys(),
                key=lambda k: quality.get(k.replace("dash-", ""), 0),
            )[-1]
        ]["src"]
        mpv = [
            "mpv",
            "--http-header-fields=" + headers,
            "--title=" + downloader.title,
            "--sub-file=" + sub_file.name,
            "--audio-file=" + src[1][0],
            src[0][0],
        ]
    if downloader.streams:
        src = downloader.streams[
            sorted(
                downloader.streams.keys(),
                key=lambda k: quality.get(k.replace("dash-", ""), 0),
            )[-1]
        ]["src"]
        mpv = [
            "mpv",
            "--http-header-fields=" + headers,
            "--title=" + downloader.title,
            "--sub-file=" + sub_file.name,
            src[0],
        ]
    logging.debug(shlex.join(mpv))
    subprocess.call(mpv)


def play_acfun(url):
    downloader = AcFun()
    downloader.url = url
    downloader.prepare()
    for stream_type in downloader.stream_types:
        if stream_type["id"] in downloader.streams:
            mpv = [
                "mpv",
                "--title=" + downloader.title,
                downloader.streams[stream_type["id"]]["src"],
            ]
            logging.debug(shlex.join(mpv))
            subprocess.call(mpv)
            return


def play_weibo(url):
    cookie = ""
    try:
        with open(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "weibo.cookie")
        ) as f:
            cookie = f.read().strip()
    except Exception as e:
        logging.debug("read cookie %s", e)

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
        "--title=" + title,
        url,
    ]
    logging.debug(shlex.join(mpv))
    subprocess.call(mpv)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()
    logging.getLogger().setLevel(logging.DEBUG)
    url = args.url
    if url.startswith("https://www.bilibili.com"):
        play_bilibili(url)
    elif url.startswith("https://www.acfun.cn"):
        play_acfun(url)
    elif url.startswith("https://video.weibo.com"):
        play_weibo(url)


if __name__ == "__main__":
    main()

# vim: et:ts=4:sts=4:sw=4
