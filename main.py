import parted
import logging
import binascii
import subprocess
import os
import sys
import shutil
from pathlib import Path
from p2v.table import get_mbr_disk_id, get_gpt_partition_id
from ntfs3g.volume import get_ntfs_volume_info

logging.basicConfig(format='[%(process)d] %(levelname)s %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)

supported_fs = (
    "ntfs",
    "ext2",
    "ext3",
    "ext4"
)


def mount(nbd_device, mount_point, mode, host, port):

    dir_path = Path(mount_point)
    if dir_path.exists() and dir_path.is_dir():
        shutil.rmtree(dir_path)
    dir_path.mkdir(parents=True, exist_ok=False)

    log.info('run nbd-client for %s...' % nbd_device)
    check_output([
        'sudo', "-S",
        'nbd-client', '-p', '-t', '60', '-b', '512', host, port,
        nbd_device
    ])

    partitions = get_partition(nbd_device)
    log.info(partitions)
    partition = None
    for part in partitions:
        partition = partitions[part]
        partition['part'] = part
        break

    # create dev mapper
    check_output(['kpartx', '-a', '-s', '-v', nbd_device])

    nbd = nbd_device.split('/')[2]

    device = '/dev/mapper/%sp%s' % (nbd, partition['part'])

    if partition['filesystem'] == 'ntfs':
        # get cluster size
        volume_info = get_ntfs_volume_info(device, force=True)
        cluster_size = int(volume_info['bytes_per_cluster'])
        print('get cluster size for %s: %s' % (
            device, cluster_size
        ))
        partition['cluster_size'] = cluster_size

    path = os.path.join(mount_point, partition['part'])

    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

    partition['device'] = device
    partition['path'] = path
    partition['mount_point'] = mount_point
    partition['nbd_device'] = nbd_device

    check_output([
        'sudo',
        'mount', '-t', partition['filesystem'], '-o', mode,
        device, path
    ])
    return partition


def get_partition(path):

    try:
        device = parted.Device(path)
        disk = parted.Disk(device)
    except parted.IOException as e:
        raise Exception('Failed to get parted info for %s' % path) from e
    except parted.disk._ped.DiskLabelException as e:
        raise Exception('failed to parse disk for %s' % path) from e

    disk_id = None
    mapping = dict()
    for partition in disk.partitions:
        if partition.fileSystem is None:
            raise Exception("Unknown file system: %s" % partition)
        if partition.fileSystem.type not in supported_fs:
            raise Exception("Unsupported file system: %s" % partition)
        geometry = partition.geometry
        attr = dict()
        attr['start'] = geometry.start * 512
        attr['length'] = geometry.length * 512
        attr['type'] = disk.type
        attr['filesystem'] = partition.fileSystem.type
        if disk.type == 'msdos':
            if not disk_id:
                disk_id = get_mbr_disk_id(path)
                disk_id = binascii.hexlify(disk_id)
            attr['disk_id'] = disk_id
        elif disk.type == 'gpt':
            guid = get_gpt_partition_id(path, partition.number)
            guid = binascii.hexlify(guid)
            attr['guid'] = guid
            log.debug(attr)
        mapping[str(partition.number)] = attr
    return mapping


def check_output(cmd):
    log.info(' '.join(cmd))
    subprocess.check_output(cmd)


if __name__ == '__main__':
    mount(*(sys.argv[1:]))