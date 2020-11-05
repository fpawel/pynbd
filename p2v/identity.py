from p2v import P2VEx
import binascii
import ctypes
import logging
import struct

log = logging.getLogger(__name__)

GptFlavor = 'gpt'

class MbrFlavor:
   partition   = 'mbr.partition'
   disk        = 'mbr.disk'

class Id:

   def __init__(self, flavor, identity):
      self.flavor = flavor
      self.identity = identity

   def __eq__(self, other):
      if other is None:
         return False
      if self.flavor != other.flavor:
         return False
      return self.identity == other.identity

   def __ne__(self, other):
      return not (self == other)

   def __repr__(self):
      return "Id { %s: %s }" % (self.flavor, self.identity.__repr__())

   def buf(self):
      return self.identity

   def is_mbr(self):
      return self.flavor == MbrFlavor.partition or \
         self.flavor == MbrFlavor.disk

   def is_gpt(self):
      return self.flavor == GptFlavor

   def encode(self):
      return "%s/%s" % (self.flavor, binascii.hexlify(self.identity).decode())

   @staticmethod
   def Decode (encoded):

      if encoded is None:
         return None

      flavor, encoded_identity = encoded.split("/")
      identity = bytearray(binascii.unhexlify(encoded_identity))

      if (flavor == MbrFlavor.partition):
         return MbrPartitionId (identity)
      elif (flavor == MbrFlavor.disk):
         return MbrDiskId (identity)
      elif (flavor == GptFlavor):
         return GptId (identity)

      raise P2VEx ("unrecognised flavor")

class GptId (Id, object):

   @staticmethod
   def Length ():
      return 16

   def __init__ (self, identity):
      if len(identity) != GptId.Length():
         raise P2VEx ("GPT GUID has incorrect length")
      Id.__init__(self, GptFlavor, identity)

   def congruent (self, other):
      if other is None:
         return True
      return len(self.identity) == len(other.identity)

   def guid (self):
      return BytesToCanonicalFormatGuid(self.buf())

   def __eq__ (self, other):
      return super(GptId, self).__eq__(other)

GptDiskId = GptId
GptPartitionId = GptId

class MbrPartitionId (Id, object):
   """
   An MbrPartitionId encapsulates a Windows-style partition identity in an
   MBR formatted disk. The partition identity itself is a 12-byte quantity.
   The first 4 bytes are the disk's MBR signature; and the last 8 bytes are
   the partition's offset in the disk.
   """

   @staticmethod
   def Length ():
      return 12

   def __init__ (self, identity):

      if len(identity) != MbrPartitionId.Length():
         raise P2VEx ("MBR ID has incorrect length")

      Id.__init__(self, MbrFlavor.partition, identity)

   def congruent (self, other):

      if other is None:
         return True

      if len(other.identity) != MbrPartitionId.Length() and \
         len(other.identity) != MbrDiskId.Length():

         return False

      if self.identity[0:4] != other.identity[0:4]:
         return False

      return True;

   def __eq__ (self, other):
      return super(MbrPartitionId, self).__eq__(other)

   def offset(self):
      """
      Unpack the offset part of the partition identity. The last 8 bytes
      of the identity are unpacked as an 8-byte unsigned integer.
      """
      offset, = struct.unpack("Q", self.identity[4:12])
      return offset

   def _set_offset(self, offset):
      self.identity = self.identity[:4] + struct.pack("Q", offset)

   def signature(self):
      """
      Unpack the disk-signature part of the partition identity. The first 4
      bytes of the identity are unpacked as bytes. The signature is only useful
      for comparison; so it's not unpacked as an unsigned integer.
      """
      return bytearray(struct.unpack("BBBB", self.identity[0:4]))

   def _set_signature(self, signature):
      self.identity = signature + self.identity[4:12]

class MbrDiskId (Id, object):

   @staticmethod
   def Length ():
      return 4

   def __init__ (self, identity):

      if len(identity) != MbrDiskId.Length():
         raise P2VEx ("MBR ID has incorrect length")

      Id.__init__(self, MbrFlavor.disk, identity)

   def congruent (self, other):

      if other is None:
         return True

      if len(other.identity) != MbrDiskId.Length() and \
         len(other.identity) != MbrPartitionId.Length():

         return False

      if self.identity != other.identity[0:4]:
         return False

      return True

   def __eq__ (self, other):
      return super(MbrDiskId, self).__eq__(other)

def SignatureToMbrDiskId (signature):
   actual_signature = ctypes.c_uint32(signature)
   log.debug  ("converting signature to mbr Id: %s" % str(actual_signature))

   raw_signature = bytearray(buffer(actual_signature))
   return MbrDiskId(raw_signature)

def BytesToCanonicalFormatGuid (my_bytes):
   """
   Format a GUID string from a GUID in raw (on-disk) form. Layout
   is dash-delimited:
   - little-endian 4-byte word
   - little-endian 4-byte word
   - little-endian 2-byte word
   - 2 bytes
   - 6 bytes
   """
   return (b"%b-%b-%b-%b-%b" % (
      binascii.hexlify(my_bytes[3::-1]),
      binascii.hexlify(my_bytes[5:3:-1]),
      binascii.hexlify(my_bytes[7:5:-1]),
      binascii.hexlify(my_bytes[8:10]),
      binascii.hexlify(my_bytes[10:16]),
   )).decode()

def CanonicalFormatGuidToGptId (guid):
   """
   Create a GptId instance from a GUID string. The GUID string is converted
   into its raw form.
   """
   parts = guid.split('-')
   if len(parts) != 5:
      raise P2VEx ("incorrect guid format")

   first_long     = int(parts[0], 16)
   second_short   = int(parts[1], 16)
   third_short    = int(parts[2], 16)
   fourth_bytes   = bytearray.fromhex(parts[3])
   fifth_bytes    = bytearray.fromhex(parts[4])

   trailing_bytes =  tuple(byte for byte in fourth_bytes) + \
                     tuple(byte for byte in fifth_bytes)
   packed = struct.pack("<IHHBBBBBBBB", first_long, second_short, third_short,
                        *trailing_bytes)
   unpacked = struct.unpack("<BBBBBBBBBBBBBBBB", packed)
   return GptId(bytearray(unpacked))
