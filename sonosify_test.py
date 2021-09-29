import pytest
import subprocess
import json
import os
import hashlib
import re
from uuid import uuid4 as uuid

SONOSIFY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sonosify')
JSON_SH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'JSON.sh')
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

  
    def with_tags(self, artist="some-artist", title="some-title", track="some-track", album="some-album"):
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
                -metadata "track={track}" \
                -metadata "album={album}" \
                /sounds/{o}""".format(
                    i=self.path.basename,
                    artist=artist,
                    title=title,
                    track=track,
                    album=album,
                    o=new_file_name
                )
        )
        return AudioFile(self.path.dirpath(new_file_name)) 


def run(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=False)
    if result.returncode == 0:     
        return result.stdout.decode('utf-8')
    else:
        print("Ran:{}".format(cmd))
        print(result.stderr.decode('utf-8'))
        raise Exception("Failed running command!")


@pytest.fixture(scope="session")
def tmp_sounds(tmpdir_factory):
    return tmpdir_factory.mktemp("sounds")


@pytest.fixture(scope="session")
def wav(tmp_sounds):
    filename = "sound.wav"
    docker(
        docker_opts="-v {sounds}:/sounds".format(sounds=tmp_sounds),
        entrypoint="ffmpeg",
        args="""-f lavfi \
            -i 'sine=frequency=1000:duration=1' \
            -ac 2 \
            /sounds/{o}""".format(
                o=filename
            )
    )
    return AudioFile(tmp_sounds.join(filename))


def sonosify(i):
    new_file_name = "{name}{ext}".format(name = uuid(), ext = i.path.ext)
    run("""docker run \
        --rm \
        -v {sounds}:/sounds \
        -v {sonosify}:/bin/sonosify \
        -u {uid}:{gid} \
        --entrypoint /bin/sonosify \
        deluan/navidrome:latest \
            /sounds/{i} \
            /sounds/{o}""".format(
                sounds=i.path.dirname,
                sonosify=SONOSIFY,
                uid=os.getuid(),
                gid=os.getgid(),
                i=i.path.basename,
                o=new_file_name
            ))
    return AudioFile(i.path.dirpath(new_file_name)) 


def test_mp3_file_should_have_tags_removed(wav):
    mp3 = wav.to_mp3()
    original_md5 = mp3.stream_md5()

    with_tags = mp3.with_tags(
        artist="sonosify-artist", 
        title="sonosify-title", 
        track="sonosify-track", 
        album="sonosify-album"
    )

    assert with_tags.stream_md5() == original_md5

    original_tags = with_tags.tags()
    assert original_tags["artist"] == "sonosify-artist"
    assert original_tags["title"] == "sonosify-title"
    assert original_tags["track"] == "sonosify-track"
    assert original_tags["album"] == "sonosify-album"

    result = sonosify(with_tags)

    assert result.stream_md5() == original_md5

    new_tags = result.tags()
    assert len(new_tags) == 1
    assert "artist" not in new_tags
    assert "title" not in new_tags
    assert "track" not in new_tags
    assert "album" not in new_tags


def test_44k_flac_file_should_have_tags_removed(wav):
    flac = wav.to_flac()
    flac_stream0 = flac.stream0()

    assert flac_stream0["sample_fmt"] == "s16"
    assert flac_stream0["sample_rate"] == "44100"

    original_md5 = flac.stream_md5()

    with_tags = flac.with_tags(
        artist="sonosify-artist", 
        title="sonosify-title", 
        track="sonosify-track", 
        album="sonosify-album"
    )

    assert with_tags.stream_md5() == original_md5

    original_tags = with_tags.tags()
    assert original_tags["artist"] == "sonosify-artist"
    assert original_tags["title"] == "sonosify-title"
    assert original_tags["track"] == "sonosify-track"
    assert original_tags["album"] == "sonosify-album"

    result = sonosify(with_tags)
    result_stream0 = result.stream0()

    assert result_stream0["sample_fmt"] == "s16"
    assert result_stream0["sample_rate"] == "44100"
    assert result.stream_md5() == original_md5

    new_tags = result.tags()
    assert len(new_tags) == 1
    assert "artist" not in new_tags
    assert "title" not in new_tags
    assert "track" not in new_tags
    assert "album" not in new_tags


@pytest.mark.parametrize(
    "in_bits,in_freq,bits_per_raw_sample,expected_bits,expected_freq,expected_bits_per_raw_sample", 
    [
        ("s16", "44100",  "16", "s16", "44100", "16"), 
        ("s16", "48000",  "16", "s16", "48000", "16"), 
        ("s16", "88200",  "16", "s16", "44100", "16"), 
        ("s16", "96000",  "16", "s16", "48000", "16"), 
        ("s16", "176400", "16", "s16", "44100", "16"), 
        ("s16", "192000", "16", "s16", "48000", "16"), 

        ("s32", "44100",  "24", "s32", "44100", "24"), 
        ("s32", "48000",  "24", "s32", "48000", "24"), 
        ("s32", "88200",  "24", "s32", "44100", "24"), 
        ("s32", "96000",  "24", "s32", "48000", "24"), 
        ("s32", "176400", "24", "s32", "44100", "24"), 
        ("s32", "192000", "24", "s32", "48000", "24"), 
    ]
)
def test_flac_is_downsampled(in_bits, in_freq, bits_per_raw_sample, expected_bits, expected_freq, expected_bits_per_raw_sample, wav):
    flac = wav.to_flac(in_bits, in_freq).with_tags()
    flac_stream0 = flac.stream0()

    assert flac_stream0["sample_fmt"] == in_bits
    assert flac_stream0["sample_rate"] == in_freq
    assert flac_stream0["bits_per_raw_sample"] == bits_per_raw_sample
    assert len(flac.tags()) > 1

    result = sonosify(flac)
    result_stream0 = result.stream0()

    assert result_stream0["sample_fmt"] == expected_bits
    assert result_stream0["sample_rate"] == expected_freq
    assert result_stream0["bits_per_raw_sample"] == expected_bits_per_raw_sample

    assert len(result.tags()) == 1


