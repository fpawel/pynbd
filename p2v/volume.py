import logging
import os

from .identity import Id
from . import P2VEx

log = logging.getLogger(__name__)


class VolumeRole:
    def __init__(self, system, boot):
        self.system = system
        self.boot = boot

    def encode(self):
        return \
            {
                'system': self.system,
                'boot': self.boot
            }

    @staticmethod
    def Decode(encoded):
        return VolumeRole(encoded['system'], encoded['boot'])

    def __repr__(self):
        return "VolumeRole { %s, %s }" % (self.system, self.boot)

    def __eq__(self, other):
        if other is None:
            return False
        return self.system == other.system and \
               self.boot == other.boot


class Volume:

    def __init__(self, guid,
                 drive=None,
                 role=VolumeRole(False, False),
                 identity=None,
                 ):
        self.guid = guid
        self.drive = drive
        self.role = role
        self.identity = identity
        self.device = None
        self.streamid = None

    def __eq__(self, other):
        return self.guid == other.guid and \
               self.drive == other.drive and \
               self.role == other.role and \
               self.identity == other.identity

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "Volume { %s, %s, %s, %s }" % \
               (self.guid, self.drive, repr(self.role), repr(self.identity))

    def name(self):
        return self.guid

    def guid_bytes(self):
        return bytearray(self.guid.translate(None, '{-}').decode("hex"))

    def is_system_drive(self):
        return self.role.system

    def add_device(self, device):
        '''
      if os.path.basename(device.path) != self.guid:
         raise P2VEx("name mismatch: path (%s), volume (%s)" % \
                     (device.path, self.guid))
      '''
        self.device = device

    def get_device(self):
        return self.device

    def encode(self):
        return \
            {
                "guid": self.guid,
                "drive": self.drive,
                "role": self.role.encode(),
                "identity": self.identity.encode() if
                self.identity is not None else None
            }

    @staticmethod
    def Decode(encoded):
        if encoded is None:
            return None
        guid = encoded['guid']
        drive = encoded['drive']
        role = VolumeRole.Decode(encoded['role'])
        identity = Id.Decode(encoded['identity'])
        return Volume(guid, drive=drive, role=role, identity=identity)

    @staticmethod
    def GetVolumeByGuid(guid, volumes):
        for volume in volumes:
            if volume.guid == guid:
                return volume
        return None

    @staticmethod
    def GetVolumeByGuid(guid, volumes):
        for volume in volumes:
            if volume.guid == guid:
                return volume
        return None
