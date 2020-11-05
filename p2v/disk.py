from . import P2VEx
from .identity import GptFlavor, Id, MbrDiskId, MbrFlavor
from .partition import Partition, PartitionStyle, GptDisk

from units.bytes import Mebibytes

import json
import logging

log = logging.getLogger(__name__)


def find_only(the_filter, the_iterable, default=None):
    filtered = list(filter(the_filter, the_iterable))
    assert len(filtered) <= 1
    if len(filtered) == 0:
        return default
    return filtered[0]


class MasterBootRecord:
    """
   A master boot record's length is one sector. See
   https://en.wikipedia.org/wiki/Master_boot_record for details.
   """
    Length = 512


class BootHeader:
    """
   The start of the first partition in an MBR formatted disk typically begins
   at 1 MiB. The first 1 MiB of a boot disk typically contains not only the
   partition table but also boot-code -- the code executed during the first
   stage of the boot process. See https://en.wikipedia.org/wiki/Boot_sector
   for details.
   """
    Length = Mebibytes(1)


class Disk:

    def __init__(self,
                 length,
                 partitions=(),
                 identity=None,
                 logical_partitions=()):

        if not Partition.CheckSanity(partitions):
            raise P2VEx("partitions failed sanity check")

        if logical_partitions:
            extended = find_only(
                lambda partition: partition.style == PartitionStyle.Extended,
                partitions)
            if extended is None:
                raise P2VEx(
                    "no extended partition in disk with logical partitions")
            if not Partition.CheckBounds(
                    extended.offset + BootHeader.Length,
                    extended.offset + extended.length,
                    logical_partitions):
                raise P2VEx("logical partitions failed sanity check")

        if partitions:
            if identity is not None and partitions[0].identity is not None:
                if not partitions[0].identity.congruent(identity):
                    raise P2VEx("partitions are not congruent with disk")
            if partitions[-1].offset + partitions[-1].length > length:
                message = "partition bounds exceed disk length"
                log.error(
                    "%s:\n\t" % message +
                    "partitions: %s\n\t" % partitions +
                    "disk length: %d" % length)
                raise P2VEx(message)

        self.identity = identity
        self.length = length
        self.partitions = tuple(partitions)
        self.logical_partitions = tuple(logical_partitions)

    def get_partitions(self):
        return self.partitions + self.logical_partitions

    def get_boot_partition(self):
        return find_only(lambda part: part.is_boot_partition(), self.partitions)

    def partition_number(self, drive):
        all_parts = self.get_partitions()
        for i, partition in zip(list(range(len(all_parts))), all_parts):
            if partition.volume is not None:
                if partition.volume.drive is not None:
                    if partition.volume.drive == drive:
                        return i + 1
        return None

    def is_boot_disk(self):
        boot_partition = self.get_boot_partition()
        if boot_partition is None:
            return False
        return True

    def _is_flavored(self, flavor):
        def _is_gpt_flavored(identity):
            return identity.is_gpt()

        def _is_mbr_flavored(identity):
            return identity.is_mbr()

        if flavor == 'gpt':
            check = _is_gpt_flavored
        elif flavor == 'mbr':
            check = _is_mbr_flavored
        else:
            raise P2VEx('no such flavor: %s' % flavor)

        # check if the disk has an identity
        if self.identity is not None:
            return check(self.identity)
        # if not, check if any of the partitions have an identity
        first_part = self.get_partitions()[0]
        if first_part.identity is not None:
            return check(first_part.identity)

        return False

    def is_mbr(self):
        return self._is_flavored('mbr')

    def is_gpt(self):
        return self._is_flavored('gpt')

    def is_unspecified(self):
        if self.identity is not None:
            return False
        first_part = self.get_partitions()[0]
        return first_part.identity is not False

    def volumes(self):
        return [partition.volume for partition in self.get_partitions() if \
                partition.volume is not None]

    def encode(self):
        return {
            "length": self.length,
            "identity": self.identity.encode() if self.identity is not None else None,
            "partitions":
                [partition.encode() for partition in self.partitions],
            "logical_partitions":
                [partition.encode() for partition in self.logical_partitions]
        }

    @staticmethod
    def decode(encoded):
        identity = Id.Decode(encoded['identity'])
        length = encoded['length']
        e_parts = encoded['partitions']
        partitions = [Partition.Decode(e_part) for e_part in e_parts]
        el_parts = encoded['logical_partitions']
        logical_partitions = \
            [Partition.Decode(el_part) for el_part in el_parts]
        return Disk(
            length,
            partitions=partitions,
            identity=identity,
            logical_partitions=logical_partitions)

    def __eq__(self, other):
        if self.identity != other.identity:
            return False
        if self.length != other.length:
            return False
        for p0, p1 in zip(self.partitions, other.partitions):
            if p0 != p1:
                return False
        for p0, p1 in zip(self.logical_partitions, other.logical_partitions):
            if p0 != p1:
                return False
        return True

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "Disk { %s, %d, %s }" % (self.identity.__repr__(),
                                        self.length, self.partitions)


def MakeMbrDisk(*volumes):
    physical_volumes = volumes[:3]
    logical_volumes = volumes[3:]
    disk_id = MbrDiskId(volumes[0].identity.signature())

    physical = list()
    for volume in physical_volumes:
        offset = volume.identity.offset()
        length = volume.device.length
        partition = Partition(offset, length,
                              style=PartitionStyle.Primary,
                              volume=volume)
        physical.append(partition)

    if not logical_volumes:
        length = physical[-1].offset + physical[-1].length
        return Disk(length,
                    partitions=physical,
                    identity=disk_id)

    extended_offset = physical[-1].offset + physical[-1].length
    last_logical_volume_end = \
        logical_volumes[-1].identity.offset() + logical_volumes[-1].device.length
    extended_length = last_logical_volume_end - extended_offset
    partition = Partition(extended_offset, extended_length,
                          style=PartitionStyle.Extended)
    physical.append(partition)

    logical = list()
    for volume in logical_volumes:
        offset = volume.identity.offset()
        length = volume.device.length
        partition = Partition(offset, length,
                              style=PartitionStyle.Logical,
                              volume=volume)
        logical.append(partition)

    length = logical[-1].offset + logical[-1].length
    return Disk(length,
                identity=disk_id,
                partitions=physical,
                logical_partitions=logical)


def MakeGptDisk(*volumes):
    parts = list()
    offset = GptDisk.aligned_partition_start
    for volume in volumes:
        length = volume.device.length
        if length % GptDisk.partition_alignment > 0:
            length += GptDisk.partition_alignment - length % GptDisk.partition_alignment
        partition = Partition(offset, length,
                              identity=volume.identity,
                              style=PartitionStyle.Gpt,
                              volume=volume)
        parts.append(partition)
        offset += length
        if offset % GptDisk.partition_alignment > 0:
            offset += GptDisk.partition_alignment - offset % GptDisk.partition_alignment

    length = parts[-1].offset + parts[-1].length + \
             GptDisk.secondary_table_length
    return Disk(length, partitions=parts)


def MakeDiskArray(*p2v_volumes):
    disk_array = list()

    def _has_mbr_partition_id(p2v_volume):
        return p2v_volume.identity.flavor == MbrFlavor.partition

    mbr_volumes = list(filter(_has_mbr_partition_id, p2v_volumes))

    mbr_volumes_by_id = dict()
    for mbr_volume in mbr_volumes:
        signature = str(mbr_volume.identity.signature())
        if signature not in mbr_volumes_by_id:
            mbr_volumes_by_id[signature] = [mbr_volume]
        else:
            mbr_volumes_by_id[signature].append(mbr_volume)

    for mbr_volumes in list(mbr_volumes_by_id.values()):
        def _p2v_volume_mbr_offset(volume):
            return volume.identity.offset()

        mbr_volumes.sort(key=_p2v_volume_mbr_offset)
        mbr_disk = MakeMbrDisk(*mbr_volumes)
        disk_array.append(mbr_disk)

    def _has_gpt_id(p2v_volume):
        return p2v_volume.identity.flavor == GptFlavor

    gpt_volumes = list(filter(_has_gpt_id, p2v_volumes))

    if gpt_volumes:
        gpt_disk = MakeGptDisk(*gpt_volumes)
        disk_array.append(gpt_disk)

    return disk_array
