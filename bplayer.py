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

from you_get.extractors import Bilibili
from danmaku2ass import Danmaku2ASS


def main(url):
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
    src = downloader.dash_streams["dash-flv"]["src"]
    headers = "Referer:{0},User-Agent:{1}".format(downloader.referer, downloader.ua)
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()
    logging.getLogger().setLevel(logging.DEBUG)
    main(args.url)

# vim: et:ts=4:sts=4:sw=4
