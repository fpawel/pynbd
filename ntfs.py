import re
import os
import subprocess
import props


class Ntfs3gError(Exception):
    """generic ntfs3g error"""
    pass


class NotNtfsError(Ntfs3gError):
    """not an NTFS filesystem"""
    pass


_volume_info_strings = {
    "bytes per sector": "bytes_per_sector",
    "bytes per cluster": "bytes_per_cluster",
    "sectors per cluster": "sectors_per_cluster",
    "bytes per volume": "bytes_per_volume",
    "sectors per volume": "sectors_per_volume",
    "clusters per volume": "clusters_per_volume",
    "initialized mft records": "initialized_mft_records",
    "mft records in use": "mft_records_in_use",
    "mft records percentage": "mft_records_percentage",
    "bytes of free space": "bytes_of_free_space",
    "sectors of free space": "sectors_of_free_space",
    "clusters of free space": "clusters_of_free_space",
    "percentage free space": "percentage_free_space",
    "bytes of user data": "bytes_of_user_data",
    "sectors of user data": "sectors_of_user_data",
    "clusters of user data": "clusters_of_user_data",
    "percentage user data": "percentage_user_data",
    "bytes of metadata": "bytes_of_metadata",
    "sectors of metadata": "sectors_of_metadata",
    "clusters of metadata": "clusters_of_metadata",
    "percentage metadata": "percentage_metadata"
}
_volume_info_rx = re.compile(r"(.+?)\s+: (\d+)")


def _parse_volume_info_output(output):
    lines_ = list(filter(None, output.split("\n")))
    info_ = dict()
    for line_ in lines_:
        text_, value_ = match_line(_volume_info_rx, line_)
        info_[_volume_info_strings[text_]] = int(value_)
    return props.props(**info_)


def get_ntfs_volume_info(device, force=False):
    ntfsvolume_binary_path = os.path.abspath(
        os.path.join(
            os.path.realpath(__file__),
            os.pardir,
            "extern", "ntfsvolume.axcient"
        )
    )

    args_ = [ntfsvolume_binary_path, device]
    if force:
        args_.append("--force")
    p_ = subprocess.Popen(
        args_, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    (output_, errput_) = p_.communicate()
    returncode_ = p_.wait()
    if returncode_ != 0:
        message_ = 'ntfsvolume.axcient failed: "%s"' % errput_.decode()
        if b"NTFS signature is missing." in errput_:
            raise NotNtfsError(message_)
        else:
            raise Ntfs3gError(message_)
    return _parse_volume_info_output(output_.decode())


class MatchException(Exception):
    def __init__(self, pattern, line):
        super().__init__(
            'unrecognized line: regex="%s", line="%s"' %
            (pattern, line))


def match_line(regex, line):
    m_ = re.match(regex, line)
    if not m_:
        raise MatchException(regex.pattern, line)
    return m_.groups()
