from p2v import P2VEx

def Sectors (bytecount):
   if bytecount % 512 != 0:
      raise P2VEx ("bytes not a multiple of sector size")
   return bytecount // 512

def SectorBytes (sectors):
   return sectors * 512

def CheckSectorAligned(offset):
   return offset % 512 == 0
