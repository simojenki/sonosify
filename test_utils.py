import pytest
import subprocess
import json
import os
import hashlib
import re
from uuid import uuid4 as uuid

DEFAULT_IMAGE="deluan/navidrome:latest"

def docker(
    image=DEFAULT_IMAGE,
    docker_opts="",
    entrypoint="", 
    args=""
):
    return run("""docker run \
        --rm \
        {docker_opts} \
        -u {uid}:{gid} \
        --entrypoint {entrypoint} \
        {image} \
            {args}""".format(
                docker_opts=docker_opts,
                uid=os.getuid(),
                gid=os.getgid(),
                image=image,
                entrypoint=entrypoint,
                args=args
            )
        )


def run(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=False)
    if result.returncode == 0:     
        return result.stdout.decode('utf-8')
    else:
        print("Ran:{}".format(cmd))
        print(result.stdout.decode('utf-8'))
        print(result.stderr.decode('utf-8'))
        raise Exception("Failed running command!")


class AudioFile:
    def __init__(self, path):
        assert path.check()
        self.path = path


    def stream_md5(self):
        out = docker(
            docker_opts="-v {sounds}:/sounds".format(sounds=self.path.dirname),
            entrypoint="ffmpeg",
            args="""-i /sounds/{i} \
                -f hash \
                -hash md5 \
                -""".format(
                    i=self.path.basename
                )
            )
        if not bool(re.compile(r'MD5=\w+').match(out)):
            raise Exception("Expected md5 for stream, got '{}'".format(out))
        return out.strip()


    def tags(self):
        out = docker(
            docker_opts="-v {sounds}:/sounds".format(sounds=self.path.dirname),
            entrypoint="ffprobe",
            args="""-show_format \
                    -print_format json \
                    /sounds/{i}""".format(
                        i=self.path.basename
                    )
            )
        return json.loads(out)["format"]["tags"]


    def stream0(self):
        out = docker(
            docker_opts="-v {sounds}:/sounds".format(sounds=self.path.dirname),
            entrypoint="ffprobe",
            args="""-select_streams 0 \
                    -show_streams \
                    -print_format json \
                    /sounds/{i}""".format(
                        i=self.path.basename
                    )
            )
        return json.loads(out)["streams"][0]

    
    def to_mp3(self):
        new_file_name = "{uuid}{ext}".format(uuid = uuid(), ext = ".mp3")
        docker(
            docker_opts="-v {sounds}:/sounds".format(sounds=self.path.dirname),
            entrypoint="ffmpeg",
            args="""-i /sounds/{i} \
                -ar 44100 \
                -ac 2 \
                -b:a 192k \
                /sounds/{o}""".format(
                    i=self.path.basename, 
                    o=new_file_name
                )
        )
        return AudioFile(self.path.dirpath(new_file_name)) 


    def to_flac(self, sample_fmt="s16", sample_rate="44100"):
        new_file_name = "{uuid}{ext}".format(uuid=uuid(), ext=".flac")
        docker(
            docker_opts="-v {sounds}:/sounds".format(sounds=self.path.dirname),
            entrypoint="ffmpeg",
            args="""-i /sounds/{i} \
                -af 'aresample=resampler=soxr:out_sample_fmt={sample_fmt}:out_sample_rate={sample_rate}' \
                -f flac \
                /sounds/{o}""".format(
                    i=self.path.basename, 
                    sample_fmt=sample_fmt,
                    sample_rate=sample_rate,
                    o=new_file_name
                )
        )
        return AudioFile(self.path.dirpath(new_file_name)) 


    def to_alac(self):
        # docker run -it -v "/tmp:/tmp" linuxserver/ffmpeg:latest -i "/tmp/01.flac" -vn -acodec alac -map_metadata -1 /tmp/01.m4a
        new_file_name = "{uuid}{ext}".format(uuid=uuid(), ext=".m4a")
        docker(
            image="linuxserver/ffmpeg:latest",
            docker_opts="-v {sounds}:/sounds".format(sounds=self.path.dirname),
            entrypoint="ffmpeg",
            args="""-i /sounds/{i} \
                -vn \
                -acodec alac \
                /sounds/{o}""".format(
                    i=self.path.basename, 
                    o=new_file_name
                )
        )
        return AudioFile(self.path.dirpath(new_file_name)) 


    def to_aac(self):
        new_file_name = "{uuid}{ext}".format(uuid=uuid(), ext=".m4a")
        docker(
            image="linuxserver/ffmpeg:latest",
            docker_opts="-v {sounds}:/sounds".format(sounds=self.path.dirname),
            entrypoint="ffmpeg",
            args="""-i /sounds/{i} \
                -c:a aac \
                /sounds/{o}""".format(
                    i=self.path.basename, 
                    o=new_file_name
                )
        )
        return AudioFile(self.path.dirpath(new_file_name)) 


    def with_tags(self, artist="some-artist", title="some-title", genre="some-genre", album="some-album"):
        new_file_name = "{name}{ext}".format(name = uuid(), ext = self.path.ext)
        docker(
            docker_opts="-v {sounds}:/sounds".format(sounds=self.path.dirname),
            entrypoint="ffmpeg",
            args="""-i /sounds/{i} \
                -map 0 \
                -codec copy \
                -write_id3v2 1 \
                -metadata "artist={artist}" \
                -metadata "title={title}" \
                -metadata "genre={genre}" \
                -metadata "album={album}" \
                /sounds/{o}""".format(
                    i=self.path.basename,
                    artist=artist,
                    title=title,
                    genre=genre,
                    album=album,
                    o=new_file_name
                )
        )
        return AudioFile(self.path.dirpath(new_file_name)) 
