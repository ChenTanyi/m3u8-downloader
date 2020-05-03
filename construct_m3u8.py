#!/usr/bin/env python3
import os
import sys
import argparse
import urllib.parse
import logging


def main(url, file_format, length):
    if not url:
        url = open('url.txt').read().strip()

    uri = urllib.parse.urlparse(url)
    uri = uri._replace(path = uri.path[:uri.path.rfind('/') + 1])

    url = urllib.parse.urlunparse(uri)

    with open('test.m3u8', 'w') as fout:
        fout.write('''#EXTM3U
#EXT-X-MEDIA-SEQUENCE:1
#EXT-X-ALLOW-CACHE:YES
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXT-X-PLAYLIST-TYPE:VOD\n''')
        for i in range(1, length):
            fout.write('#EXTINF:10,\n')
            fout.write(url + file_format.format(i) + '\n')
        fout.write('#EXT-X-ENDLIST\n')


if __name__ == "__main__":
    logging.basicConfig(
        level = logging.ERROR, format = '%(asctime)s %(levelname)s %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--url')
    parser.add_argument(
        '-f', '--format', default = 'seg-{}-v1-a1.ts', help = 'ts files format')
    parser.add_argument('length', nargs = 1, type = int)
    args = parser.parse_args()

    if not args.length:
        logging.error('need input length for ts files')
        sys.exit(1)

    main(args.url, args.format, args.length[0])