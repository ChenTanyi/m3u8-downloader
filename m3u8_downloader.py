#!/usr/bin/env python

import gevent.monkey

gevent.monkey.patch_all()

import os
import sys
import re
import gevent
import gevent.pool
import requests
import m3u8
import shlex
import logging
import argparse
import urllib.parse
import json
import urllib3


class M3U8Downloader:

    def __init__(self, config, pool_size = 8, retry = 3):
        self._config = config
        self.set_pool(pool_size, retry)

        self._ssl = self._config.get('ssl', True)
        if self._ssl == False:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self._proxy = self._config.get('proxy')
        if self._proxy:
            self._session.proxies = {
                'http': self._proxy,
                'https': self._proxy,
            }

        self._output_dir = self._config.get('output_dir', '')
        self._timeout = float(self._config.get('timeout', 20))
        self._headers = {k.lower().strip(): v.strip() for k, v in self._config.get('headers', {}).items()}
        self._uri = self._config.get('uri', None)

        curlFile = self._config.get('fromCurl')
        if curlFile and os.path.isfile(curlFile):
            with open(curlFile, 'r') as fin:
                command = fin.read()
                if command:
                    self._parse_curl(command)

    def set_pool(self, pool_size, retry = None):
        self._pool_size = pool_size
        self._pool = gevent.pool.Pool(self._pool_size)
        self._session = self._get_http_session(self._pool_size, retry)

    def run(self, uri = None):
        if not uri:
            uri = self._uri
            if not uri:
                raise ValueError('Uri should not be empty.')

        if not self._output_dir:
            raise ValueError('Output Dir should not be empty.')
        if os.path.isfile(self._output_dir):
            raise ValueError('File {0} has already existed.'.format(
                self._output_dir))
        os.makedirs(self._output_dir, exist_ok = True)

        self._m3u8_content = self._download_m3u8(uri, self._timeout,
                                                 self._headers)
        assert (self._m3u8_content.is_variant is False)

        self._failed = []
        self._pool.map(self._download_ts, self._m3u8_content.segments)
        self._pool.map(self._download_extra, [*self._m3u8_content.keys, *self._m3u8_content.segment_map])

        input_file = self._dump_m3u8(uri)
        if self._failed:
            logging.error(
                '[Run Finish] Some files fail to download. Please check the configure and run again.'
            )
            return
        else:
            logging.info('[Finish Download]')

        self._remove_png_header()
        if self._config.get('concat', True):
            output_file = self._config.get('output_file', None)
            if not output_file:
                logging.error('[Concat] Can\'t get output file name')
                logging.error(
                    '[Help] "cancat_file" should be set if "concat" is True or default'
                )
                logging.error(
                    '[Help] "cancat_file" is relative to "output_dir"')
                return
            output_file = os.path.abspath(
                os.path.join(self._output_dir, output_file))
            self.concat_with_ffmpeg(input_file, output_file)

    def concat_with_ffmpeg(self, input_file, output_file):
        ffmpeg_path = self._config.get('ffmpeg_path', 'ffmpeg')
        ffmpeg_loglevel = self._config.get('ffmpeg_loglevel', 'warning')
        ffmpeg_cmd = '{0} -allowed_extensions ALL -y -loglevel {1} -f hls -i {2} -c copy {3}'.format(
            ffmpeg_path, ffmpeg_loglevel, input_file, output_file)
        logging.info('[concat cmd] {0}'.format(ffmpeg_cmd))
        os.system(ffmpeg_cmd)

    def _dump_m3u8(self, uri):
        for index, segment in enumerate(self._m3u8_content.segments):
            self._m3u8_content.segments[index].uri = self._get_filename(
                segment.uri, self._output_dir)
            if self._m3u8_content.segments[index].init_section:
                self._m3u8_content.segments[index].init_section.uri = self._get_filename(
                    segment.init_section.uri, self._output_dir).replace('\\', '/')

        for key in self._m3u8_content.keys:
            if key and key.absolute_uri:
                key.uri = self._get_filename(key.absolute_uri, self._output_dir
                    ).replace('\\', '/')  # ffmpeg error when using \\ in windows

        filename = self._get_filename(uri, self._output_dir)
        self._m3u8_content.dump(filename)
        return filename

    def _download_m3u8(self, uri, timeout, headers):
        if self._is_url(uri):
            resp = self._session.get(
                uri, timeout = timeout, headers = headers, verify = self._ssl)
            resp.raise_for_status()
            raw_content = resp.content.decode(resp.encoding or 'utf-8')
            base_uri = urllib.parse.urljoin(uri, '.')
        else:
            with open(uri) as fin:
                raw_content = fin.read()
                base_uri = os.path.dirname(uri)
        base_uri = self._config.get('base_uri') or base_uri
        content = m3u8.M3U8(raw_content, base_uri = base_uri)

        if content.is_variant:
            print(
                '\nThere are various m3u8 files. Please select one of them.\n')
            for index, playlist in enumerate(content.playlists):
                self._print_stream_info(index, playlist)

            while True:
                try:
                    if len(content.playlists) == 1:
                        chosen_idx = 0
                    else:
                        chosen_idx = int(input('INDEX > '))
                    chosen_uri = content.playlists[chosen_idx].uri
                    if not self._is_url(chosen_uri):
                        chosen_uri = urllib.parse.urljoin(
                            content.base_uri, chosen_uri)
                    return self._download_m3u8(chosen_uri, timeout, headers)

                except (ValueError, IndexError):
                    print('Invalid Index! Try Again.')

        return content

    def _download_extra(self, item):
        if item and item.absolute_uri:
            uri = item.absolute_uri
            filename = self._get_filename(uri, self._output_dir)

            with self._session.get(
                    uri,
                    timeout = self._timeout,
                    headers = self._headers,
                    verify = self._ssl) as response:
                response.raise_for_status()
                with open(filename, 'wb') as fout:
                    fout.write(response.content)

    def _download_ts(self, m3u8_segments):
        uri = urllib.parse.urljoin(m3u8_segments.base_uri, m3u8_segments.uri)
        if not self._is_url(uri):
            logging.error('[Not Uri] {0} Skip.'.format(uri))
            self._failed.append(uri)
            return

        filename = self._get_filename(uri, self._output_dir)
        headers = self._headers
        stream = self._config.get('continue', False)

        if not stream and os.path.exists(filename):
            logging.info('[Exists file] {0} Skip.'.format(filename))
            return

        if stream:
            self._add_range_header(headers = headers, filename = filename)

        try:
            with self._session.get(
                    uri,
                    timeout = self._timeout,
                    headers = headers,
                    verify = self._ssl,
                    stream = stream) as response:

                if response.status_code == 416:
                    return

                response.raise_for_status()

                if stream and response.status_code != 206:
                    logging.debug('[Debug] Server do not support Range')
                    if os.path.exists(filename):
                        os.remove(filename)

                filesize = 0
                if os.path.exists(filename):
                    filesize = os.stat(filename).st_size

                filesize += int(response.headers.get('Content-Length', 0))
                if filesize < self._config.get('ignore_small_file_size', 10240):
                    logging.error(f'[File too small] {uri}, size {filesize}')
                    logging.info(
                        '[Help] If you want to download small files, set "ignore_small_file_size" to 0'
                    )

                if stream:
                    for chunk in response.iter_content(chunk_size = 4096):
                        with open(filename, 'ab') as fout:
                            fout.write(chunk)
                else:
                    with open(filename, 'wb') as fout:
                        fout.write(response.content)
        except Exception as e:
            logging.error(f'[Download Failed] {uri}, error: {e}')
            self._failed.append(uri)

    def _remove_png_header(self):
        for segment in self._m3u8_content.segments:
            filename = segment.uri
            with open(filename, 'rb') as fin:
                content = fin.read()
            # http://www.libpng.org/pub/png/spec/1.2/PNG-Rationale.html#R.PNG-file-signature
            if content.startswith(b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a'):
                with open(filename, 'wb') as fout:
                    fout.write(content[8:])

    def _add_range_header(self, headers = {}, filename = None):
        if not (filename and os.path.isfile(filename)):
            return

        filesize = os.stat(filename).st_size
        headers['Range'] = f'bytes={filesize}-'

    @staticmethod
    def _print_stream_info(index, playlist):
        print('INDEX: ' + str(index))
        stream_info = playlist.stream_info
        if stream_info.bandwidth:
            print('\tBandwidth: {0}'.format(stream_info.bandwidth))
        if stream_info.average_bandwidth:
            print('\tAverage bandwidth: {0}'.format(
                stream_info.average_bandwidth))
        if stream_info.program_id:
            print('\tProgram ID: {0}'.format(stream_info.program_id))
        if stream_info.resolution:
            print('\tResolution: {0}'.format(stream_info.resolution))
        if stream_info.codecs:
            print('\tCodecs: {0}'.format(stream_info.codecs))
        print()

    @staticmethod
    def _get_http_session(pool_size, retry):
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_size, pool_size, retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    @staticmethod
    def _is_url(uri):
        return re.match(r'https?://', uri) is not None

    @staticmethod
    def _get_filename(uri, dir):
        basename = urllib.parse.urlparse(uri).path.split('/')[-1]
        filename = os.path.abspath(os.path.join(dir, basename))
        return filename

    _curl_parser = argparse.ArgumentParser()
    _curl_parser.add_argument('curl')
    _curl_parser.add_argument('url')
    _curl_parser.add_argument('-X', '--request', dest = 'method')
    _curl_parser.add_argument('-H', '--header', action = 'append')
    _curl_parser.add_argument('-d', '--data', '--data-ascii', '--data-binary', '--data-raw', '--data-urlencode', dest = 'body')
    _curl_parser.add_argument('--compressed', action='store_true')

    def _parse_curl(self, command):
        args = shlex.split(command.replace("\\\n", ""))
        parsed_args, unknown = self._curl_parser.parse_known_args(args)
        if unknown:
            logging.warning(f'[Unknown Curl Args] {unknown}')

        if parsed_args.url:
            self._uri = parsed_args.url

        if parsed_args.header:
            for header in parsed_args.header:
                if header.startswith(':'):
                    index = header[1:].find(':') + 1
                else:
                    index = header.find(':')
                key = header[:index].lower().strip()
                value = header[index + 1:].strip()
                self._headers[key] = value


if __name__ == '__main__':
    logging.basicConfig(
        level = logging.ERROR,
        format = '%(asctime)s %(levelname)-8s %(message)s',
        datefmt = '%Y-%m-%d %H:%M:%S')
    config_file = open('config.json', 'r')
    config = json.load(config_file)
    x = M3U8Downloader(config, 16)
    x.run()
