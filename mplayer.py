#!/usr/bin/env python3

import urllib.request
import re
import logging
import os.path

VPX = ""
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"


def get_info(url, idx):
    cookie = ""
    try:
        with open(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "mplayer.cookie")
        ) as f:
            cookie = f.read().strip()
    except Exception as e:
        logging.debug("read cookie %s", e)
    req = urllib.request.Request(
        url,
        headers={
            "referer": "https://myself-bbs.com",
            "User-Agent": UA,
            "Cookie": cookie,
        },
    )
    logging.debug("header %s", req.headers)
    logging.debug("opening %s", req.full_url)
    data = urllib.request.urlopen(req).read().decode()
    title = re.findall(r'<meta name="keywords" content="(.*)" />', data)[0].strip()
    playlist = re.findall(r"https://v.myself-bbs.com/player/play/\d+/\d+", data)
    playlist_name = re.findall(r'<a href="javascript:;">(.*)</a>', data)
    title = playlist_name[idx] + " | " + title

    req = urllib.request.Request(
        playlist[idx],
        headers={
            "referer": "https://myself-bbs.com",
            "User-Agent": UA,
            "Cookie": cookie,
        },
    )
    logging.debug("opening %s", req.full_url)
    data = urllib.request.urlopen(req).read().decode().replace(" ", "")
    info = re.findall(r"tid='(\d*)',vid='(\d*)',ver='(\d*)'", data)
    tid, vid, ver = info[0]

    if ver == "" or ver == "0":
        m3u8 = "https://vpx%s.myself-bbs.com/%s/%s/720p.m3u8" % (VPX, tid, vid)
    else:
        m3u8 = "https://vpx%s.myself-bbs.com/%s/%s_v%s/720p.m3u8" % (VPX, tid, vid, ver)
    return (title, m3u8)


if __name__ == "__main__":
    import argparse
    import shlex
    import subprocess

    logging.getLogger().setLevel(logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("idx", type=int, nargs="?", default=-1)
    parser.add_argument("-d", "--dry-run", action="store_true")
    args = parser.parse_args()
    logging.debug("args %s", args)
    title, m3u8 = get_info(args.url, args.idx)
    mpv = [
        "mpv",
        "--user-agent=" + UA,
        "--title=" + title,
        m3u8,
    ]
    logging.debug("calling %s", shlex.join(mpv))
    if not args.dry_run:
        subprocess.call(mpv)
