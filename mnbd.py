import parted
import logging
import subprocess
import os
import sys
import shutil
from pathlib import Path

logging.basicConfig(format='[%(process)d] %(levelname)s %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)


def unmount(nbd_device, mount_point):
    check_output(['umount', '-l', mount_point])
    check_output(['nbd-client', '-d', nbd_device])


def mount(nbd_device, mount_point, mode, host, port):

    dir_path = Path(mount_point)
    if dir_path.exists() and dir_path.is_dir():
        shutil.rmtree(mount_point)
    dir_path.mkdir(parents=True, exist_ok=False)

    check_output([
        'nbd-client', '-p', '-t', '60', '-b', '512', host, port,
        nbd_device
    ])

    # create dev mapper
    check_output(['kpartx', '-a', '-s', '-v', nbd_device])

    check_output([
        'mount', '-t', "ntfs", '-o', "rw",
        get_device_mapper_path(nbd_device), mount_point
    ])


def get_device_mapper_path(nbd_device):
    return '/dev/mapper/%sp1' % nbd_device.split('/')[2]


def get_partition(path):
    try:
        device = parted.Device(path)
        disk = parted.Disk(device)
    except parted.IOException as e:
        raise Exception('Failed to get parted info for %s' % path) from e
    except parted.disk._ped.DiskLabelException as e:
        raise Exception('failed to parse disk for %s' % path) from e

    mapping = dict()
    for partition in disk.partitions:
        if partition.fileSystem is None:
            raise Exception("Unknown file system: %s" % partition)
        attr = dict()
        attr['filesystem'] = partition.fileSystem.type
        mapping[str(partition.number)] = attr
    return mapping


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
