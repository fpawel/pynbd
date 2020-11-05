import mproc
import parted
import logging

from . import P2VEx
from .partition import \
    GptPartition, \
    MbrDisk, \
    PartitionStyle
from .sectors import Sectors

log = logging.getLogger(__name__)


def SetMbrDiskId(path, identity):
    if len(identity.buf()) != MbrDisk.id_length:
        raise P2VEx("mbr identity is not %d bytes long" % MbrDisk.id_length)
    with open(path, "rb+") as f:
        f.seek(MbrDisk.id_offset)
        f.write(identity.buf())


def get_mbr_disk_id(path):
    with open(path, "rb") as f:
        f.seek(MbrDisk.id_offset)
        signature = f.read(MbrDisk.id_length)
    return bytearray(signature)


def set_gpt_partition_id(path, partition_number, identity):
    if len(identity.buf()) != GptPartition.unique_guid_length:
        raise P2VEx("gpt identity is not %d bytes long" %
                    GptPartition.unique_guid_length)
    mproc.check_call(['/sbin/sgdisk',
                      '--partition-guid=%d:%s' % (partition_number, identity.guid()), path])


def get_gpt_partition_id(path, partition_number):
    with open(path, "rb") as f:
        offset = GptPartition.get_unique_guid_offset(partition_number)
        log.debug("reading guid at offset: %d" % offset)
        f.seek(offset)
        guid_bytes = f.read(GptPartition.unique_guid_length)
    return bytearray(guid_bytes)


def _AddPartitionToDisk(parted_device, parted_disk, p2v_partition):
    sector_offset = Sectors(p2v_partition.offset)
    sector_length = Sectors(p2v_partition.length)
    log.debug("adding partition: %s" % p2v_partition + \
              "\n\toffset (sectors)\t= %d" % sector_offset + \
              "\n\tlength (sectors)\t= %d" % sector_length)

    if p2v_partition.style == PartitionStyle.Primary:
        parted_partition_type = parted.PARTITION_NORMAL
    elif p2v_partition.style == PartitionStyle.Extended:
        parted_partition_type = parted.PARTITION_EXTENDED
    elif p2v_partition.style == PartitionStyle.Logical:
        parted_partition_type = parted.PARTITION_LOGICAL
    elif p2v_partition.style == PartitionStyle.Gpt:
        parted_partition_type = parted.PARTITION_NORMAL
    else:
        raise P2VEx("unsupported partition type: %s" % p2v_partition.type)

    geometry = parted.Geometry(
        device=parted_device,
        start=sector_offset,
        length=sector_length)

    filesystem = None
    if p2v_partition.volume is not None:
        filesystem = parted.filesystem.FileSystem(
            type='ntfs',
            geometry=geometry)

    partition = parted.Partition(
        disk=parted_disk, type=parted_partition_type, fs=filesystem,
        geometry=geometry)
    parted_disk.addPartition(
        partition=partition,
        constraint=parted_device.optimalAlignedConstraint)

    if p2v_partition.volume is not None and \
            p2v_partition.volume.is_system_drive():
        partition.setFlag(parted.PARTITION_BOOT)


def FormatMbr(path, p2v_disk):
    device = parted.getDevice(path)
    disk = parted.freshDisk(device, 'msdos')
    log.debug("editing disk image: %s" % path)
    for p2v_partition in p2v_disk.partitions:
        _AddPartitionToDisk(device, disk, p2v_partition)
    for p2v_partition in p2v_disk.logical_partitions:
        _AddPartitionToDisk(device, disk, p2v_partition)
    disk.commit()
    if p2v_disk.identity is not None:
        SetMbrDiskId(path, p2v_disk.identity)


def FormatGpt(path, p2v_disk):
    device = parted.getDevice(path)
    disk = parted.freshDisk(device, 'gpt')
    log.debug("editing disk image: %s" % path)
    p2v_partitions = p2v_disk.get_partitions()
    for p2v_partition in p2v_partitions:
        _AddPartitionToDisk(device, disk, p2v_partition)
    disk.commit()
    # partition numbers start at one
    for index, p2v_partition in enumerate(p2v_partitions, 1):
        if p2v_partition.identity is not None:
            set_gpt_partition_id(path, index, p2v_partition.identity)
