import os
import re
import sys
import m3u8
import logging
import subprocess

def is_url(uri):
    return re.match(r'https?://', uri) is not None

def get_duration(filename):
    ffprobe_process = subprocess.Popen(["ffprobe", filename],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ffprobe_output = ffprobe_process.stdout.readlines()
    duration_line = [x for x in ffprobe_output if 'Duration' in x.decode('utf-8')]
    assert(len(duration_line) > 0)
    duration = duration_line[0].decode('utf-8').split(',')[0].split('Duration:')[1].strip()
    hour, min, second = list(map(float, duration.split(':')))
    return hour * 3600 + min * 60 + second

def check_video(filename, remove):
    m3u8_stream = m3u8.load(filename)
    wrong_files = []
    for seg in m3u8_stream.segments:
        if is_url(seg.base_uri) or is_url(seg.uri):
            logging.error('[Segments] Must be downloaded first')
            return None

        ts_filename = os.path.join(seg.base_uri, seg.uri)
        duration = get_duration(ts_filename)
        if duration - seg.duration < - 0.2:
            wrong_files.append(ts_filename)
            logging.info('File {0} with expected duration {1} but get {2}'.format(ts_filename, seg.duration, duration))
            if remove:
                os.remove(ts_filename)
    logging.info(len(wrong_files))
    return wrong_files

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

    if len(sys.argv) > 1:
        check_video(sys.argv[1], False)
    else:
        print('Error! try: \npython check_video.py [m3u8 file name]', file=sys.stderr)
