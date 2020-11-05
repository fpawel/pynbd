import logging
import subprocess
import sys
import shutil
from pathlib import Path

logging.basicConfig(format='[%(process)d] SETUP-P2V %(levelname)s %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)


def unmount(nbd_device, mount_point):
    check_output(['umount', '-l', mount_point])
    shutil.rmtree(mount_point)
    # delete partition mappings
    check_output(['kpartx', '-d', nbd_device])
    check_output(['nbd-client', '-d', nbd_device])


def mount(nbd_device, mount_point, host, port):

    mount_point_dir_path = Path(mount_point)
    if mount_point_dir_path.exists() and mount_point_dir_path.is_dir():
        shutil.rmtree(mount_point)
    mount_point_dir_path.mkdir(parents=True, exist_ok=False)

    check_output([
        'nbd-client', '-p', '-t', '60', '-b', '512', host, port,
        nbd_device
    ])

    # create partition mappings
    check_output(['kpartx', '-a', '-s', nbd_device])

    check_output([
        'mount', '-t', "ntfs-3g", '-o', "rw",
        get_device_mapper_path(nbd_device), mount_point
    ])


def get_device_mapper_path(nbd_device):
    return '/dev/mapper/%sp1' % nbd_device.split('/')[2]


def check_output(cmd):
    log.info(' '.join(cmd))
    subprocess.check_output(cmd)


if __name__ == '__main__':
    if sys.argv[1] == "-m":
        mount(*(sys.argv[2:]))
    elif sys.argv[1] == "-u":
        unmount(*(sys.argv[2:]))
    else:
        raise Exception("unexpected key: %s", sys.argv[1])
