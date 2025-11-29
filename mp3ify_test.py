import pytest
import os
from uuid import uuid4 as uuid

from test_utils import docker, run, AudioFile


MP3IFY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mp3ify')
JSON_SH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'JSON.sh')


def mp3ify(i):
    new_file_name = "{name}.mp3".format(name = uuid())
    print(run("""docker run \
        --rm \
        -t \
        -v {sounds}:/sounds \
        -v {mp3ify}:/bin/mp3ify \
        -u {uid}:{gid} \
        -e MP3IFY_LOG=true \
        --entrypoint /bin/mp3ify \
        deluan/navidrome:latest \
            /sounds/{i} \
            /sounds/{o}""".format(
                sounds=i.path.dirname,
                mp3ify=MP3IFY,
                uid=os.getuid(),
                gid=os.getgid(),
                i=i.path.basename,
                o=new_file_name
            )))
    return AudioFile(i.path.dirpath(new_file_name)) 


def test_mp3_file_should_be_same_as_original_retaining_tags(wav):
    mp3 = wav.to_mp3()
    original_md5 = mp3.stream_md5()

    with_tags = mp3.with_tags(
        artist="artist 1", 
        title="title 1", 
        genre="genre 1", 
        album="album 1"
    )

    assert with_tags.stream_md5() == original_md5

    original_tags = with_tags.tags()
    assert original_tags["artist"] == "artist 1"
    assert original_tags["title"] == "title 1"
    assert original_tags["genre"] == "genre 1"
    assert original_tags["album"] == "album 1"

    result = mp3ify(with_tags)

    assert result.stream_md5() == original_md5

    result_tags = result.tags()
    assert result_tags["artist"] == "artist 1"
    assert result_tags["title"] == "title 1"
    assert result_tags["genre"] == "genre 1"
    assert result_tags["album"] == "album 1"


@pytest.mark.parametrize("input_type",
    [
        ("flac"), 
        ("alac"), 
        ("aac")
    ]
)
def test_non_mp3_are_transcoded_to_mp3_retaining_tags(wav, input_type):
    if input_type == "flac":
        input = wav.to_flac()
    elif input_type == "alac":
        input = wav.to_alac()
    elif input_type == "aac":
        input = wav.to_aac()

    input_with_tags = input.with_tags(
        artist="a1",
        title="t1",
        genre="g1",
        album="b1"
    )

    original_tags = input_with_tags.tags()
    assert original_tags["artist"] == "a1"
    assert original_tags["title"] == "t1"
    assert original_tags["genre"] == "g1"
    assert original_tags["album"] == "b1"

    mp3 = mp3ify(input_with_tags)
    result_stream0 = mp3.stream0()

    assert result_stream0["codec_name"] == "mp3"
    assert result_stream0["sample_fmt"] == "fltp"
    assert result_stream0["sample_rate"] == "44100"

    mp3_tags = mp3.tags()
    assert mp3_tags["artist"] == "a1"
    assert mp3_tags["title"] == "t1"
    assert mp3_tags["genre"] == "g1"
    assert mp3_tags["album"] == "b1"

