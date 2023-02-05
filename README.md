# M3U8 Downloader

Simple downloader

## Prerequisites

* [ffmpeg](https://www.ffmpeg.org/) (concatenate)
* pip install -r requirements.txt

## Configure

In `config.json`

#### require

* `uri`
    > the uri of m3u8, it would be overwritten by `fromCurl`
* `output_dir`
    > the output folder to store all download file
* `output_file` (if `concat` is `true`)
    > the final concatenated file

#### optional with default

* `concat`: true
    > specify whether to concatenate the downloaded m3u8
* `timeout`: 20
    > request timeout
* `headers`: {}
    > http header, it would be overwritten by `fromCurl`
* `ffmpeg_path`: ffmpeg
    > executable file for concatenate
* `ffmpeg_loglevel`: warning
    > ffmpeg parameter
* `ignore_small_file_size`: 10240
    > ignore small file as it may meet error
* `continue`: false
    > use http range to continue download for every file, usually for big file
* `ssl`: true
    > ignore ssl error if set to false
* `base_uri`: None
    > specify when the base uri cannot get from uri
* `proxy`: None
    > specify the proxy for all request
* `fromCurl`: None
    > specify a file containing curl command (usually from DevTools), update `uri` and `headers` from curl