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


def run(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=False)
    if result.returncode == 0:     
        return result.stdout.decode('utf-8')
    else:
        print("Ran:{}".format(cmd))
        print(result.stdout.decode('utf-8'))
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


def sonosify(i, target=""):
    new_file_name = "{name}{ext}".format(name = uuid(), ext = i.path.ext)
    print(run("""docker run \
        --rm \
        -t \
        -v {sounds}:/sounds \
        -v {sonosify}:/bin/sonosify \
        -u {uid}:{gid} \
        -e SONOSIFY_LOG=true \
        -e SONOSIFY_TARGET={target} \
        --entrypoint /bin/sonosify \
        deluan/navidrome:latest \
            /sounds/{i} \
            /sounds/{o}""".format(
                sounds=i.path.dirname,
                sonosify=SONOSIFY,
                uid=os.getuid(),
                gid=os.getgid(),
                i=i.path.basename,
                o=new_file_name,
                target=target
            )))
    return AudioFile(i.path.dirpath(new_file_name)) 


def test_mp3_file_should_have_tags_removed(wav):
    mp3 = wav.to_mp3()
    original_md5 = mp3.stream_md5()

    with_tags = mp3.with_tags(
        artist="sonosify-artist", 
        title="sonosify-title", 
        genre="sonosify-genre", 
        album="sonosify-album"
    )

    assert with_tags.stream_md5() == original_md5

    original_tags = with_tags.tags()
    assert original_tags["artist"] == "sonosify-artist"
    assert original_tags["title"] == "sonosify-title"
    assert original_tags["genre"] == "sonosify-genre"
    assert original_tags["album"] == "sonosify-album"

    result = sonosify(with_tags)

    assert result.stream_md5() == original_md5
    assert list(result.tags().keys()) == ["encoder"]


def test_44k_flac_file_should_have_tags_removed(wav):
    flac = wav.to_flac()
    flac_stream0 = flac.stream0()

    assert flac_stream0["sample_fmt"] == "s16"
    assert flac_stream0["sample_rate"] == "44100"

    original_md5 = flac.stream_md5()

    with_tags = flac.with_tags(
        artist="sonosify-artist", 
        title="sonosify-title", 
        genre="sonosify-genre", 
        album="sonosify-album"
    )

    assert with_tags.stream_md5() == original_md5

    original_tags = with_tags.tags()
    assert original_tags["artist"] == "sonosify-artist"
    assert original_tags["title"] == "sonosify-title"
    assert original_tags["genre"] == "sonosify-genre"
    assert original_tags["album"] == "sonosify-album"

    result = sonosify(with_tags)
    result_stream0 = result.stream0()
    assert result_stream0["sample_fmt"] == "s16"
    assert result_stream0["sample_rate"] == "44100"
    assert result.stream_md5() == original_md5
    assert list(result.tags().keys()) == ["encoder"]


@pytest.mark.parametrize(
    "target,in_bits,in_freq,bits_per_raw_sample,expected_bits,expected_freq,expected_bits_per_raw_sample,expected_stream_hash_match", 
    [
        (None, "s16", "44100",  "16", "s16", "44100", "16", True), 
        (None, "s16", "48000",  "16", "s16", "48000", "16", True), 
        (None, "s16", "88200",  "16", "s16", "44100", "16", False), 
        (None, "s16", "96000",  "16", "s16", "48000", "16", False), 
        (None, "s16", "176400", "16", "s16", "44100", "16", False), 
        (None, "s16", "192000", "16", "s16", "48000", "16", False), 

        (None, "s32", "44100",  "24", "s32", "44100", "24", True), 
        (None, "s32", "48000",  "24", "s32", "48000", "24", True), 
        (None, "s32", "88200",  "24", "s32", "44100", "24", False), 
        (None, "s32", "96000",  "24", "s32", "48000", "24", False), 
        (None, "s32", "176400", "24", "s32", "44100", "24", False), 
        (None, "s32", "192000", "24", "s32", "48000", "24", False), 

        ("S1", "s16", "44100",  "16", "s16", "44100", "16", True), 
        ("S1", "s16", "48000",  "16", "s16", "48000", "16", True), 
        ("S1", "s16", "88200",  "16", "s16", "44100", "16", False), 
        ("S1", "s16", "96000",  "16", "s16", "48000", "16", False), 
        ("S1", "s16", "176400", "16", "s16", "44100", "16", False), 
        ("S1", "s16", "192000", "16", "s16", "48000", "16", False), 

        ("S1", "s32", "44100",  "24", "s16", "44100", "16", False), 
        ("S1", "s32", "48000",  "24", "s16", "48000", "16", False), 
        ("S1", "s32", "88200",  "24", "s16", "44100", "16", False), 
        ("S1", "s32", "96000",  "24", "s16", "48000", "16", False), 
        ("S1", "s32", "176400", "24", "s16", "44100", "16", False), 
        ("S1", "s32", "192000", "24", "s16", "48000", "16", False), 
    ]
)
def test_flac_is_downsampled(
    target,
    in_bits, 
    in_freq, 
    bits_per_raw_sample, 
    expected_bits, 
    expected_freq, 
    expected_bits_per_raw_sample, 
    expected_stream_hash_match, 
    wav
):
    flac = wav.to_flac(in_bits, in_freq).with_tags()
    flac_stream0 = flac.stream0()

    assert flac_stream0["codec_name"] == "flac"
    assert flac_stream0["sample_fmt"] == in_bits
    assert flac_stream0["sample_rate"] == in_freq
    assert flac_stream0["bits_per_raw_sample"] == bits_per_raw_sample
    assert len(flac.tags()) > 1

    result = sonosify(
        flac,
        target=target
    )
    result_stream0 = result.stream0()

    assert result_stream0["codec_name"] == "flac"
    assert result_stream0["sample_fmt"] == expected_bits
    assert result_stream0["sample_rate"] == expected_freq
    assert result_stream0["bits_per_raw_sample"] == expected_bits_per_raw_sample

    assert len(result.tags()) == 1

    if(expected_stream_hash_match):
        assert result.stream_md5() == flac.stream_md5()


@pytest.mark.parametrize(
    "target,in_bits,in_freq,bits_per_raw_sample,expected_bits,expected_freq,expected_bits_per_raw_sample,expected_stream_hash_match", 
    [
        (None, "s16", "44100",  "16", "s16", "44100", "16", True), 
        (None, "s16", "48000",  "16", "s16", "48000", "16", True), 
        (None, "s16", "88200",  "16", "s16", "44100", "16", False), 
        (None, "s16", "96000",  "16", "s16", "48000", "16", False), 

        (None, "s32", "44100",  "24", "s32", "44100", "24", True), 
        (None, "s32", "48000",  "24", "s32", "48000", "24", True), 
        (None, "s32", "88200",  "24", "s32", "44100", "24", False), 
        (None, "s32", "96000",  "24", "s32", "48000", "24", False), 

        ("S1", "s16", "44100",  "16", "s16", "44100", "16", True), 
        ("S1", "s16", "48000",  "16", "s16", "48000", "16", True), 
        ("S1", "s16", "88200",  "16", "s16", "44100", "16", False), 
        ("S1", "s16", "96000",  "16", "s16", "48000", "16", False), 

        ("S1", "s32", "44100",  "24", "s16", "44100", "16", False), 
        ("S1", "s32", "48000",  "24", "s16", "48000", "16", False), 
        ("S1", "s32", "88200",  "24", "s16", "44100", "16", False), 
        ("S1", "s32", "96000",  "24", "s16", "48000", "16", False), 
    ]
)
def test_alac_is_downsampled_and_converted_to_flac(
    target,
    in_bits, 
    in_freq, 
    bits_per_raw_sample, 
    expected_bits, 
    expected_freq, 
    expected_bits_per_raw_sample, 
    expected_stream_hash_match, 
    wav
):
    m4a = wav.to_flac(in_bits, in_freq).with_tags().to_alac()
    m4a_stream0 = m4a.stream0()

    assert m4a_stream0["codec_name"] == "alac"
    assert m4a_stream0["sample_fmt"] == "{}p".format(in_bits)
    assert m4a_stream0["sample_rate"] == in_freq
    assert m4a_stream0["bits_per_raw_sample"] == bits_per_raw_sample
    assert len(m4a.tags()) > 1

    result = sonosify(
        m4a,
        target=target
    )
    result_stream0 = result.stream0()

    assert result_stream0["codec_name"] == "flac"
    assert result_stream0["sample_fmt"] == expected_bits
    assert result_stream0["sample_rate"] == expected_freq
    assert result_stream0["bits_per_raw_sample"] == expected_bits_per_raw_sample

    assert len(result.tags()) == 1

    if(expected_stream_hash_match):
        assert result.stream_md5() == m4a.stream_md5()


def test_alac_m4a_has_tags_removed(wav):
    m4a = wav.to_flac().with_tags(
        artist="bob",
        title="jane",
        genre="jeff",
        album="great stuff"
    ).to_alac()

    original_tags = m4a.tags()
    assert original_tags["artist"] == "bob"
    assert original_tags["title"] == "jane"
    assert original_tags["genre"] == "jeff"
    assert original_tags["album"] == "great stuff"

    result = sonosify(m4a)
    assert list(result.tags().keys()) == ["encoder"]


def test_aac_is_converted_to_flac(wav):
    aac = wav.to_aac()
    aac_stream0 = aac.stream0()
    assert aac_stream0["codec_name"] == "aac"

    result = sonosify(aac)
    result_stream0 = result.stream0()
    assert result_stream0["codec_name"] == "flac"


def test_aac_m4a_has_tags_removed(wav):
    m4a = wav.with_tags(
        artist="bob",
        title="jane",
        genre="jeff",
        album="great stuff"
    ).to_aac()

    original_tags = m4a.tags()
    assert original_tags["artist"] == "bob"
    assert original_tags["title"] == "jane"
    # assert original_tags["genre"] == "jeff"
    assert original_tags["album"] == "great stuff"

    result = sonosify(m4a)
    assert list(result.tags().keys()) == ["encoder"]

# docker run --rm -v /tmp:/sounds -v /home/simon/src/github/simojenki/sonosify/sonosify:/bin/sonosify -u 1000:1000 --entrypoint /bin/sonosify deluan/navidrome:latest /sounds/out.wav /sounds/123.m4a