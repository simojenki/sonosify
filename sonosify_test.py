import pytest
import subprocess
import json
import os
import hashlib
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


    def md5(self):
        return hashlib.md5(open(self.path,'rb').read()).hexdigest()


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


    def to_flac(self):
        new_file_name = "{uuid}{ext}".format(uuid = uuid(), ext = ".mp3")
        docker(
            docker_opts="-v {sounds}:/sounds".format(sounds=self.path.dirname),
            entrypoint="ffmpeg",
            args="""-i /sounds/{i} \
                -af aformat=s16:44100 \
                /sounds/{o}""".format(
                    i=self.path.basename, 
                    o=new_file_name
                )
        )
        return AudioFile(self.path.dirpath(new_file_name)) 

    
    def to_raw_wav(self):
        new_file_name = "{uuid}{ext}".format(uuid = uuid(), ext = ".wav")
        docker(
            docker_opts="-v {sounds}:/sounds".format(sounds=self.path.dirname),
            entrypoint="ffmpeg",
            args="""-i /sounds/{i} \
                    -map_metadata -1 \
                    /sounds/{o}""".format(
                        i=self.path.basename,
                        o=new_file_name,
                    )
        )
        return AudioFile(self.path.dirpath(new_file_name)) 


    def with_tags(self, artist="", title="", track="", album=""):
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
    original_md5 = mp3.to_raw_wav().md5()

    with_tags = mp3.with_tags(
        artist="sonosify-artist", 
        title="sonosify-title", 
        track="sonosify-track", 
        album="sonosify-album"
    )

    assert with_tags.to_raw_wav().md5() == original_md5

    original_tags = with_tags.tags()
    assert original_tags["artist"] == "sonosify-artist"
    assert original_tags["title"] == "sonosify-title"
    assert original_tags["track"] == "sonosify-track"
    assert original_tags["album"] == "sonosify-album"

    result = sonosify(with_tags)

    assert result.to_raw_wav().md5() == original_md5

    new_tags = result.tags()
    assert "artist" not in new_tags
    assert "title" not in new_tags
    assert "track" not in new_tags
    assert "album" not in new_tags



def test_flac_file_should_have_tags_removed(wav):
    flac = wav.to_flac()
    original_md5 = flac.to_raw_wav().md5()

    with_tags = flac.with_tags(
        artist="sonosify-artist", 
        title="sonosify-title", 
        track="sonosify-track", 
        album="sonosify-album"
    )

    assert with_tags.to_raw_wav().md5() == original_md5

    original_tags = with_tags.tags()
    assert original_tags["artist"] == "sonosify-artist"
    assert original_tags["title"] == "sonosify-title"
    assert original_tags["track"] == "sonosify-track"
    assert original_tags["album"] == "sonosify-album"

    result = sonosify(with_tags)

    assert result.to_raw_wav().md5() == original_md5

    new_tags = result.tags()
    assert "artist" not in new_tags
    assert "title" not in new_tags
    assert "track" not in new_tags
    assert "album" not in new_tags
