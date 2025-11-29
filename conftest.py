from test_utils import docker, AudioFile

import pytest


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


