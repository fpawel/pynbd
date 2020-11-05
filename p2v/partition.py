import logging

from .identity import Id
from .sectors import SectorBytes
from .volume import Volume
from . import P2VEx
from units.bytes import AlignedOffset, Mebibytes

log = logging.getLogger(__name__)


class PartitionStyle:
    """
   The class members of PartitionStyle identify "styles" of partitions
   recognized by Axcient P2V. 'Primary', 'Extended' and 'Logical' are only
   applicable for MBR formatted disks. 'Gpt' formatted disks contain only
   'Gpt'-style partitions. See
   https://en.wikipedia.org/wiki/Master_boot_record#PT and
   https://en.wikipedia.org/wiki/GUID_Partition_Table for details.
   """
    Primary = 'primary'
    Extended = 'extended'
    Logical = 'logical'
    Gpt = 'gpt'


class MbrDisk:
    """
   The class-members of MbrDisk describe an MBR partition table. See
   https://en.wikipedia.org/wiki/Master_boot_record#PT for details. For
   example:
   - @table_offset   : the offset of the partition table
   - @id_offset      : the offset of the disk signature
   - @id_length      : the length of the disk signature
   - @alignment      : typical alignment of partitions
   """
    table_offset = 0x1be
    id_offset = 0x1b8
    id_length = 4
    alignment = 1024 * 1024


class MbrPartitionEntry:
    """
   The class-members of MbrPartitionEntry describe an MBR partition table
   entry. See https://en.wikipedia.org/wiki/Master_boot_record#PT for details.
   For example:
   - @length   : the length of an entry
   - @type_offset : the offset of the partition type within a partition entry
   - @type_length : the length of the partition type field
   """
    length = 16
    type_offset = 4
    type_length = 1


class GptDisk:
    """
   The class-members of GptDisk describe a GPT formatted disk. See
   https://en.wikipedia.org/wiki/GUID_Partition_Table for details. For example:
   - @table_offset   : the offset of the GPT partition table
   - @entry_size     : the size of an entry in a GPT partition table
   - @aligned_partition_start : the location of the first partition
   - @partition_alignment     : the alignment of partitions
   - @secondary_table_length  : the length of the backup partition table
   """
    table_offset = SectorBytes(2)
    entry_size = 0x80
    aligned_partition_start = 1024 * 1024
    partition_alignment = 1024 * 1024
    secondary_table_length = SectorBytes(33)

    @staticmethod
    def get_entry_offset(partition_number):
        """
      get the offset of an entry in a GPT partitioned disk's partition
      table
      """
        return GptDisk.table_offset + (partition_number - 1) * GptDisk.entry_size


class GptPartition:
    """
   The class-members of GptPartition describe a GPT partition entry. See
   https://en.wikipedia.org/wiki/GUID_Partition_Table for details. For
   example:
   - @unique_guid_offset   : the offset of the GUID in the entry
   - @unique_guid_length   : the length of the GUID field
   """
    unique_guid_offset = 0x10
    unique_guid_length = 0x10

    @staticmethod
    def get_unique_guid_offset(partition_number):
        """
      get the offset of the unique GUID in an entry in a GPT partitioned
      disk's partition table
      """
        return GptDisk.get_entry_offset(partition_number) + \
               GptPartition.unique_guid_offset


PerPartitionOverhead = \
    {
        PartitionStyle.Primary: 0,
        PartitionStyle.Extended: 0,
        PartitionStyle.Logical: SectorBytes(1),
        PartitionStyle.Gpt: 0
    }


class Partition:

    def __init__(self, offset, length, style=PartitionStyle.Primary,
                 identity=None,
                 volume=None,
                 alignment=Mebibytes(1)):

        if not AlignedOffset(offset, alignment).is_aligned():
            raise P2VEx("start not aligned: %d" % offset)

        if not AlignedOffset(length, alignment).is_aligned():
            raise P2VEx("end not aligned: %d" % (offset + length))

        if offset < PerPartitionOverhead[style]:
            raise P2VEx(
                "partition (%s) offset (%d) less than allowed minimum (%d)" % \
                (style, offset, PerPartitionOverhead[style]))

        if length <= 0:
            raise P2VEx("partition length less than or equal to zero")

        self.style = style
        self.identity = identity
        self.offset = offset
        self.length = length
        self.volume = volume
        self.alignment = alignment

    def congruent(self, other):
        """
      Whether this partition is of the same type, and thus compatible with
      another partition. A negative result implies that these partitions are
      not part of the same disk. This function's primary intended use is sanity
      checking within the implementation of Partition.
      """
        if self.identity is None:
            return True

        return self.identity.congruent(other.identity)

    def precedes(self, other):
        return self.offset + self.length <= \
               other.offset - PerPartitionOverhead[other.style]

    def succeeds(self, other):
        return self.offset >= other.offset + other.length

    def get_device(self):
        if self.volume is None:
            return None
        return self.volume.get_device()

    def is_boot_partition(self):
        if self.volume is None:
            return False
        return self.volume.is_system_drive()

    def volume_name(self):
        if self.volume is None:
            raise P2VEx("partition has no volume")
        return self.volume.name()

    def encode(self):
        return \
            {
                "offset": self.offset,
                "length": self.length,
                "style": self.style,
                "identity": self.identity.encode() \
                    if self.identity is not None else None,
                "volume": self.volume.encode() \
                    if self.volume is not None else None,
                "alignment": self.alignment
            }

    @staticmethod
    def Decode(encoded):
        offset = encoded['offset']
        length = encoded['length']
        style = encoded['style']
        alignment = encoded['alignment']
        identity = Id.Decode(encoded['identity'])
        volume = Volume.Decode(encoded['volume'])
        return Partition(
            offset, length,
            style=style,
            identity=identity,
            volume=volume,
            alignment=alignment)

    def __eq__(self, other):
        return self.offset == other.offset and \
               self.length == other.length and \
               self.style == other.style and \
               self.identity == other.identity and \
               self.volume == other.volume and \
               self.alignment == other.alignment

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "Partition { %d, %d, %s, %s, %s }" % (
            self.offset, self.length, self.style,
            repr(self.identity), repr(self.volume))

    @staticmethod
    def CheckSanity(partitions):
        if not partitions:
            return True

        extended = partitions[0].style == PartitionStyle.Extended
        logical = partitions[0].style == PartitionStyle.Logical
        for i in range(len(partitions) - 1):
            if not partitions[i].congruent(partitions[i + 1]):
                log.debug("partitions are not congruent")
                return False
            if not partitions[i].precedes(partitions[i + 1]):
                log.debug("partition offset / length mismatch detected")
                return False
            if partitions[i + 1].style == PartitionStyle.Extended:
                if extended:
                    log.debug("multiple extended partitions given")
                    return False
                extended = True
            next_logical = partitions[i + 1].style == PartitionStyle.Logical
            if next_logical != logical:
                log.debug("logical and nonlogical partitions given")
                return False

        return True

    @staticmethod
    def CheckBounds(start, end, partitions):
        if not Partition.CheckSanity(partitions):
            raise P2VEx("partitions are not sane")
        if not partitions:
            raise P2VEx("empty partition list")
        return \
            partitions[0].offset >= start and \
            partitions[-1].offset + partitions[-1].length <= end
