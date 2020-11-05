def Kibibytes(number):
    return number * 1024


def Mebibytes(number):
    return Kibibytes(number) * 1024


def Gibibytes(number):
    return Mebibytes(number) * 1024


def Tebibytes(number):
    return Gibibytes(number) * 1024


class AlignedOffset:

    def __init__(self, offset, alignment):
        self.value_ = offset
        self.alignment_ = alignment

    def offset(self):
        return self.value_ - self.value_ % self.alignment_

    def previous(self):
        return self.offset() - self.alignment_

    def __next__(self):
        return self.offset() + self.alignment_

    def is_aligned(self):
        return self.value_ % self.alignment_ == 0
