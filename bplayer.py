#!/usr/bin/env python3

import argparse
import io
import logging
import shlex
import subprocess
import sys
import tempfile
from os.path import abspath, join, dirname

sys.path.extend(
    [
        abspath(join(dirname(__file__), "third_party", "danmaku2ass")),
        abspath(join(dirname(__file__), "third_party", "you-get", "src")),
    ]
)


def fake_download(url, title, *args, **kwargs):
    mpv = ["mpv", "--title=" + title, url]
    logging.debug(shlex.join(mpv))
    subprocess.call(mpv)


from you_get import common

common.download_url_ffmpeg = fake_download

from you_get.extractors import Bilibili
from you_get.extractors import acfun_download
from danmaku2ass import Danmaku2ASS


def play_bilibili(url):
    downloader = Bilibili()
    downloader.url = url
    downloader.extract()
    downloader.prepare()
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
    src = downloader.dash_streams[
        sorted(
            downloader.dash_streams.keys(),
            key=lambda k: quality.get(k.replace("dash-", ""), 0),
        )[-1]
    ]["src"]
    headers = "Referer:{0},User-Agent:{1}".format(
        downloader.referer, downloader.ua.replace(",", "\,")
    )
    mpv = [
        "mpv",
        "--http-header-fields=" + headers,
        "--title=" + downloader.title,
        "--sub-file=" + sub_file.name,
        "--audio-file=" + src[1][0],
        src[0][0],
    ]
    logging.debug(shlex.join(mpv))
    subprocess.call(mpv)


def play_acfun(url):
    acfun_download(url)


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


if __name__ == "__main__":
    main()

# vim: et:ts=4:sts=4:sw=4
