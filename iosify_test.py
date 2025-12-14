import pytest
import os
from uuid import uuid4 as uuid

from test_utils import run, AudioFile, DEFAULT_IMAGE


IOSIFY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iosify')
JSON_SH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'JSON.sh')


def iosify(i):
    new_file_name = "{name}.mp3".format(name = uuid())
    print(run("""docker run \
        --rm \
        -t \
        -v {sounds}:/sounds \
        -v {iosify}:/bin/iosify \
        -u {uid}:{gid} \
        -e IOSIFY_LOG=true \
        --entrypoint /bin/iosify \
        {image} \
            /sounds/{i} \
            /sounds/{o}""".format(
                sounds=i.path.dirname,
                iosify=IOSIFY,
                uid=os.getuid(),
                gid=os.getgid(),
                image=DEFAULT_IMAGE,
                i=i.path.basename,
                o=new_file_name
            )))
    return AudioFile(i.path.dirpath(new_file_name)) 


def test_flac_is_transcoded_to_aac_removing_tags(wav):
    input = wav.to_flac()

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

    m4a = iosify(input_with_tags)

    result_stream0 = m4a.stream0()

    assert result_stream0["codec_name"] == "aac"
    assert result_stream0["sample_fmt"] == "fltp"
    assert result_stream0["sample_rate"] == "44100"

    assert list(m4a.tags().keys()) == ["encoder"]


# def test_mp3_file_should_have_tags_removed(wav):
#     mp3 = wav.to_mp3()

#     with_tags = mp3.with_tags(
#         artist="sonosify-artist", 
#         title="sonosify-title", 
#         genre="sonosify-genre", 
#         album="sonosify-album"
#     )

#     original_tags = with_tags.tags()
#     assert original_tags["artist"] == "sonosify-artist"
#     assert original_tags["title"] == "sonosify-title"
#     assert original_tags["genre"] == "sonosify-genre"
#     assert original_tags["album"] == "sonosify-album"

#     result = iosify(with_tags)

#     assert list(result.tags().keys()) == ["encoder"]


# def test_mp3_file_should_have_same_audio_as_original_however_tags_removed(wav):
#     mp3 = wav.to_mp3()
#     original_md5 = mp3.stream_md5()

#     with_tags = mp3.with_tags(
#         artist="sonosify-artist", 
#         title="sonosify-title", 
#         genre="sonosify-genre", 
#         album="sonosify-album"
#     )

#     original_tags = with_tags.tags()
#     assert original_tags["artist"] == "sonosify-artist"
#     assert original_tags["title"] == "sonosify-title"
#     assert original_tags["genre"] == "sonosify-genre"
#     assert original_tags["album"] == "sonosify-album"

#     result = iosify(with_tags)

#     assert result.stream_md5() == original_md5

#     assert list(result.tags().keys()) == ["encoder"]


