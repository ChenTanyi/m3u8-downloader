# M3U8 Downloader

Simple downloader

## Prerequisites

* [ffmpeg](https://www.ffmpeg.org/) (concatenate)
* pip install -r requirements.txt

## Configure

In `config.json`

#### require

* `uri`
* `output_dir`
* `output_file`(if `concat` is `true`)

#### optional with default

* `concat`: true
* `timeout`: 20
* `headers`: {}
* `ffmpeg_path`: ffmpeg
* `ffmpeg_loglevel`: warning
* `ignore_small_file_size`: 10240
* `continue`: true
* `ssl`: true
* `base_uri`: None

## Notice

* m3u8 does not support ssl now, need to add `import ssl` like https://github.com/globocom/m3u8/pull/181