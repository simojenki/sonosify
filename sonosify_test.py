import pytest
import os
from uuid import uuid4 as uuid

from test_utils import run, AudioFile, DEFAULT_IMAGE


SONOSIFY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sonosify')
JSON_SH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'JSON.sh')


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
        {image} \
            /sounds/{i} \
            /sounds/{o}""".format(
                sounds=i.path.dirname,
                sonosify=SONOSIFY,
                uid=os.getuid(),
                gid=os.getgid(),
                image=DEFAULT_IMAGE, 
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