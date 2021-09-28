import pytest
import subprocess
import json
import os
from uuid import uuid4 as uuid

SONOSIFY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sonosify')

class AudioFile:
    def __init__(self, path):
        assert path.check()
        self.path = path


    def tags(self):
        out = run("""docker run \
            --rm \
            -v {sounds}:/sounds \
            -u {uid}:{gid} \
            --entrypoint ffprobe \
            deluan/navidrome:latest \
                -show_format \
                -print_format json \
                /sounds/{i}""".format(
                    sounds=self.path.dirname,
                    uid=os.getuid(),
                    gid=os.getgid(),
                    i=self.path.basename
                ))
        return json.loads(out)["format"]["tags"]
            

    def with_tags(self, artist="", title="", track="", album=""):
        new_file_name = "{name}{ext}".format(name = uuid(), ext = self.path.ext)
        run("""docker run \
            --rm \
            -v {sounds}:/sounds \
            -u {uid}:{gid} \
            --entrypoint ffmpeg \
            deluan/navidrome:latest \
                -i /sounds/{i} \
                -map 0 \
                -codec copy \
                -write_id3v2 1 \
                -metadata "artist={artist}" \
                -metadata "title={title}" \
                -metadata "track={track}" \
                -metadata "album={album}" \
                /sounds/{o}""".format(
                    sounds=self.path.dirname, 
                    uid=os.getuid(),
                    gid=os.getgid(),
                    i=self.path.basename,
                    o=new_file_name,
                    artist=artist,
                    title=title,
                    track=track,
                    album=album
                ))
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
    run("""docker run \
        --rm \
        -v {sounds}:/sounds \
        -u {uid}:{gid} \
        --entrypoint ffmpeg \
        deluan/navidrome:latest \
            -f lavfi \
            -i 'sine=frequency=1000:duration=1' \
            -ac 2 \
            /sounds/{o}""".format(
                sounds=tmp_sounds, 
                uid=os.getuid(),
                gid=os.getgid(),
                o=filename
            ))
    return AudioFile(tmp_sounds.join(filename))


@pytest.fixture(scope="session")
def mp3(tmp_sounds, wav):
    filename = "sound.mp3"
    run("""docker run \
        --rm \
        -v {sounds}:/sounds \
        -u {uid}:{gid} \
        --entrypoint ffmpeg \
        deluan/navidrome:latest \
            -i /sounds/{i} \
            -ar 44100 \
            -ac 2 \
            -b:a 192k \
            /sounds/{o}""".format(
                sounds=tmp_sounds, 
                uid=os.getuid(),
                gid=os.getgid(),
                i=wav.path.basename, 
                o=filename
            ))
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


def test_mp3_file_should_have_tags_removed(mp3):
    mp3_with_tags = mp3.with_tags(
        artist="sonosify-artist", 
        title="sonosify-title", 
        track="sonosify-track", 
        album="sonosify-album"
    )
    original_tags = mp3_with_tags.tags()
    assert original_tags["artist"] == "sonosify-artist"
    assert original_tags["title"] == "sonosify-title"
    assert original_tags["track"] == "sonosify-track"
    assert original_tags["album"] == "sonosify-album"

    result = sonosify(
        i=mp3_with_tags
    )

    assert result.path.check()
    new_tags = result.tags()
    assert "artist" not in new_tags
    assert "title" not in new_tags
    assert "track" not in new_tags
    assert "album" not in new_tags
