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
    parts = get_partition(nbd_device)
    log.info(parts)
    for part in parts:
        _, path = get_device_path_of_partition(nbd_device, mount_point, part)
        check_output(['umount', '-l', path])
        check_output(['nbd-client', '-d', nbd_device])


def mount(nbd_device, mount_point, mode, host, port):
    dir_path = Path(mount_point)
    if dir_path.exists() and dir_path.is_dir():
        shutil.rmtree(mount_point)
    dir_path.mkdir(parents=True, exist_ok=False)

    log.info('run nbd-client for %s...' % nbd_device)
    check_output([
        'nbd-client', '-p', '-t', '60', '-b', '512', host, port,
        nbd_device
    ])

    # create dev mapper
    check_output(['kpartx', '-a', '-s', '-v', nbd_device])

    parts = get_partition(nbd_device)

    partitions = []

    for part in parts:
        partition = parts[part]
        partition['part'] = part
        device, path = get_device_path_of_partition(nbd_device, mount_point, part)

        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)

        partition['device'] = device
        partition['path'] = path
        partition['mount_point'] = mount_point
        partition['nbd_device'] = nbd_device

        log.info("partition: %s", partition)

        check_output([
            'mount', '-t', partition['filesystem'], '-o', mode,
            device, path
        ])

        partitions.append(partition)
        log.info(partition)

    return partitions


def get_device_path_of_partition(nbd_device, mount_point, part):
    nbd = nbd_device.split('/')[2]
    device = '/dev/mapper/%sp%s' % (nbd, part)
    path = os.path.join(mount_point, part)
    return device, path


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
