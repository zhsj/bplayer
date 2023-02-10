#!/usr/bin/env python3

import urllib.request
import re
import logging
import os.path

VPX = "15"
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
    playlist = re.findall(r'"https://v.myself-bbs.com/player/([^"]+)"', data)
    playlist_name = re.findall(r'<a href="javascript:;">(.*)</a>', data)

    logging.debug("playlist %s", playlist)
    logging.debug("playlist_name %s", playlist_name)

    if idx.count(":") == 0:
        playlist = [playlist[int(idx)]]
        playlist_name = [playlist_name[int(idx)]]
    elif idx.count(":") == 1:
        start, end = [int(i) if i.isdigit() else None for i in idx.split(":")]
        playlist = playlist[start:end]
        playlist_name = playlist_name[start:end]

    result = []

    for i in range(0, len(playlist)):
        play_title = playlist_name[i] + " | " + title

        if not playlist[i].startswith("play/"):
            name = playlist[i].strip()
            m3u8 = "https://vpx%s.myself-bbs.com/hls/%s/%s/%s/%s/index.m3u8" % (
                VPX,
                name[4:6],
                name[6:8],
                name[8:10],
                name,
            )
            result.append((play_title, m3u8))
            continue

        req = urllib.request.Request(
            "https://v.myself-bbs.com/player/" + playlist[i],
            headers={
                "referer": "https://myself-bbs.com",
                "User-Agent": UA,
                "Cookie": cookie,
            },
        )
        logging.debug("opening %s", req.full_url)
        data = urllib.request.urlopen(req).read().decode().replace(" ", "")
        tid = re.findall(r'tid\s*=\s*"(\d+)";', data)[0]
        vid = re.findall(r'vid\s*=\s*"(\d+)";', data)[0]
        ver = re.findall(r'[^tv]id\s*=\s*"(\d*)";', data)[0]
        logging.debug("tid=%s, vid=%s, ver=%s", tid, vid, ver)

        if ver == "" or ver == "0":
            m3u8 = "https://vpx%s.myself-bbs.com/vpx/%s/%s/720p.m3u8" % (VPX, tid, vid)
        else:
            m3u8 = "https://vpx%s.myself-bbs.com/vpx/%s/%s_v%s/720p.m3u8" % (
                VPX,
                tid,
                vid,
                ver,
            )

        result.append((play_title, m3u8))
    return result


if __name__ == "__main__":
    import argparse
    import shlex
    import subprocess

    logging.getLogger().setLevel(logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("idx", nargs="?", default="-1")
    parser.add_argument("-d", "--dry-run", action="store_true")
    args = parser.parse_args()
    logging.debug("args %s", args)
    result = get_info(args.url, args.idx)
    headers = "Referer:{0},User-Agent:{1}".format(
        "https://v.myself-bbs.com", UA.replace(",", "\,")
    )

    for title, m3u8 in result:
        mpv = [
            "mpv",
            "--http-header-fields=" + headers,
            "--force-media-title=" + title,
            m3u8,
        ]
        logging.debug("calling %s", shlex.join(mpv))
        if not args.dry_run:
            subprocess.call(mpv)
