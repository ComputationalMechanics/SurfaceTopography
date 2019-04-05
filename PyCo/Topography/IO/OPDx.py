#
# Copyright 2019 Antoine Sanner
# 
# ### MIT license
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
import numpy as np

from PyCo.Topography.IO.Reader import ReaderBase
from PyCo.Topography import Topography


MAGIC = "VCA DATA\x01\x00\x00\x55"
MAGIC_SIZE = 12

DEKTAK_MATRIX = 0x00          # Too lazy to assign an actual type id?
DEKTAK_BOOLEAN = 0x01         # Takes value 0 and 1
DEKTAK_SINT32 = 0x06
DEKTAK_UINT32 = 0x07
DEKTAK_SINT64 = 0x0a
DEKTAK_UINT64 = 0x0b
DEKTAK_FLOAT = 0x0c           # Single precision float
DEKTAK_DOUBLE = 0x0d          # Double precision float
DEKTAK_TYPE_ID = 0x0e         # Compound type holding some kind of type id
DEKTAK_STRING = 0x12          # Free-form string value
DEKTAK_QUANTITY = 0x13        # Value with units (compound type)
DEKTAK_TIME_STAMP = 0x15      # Datetime (string/9-byte binary)
DEKTAK_UNITS = 0x18           # Units (compound type)
DEKTAK_DOUBLE_ARRAY = 0x40    # Raw data array, in XML Base64-encoded
DEKTAK_STRING_LIST = 0x42     # List of Str
DEKTAK_RAW_DATA = 0x46        # Parent/wrapper tag of raw data
DEKTAK_RAW_DATA_2D = 0x47     # Parent/wrapper tag of raw data
DEKTAK_POS_RAW_DATA = 0x7c    # Base64-encoded positions, not sure how it differs from 64
DEKTAK_CONTAINER = 0x7d       # General nested data structure
DEKTAK_TERMINATOR = 0x7f      # Always the last item. Usually a couple of 0xff bytes inside.

TIMESTAMP_SIZE = 9
UNIT_EXTRA = 12
DOUBLE_ARRAY_EXTRA = 5

MEAS_SETTINGS = "/MetaData/MeasurementSettings"
RAW_1D_DATA = "/1D_Data/Raw"
ANY_2D_DATA = "/2D_Data/"


class OPDxReader(ReaderBase):

    # Reads in the positions of all the data and metadata
    def __init__(self, file_path, size=None, unit=None, info=None):
        super().__init__(size, info)

        with open(file_path, "rb") as f:

            # read in file as hexadecimal
            self.buffer = [chr(byte) for byte in f.read()]

            # length of file
            size = len(self.buffer)

            # check if correct header
            if size < MAGIC_SIZE or ''.join(self.buffer[:MAGIC_SIZE]) != MAGIC:
                raise ValueError('Invalid file format for Dektak OPDx.')

            self.hash_table = dict()
            pos = MAGIC_SIZE
            while pos < size:
                buf, pos, self.hash_table, path = read_item(buf=self.buffer, pos=pos, hash_table=self.hash_table, path="")

    # Gets the actual data and metadata from the previously fetched positions
    def topography(self):
        # TODO: Right now returns all values in m

        channels = find_2d_data(self.hash_table, self.buffer)

        data, metadata = channels['Raw']  # TODO: Metadata currently not used  ----  TODO: return all channels

        # Get size of x and y and multiply with factors to end up with m
        size_x = metadata.pop('Raw::Width value', None)
        x_unit = metadata.pop('Raw::Width unit', None)
        size_x = str_to_factor(x_unit) * size_x

        size_y = metadata.pop('Raw::Height value', None)
        y_unit = metadata.pop('Raw::Height unit', None)
        size_y = str_to_factor(y_unit) * size_y

        if x_unit != y_unit:
            raise ValueError('width and height are not in the same unit.')  # TODO: Accept this?

        size = (size_x, size_y)

        unit = metadata.pop('Raw::z unit', None)
        data *= str_to_factor(unit)

        info = {'unit': 'm'}  # TODO: Bring to common unit and denote here

        return Topography(heights=data, size=size, info=info)


def str_to_factor(unit_str):
    """
    Converts a received unit string to a factor.
    :param unit_str: The input string
    :return:
    A factor as a python float
    """

    # Cut off strange starts. TODO: Check if more different starts that have to be cut
    if unit_str.startswith("Â"):
        unit_str = unit_str[1:]

    if unit_str == 'Ym':
        return 10e24
    elif unit_str == 'Zm':
        return 10e21
    elif unit_str == 'Em':
        return 10e18
    elif unit_str == 'Pm':
        return 10e15
    elif unit_str == 'Tm':
        return 10e12
    elif unit_str == 'Gm':
        return 10e9
    elif unit_str == 'Mm':
        return 10e6
    elif unit_str == 'km':
        return 10e3
    elif unit_str == 'hm':
        return 10e2
    elif unit_str == 'dam':
        return 10e1
    elif unit_str == 'm':
        return 10e0
    elif unit_str == 'dm':
        return 10e-1
    elif unit_str == 'cm':
        return 10e-2
    elif unit_str == 'mm':
        return 10e-3
    elif unit_str == 'µm':
        return 10e-6
    elif unit_str == 'nm':
        return 10e-9
    elif unit_str == 'pm':
        return 10e-12
    elif unit_str == 'fm':
        return 10e-15
    elif unit_str == 'am':
        return 10e-18
    elif unit_str == 'zm':
        return 10e-21
    elif unit_str == 'ym':
        return 10e-24
    else:
        raise ValueError('Unknown unit.')


class DektakItemData:
    def __init__(self):
        self.b = None
        self.ui = None
        self.si = None
        self.uq = None
        self.sq = None
        self.d = None
        self.timestamp = []
        self.buf = None
        self.qun = None
        self.rawpos1d = DektakRawPos1D()
        self.rawpos2d = DektakRawPos2D()
        self.matrix = DektakMatrix()
        self.strlist = None


class DektakItem:
    def __init__(self):
        self.typename = None
        self.typeid = None
        self.data = DektakItemData()


class DektakRawPos1D:
    def __init__(self):
        self.unit = DektakQuantUnit()
        self.divisor = None
        self.count = None
        self.buf = DektakBuf


class DektakRawPos2D:
    def __init__(self):
        self.unitx = DektakQuantUnit()
        self.unity = DektakQuantUnit()
        self.divisorx = None
        self.divisory = None


class DektakQuantUnit:
    def __init__(self):
        self.name = None
        self.symbol = None
        self.value = None
        self.extra = None


class DektakMatrix:
    def __init__(self):
        self.another_name = None
        self.some_int = None
        self.xres = None
        self.yres = None
        self.buf = DektakBuf()


class DektakBuf:
    def __init__(self, position=None, length=None):
        self.position = position
        self.length = length


def find_2d_data_matrix(name, item):
    """ Checks if an item is a matrix and if it is, returns it's channel name.
    :param name: The name (key) of a found item
    :param item: The item itself
    :return: The name of the matrix data channel
    """
    if item.typeid != DEKTAK_MATRIX:
        return
    if name[:9] != ANY_2D_DATA:
        return
    s = 9 + name[9:].find('/')
    if s == -1:
        return
    if not name[s+1:] == "Matrix":
        return
    return name[9:s]


def find_1d_data(hash_table, buf):
    """ THIS HAS NOT BEEN TESTED DUE TO NO FILES WITH 1D DATA AVAILABLE."""

    item = hash_table.pop("/MetaData/MeasurementSettings/SamplesToLog", None)

    if item is None:
        return None
    else:
        raise NotImplementedError


def find_2d_data(hash_table, buf):
    """ Get all the 2d data channels out of the previously filled hash table.

    :param hash_table: The filled hash table
    :param buf: The raw hex data
    :return: Dictionary with all names, data and metadata of the different channels
    """
    output = dict()
    channels = []

    # Get a list of all channels containing 2d data matrices
    for key in hash_table.keys():
        found = find_2d_data_matrix(key, hash_table[key])
        if found is not None:
            channels.append(found)

    for channel in channels:
        meta_data = create_meta(hash_table)

        string = ANY_2D_DATA
        string += channel

        length = len(string)

        # Get position and res of data matrix
        string += "/Matrix"
        item = hash_table[string]
        start = item.data.matrix.buf.p

        end = start + item.data.matrix.buf.length
        xres = item.data.matrix.xres
        yres = item.data.matrix.yres

        meta_data[channel + "::xres"] = xres
        meta_data[channel + "::yres"] = yres

        # TODO: multiply value by interpret(item.data.qun.symbol)
        string = string[:length]
        string += "/Dimension1Extent"
        item = hash_table[string]
        yreal = item.data.qun.value
        yunit = item.data.qun.symbol

        meta_data[channel + "::Height value"] = yreal
        meta_data[channel + "::Height unit"] = yunit

        string = string[:length]
        string += "/Dimension2Extent"
        item = hash_table[string]
        xreal = item.data.qun.value
        xunit = item.data.qun.symbol

        meta_data[channel + "::Width value"] = xreal
        meta_data[channel + "::Width unit"] = xunit

        string = string[:length]
        string += "/DataScale"
        item = hash_table[string]
        q = item.data.qun.value
        zunit = item.data.qun.symbol

        meta_data[channel + "::z scale"] = q
        meta_data[channel + "::z unit"] = zunit

        rawdata = build_matrix(xres=xres, yres=yres, data=buf[start:end], q=q)

        output[channel] = (rawdata, meta_data)
    return output


def create_meta(hash_table):
    """
    Gets all the metadata out of a hash table.
    :param hash_table: The hash table
    :return: Hash table with all metadata names and values
    """
    container = dict()
    for key in hash_table.keys():
        if not key.startswith('/MetaData/'):
            continue
        item = hash_table[key]

        if item.typeid == DEKTAK_BOOLEAN:
            metavalue = item.data.b
        elif item.typeid == DEKTAK_SINT32:
            metavalue = item.data.si
        elif item.typeid == DEKTAK_UINT32:
            metavalue = item.data.ui
        elif item.typeid == DEKTAK_SINT64:
            metavalue = item.data.sq
        elif item.typeid == DEKTAK_UINT64:
            metavalue = item.data.uq
        elif item.typeid == DEKTAK_DOUBLE or item.typeid == DEKTAK_FLOAT:
            metavalue = item.data.d
        elif item.typeid == DEKTAK_STRING:
            metavalue = "".join(item.data.buf)
        elif item.typeid == DEKTAK_QUANTITY:
            metavalue = str(item.data.qun.value) + item.data.qun.symbol
        elif item.typeid == DEKTAK_STRING_LIST:
            metavalue = "; ".join(item.data.strlist)
        elif item.typeid == DEKTAK_TERMINATOR:
            metavalue = None
        else:
            # Not really meta data
            continue
        metakey = key.replace("/", "::")
        container[metakey] = metavalue
    return container


def read_item(buf, pos, hash_table, path, abspos=0):
    """
    Reads in the next item out of the buffer and saves it in the hash table. May recursively call itself for containers.
    :param buf: The raw data buffer
    :param pos: Current position in the buffer
    :param hash_table: The output hash table
    :param path: Current name to save
    :param abspos: Absolute position in buffer to keep track when calling itself
    :return:
    Buffer, new position, hash table with new item in it, new path
    """
    orig_path_len = len(path)
    item = DektakItem()
    itempos = 0
    name, pos = read_name(buf, pos)

    path += '/'
    path += name

    item.typeid, pos = read_with_check(buf, pos, 1)
    item.typeid = ord(item.typeid[0])

    # simple types
    if item.typeid == DEKTAK_BOOLEAN:
        b8, pos = read_with_check(buf, pos, 1)
        if b8 == '\x01':
            item.data.b = True
        elif b8 == '\x00':
            item.data.b = False
        else:
            raise ValueError("Something went wrong.")

    elif item.typeid == DEKTAK_SINT32:
        item.data.si, pos = read_int32(buf, pos, signed=True)

    elif item.typeid == DEKTAK_UINT32:
        item.data.ui, pos = read_int32(buf, pos, signed=False)

    elif item.typeid == DEKTAK_SINT64:
        item.data.sq, pos = read_int64(buf, pos, signed=True)

    elif item.typeid == DEKTAK_UINT64:
        item.data.uq, pos = read_int64(buf, pos, signed=False)

    elif item.typeid == DEKTAK_FLOAT:
        item.data.d, pos = read_float(buf, pos)

    elif item.typeid == DEKTAK_DOUBLE:
        item.data.d, pos = read_double(buf, pos)

    elif item.typeid == DEKTAK_TIME_STAMP:
        time, pos = read_with_check(buf, pos, TIMESTAMP_SIZE)
        item.data.timestamp.append(time)

    elif item.typeid == DEKTAK_STRING:
        item.data.buf, _, pos = read_structured(buf, pos)

    elif item.typeid == DEKTAK_QUANTITY:
        content, _, pos = read_structured(buf, pos)
        item.data.qun, itempos = read_quantunit_content(content, itempos, False)

    elif item.typeid == DEKTAK_UNITS:
        content, _, pos = read_structured(buf, pos)
        item.data.qun, itempos = read_quantunit_content(content, itempos, True)

    elif item.typeid == DEKTAK_TERMINATOR:
        pos = len(buf)

    # Container types.
    elif item.typeid == DEKTAK_CONTAINER or item.typeid == DEKTAK_RAW_DATA or item.typeid == DEKTAK_RAW_DATA_2D:
        content, start, pos = read_structured(buf, pos)  # TODO find out if maybe better place somewhere else
        abspos += start
        while itempos < len(content):
            content, itempos, hash_table, path = read_item(buf=content, pos=itempos, hash_table=hash_table, path=path, abspos= abspos)

    # Types with string type name
    elif item.typeid == DEKTAK_DOUBLE_ARRAY:
        item.typename, item.data.buf, _, pos = read_named_struct(buf, pos)

    elif item.typeid == DEKTAK_STRING_LIST:
        item.typename, content, start, pos = read_named_struct(buf, pos)
        item.data.strlist = []
        while itempos < len(content):
            s, itempos = read_name(content, itempos)
            item.data.strlist.append(s)

    elif item.typeid == DEKTAK_TYPE_ID:
        item.typename, item.data.buf, _, pos = read_named_struct(buf, pos)

    elif item.typeid == DEKTAK_POS_RAW_DATA:
        if path.startswith('/2D_Data'):
            item.typename, content, _, pos = read_named_struct(buf, pos)

            item.data.rawpos2d.unitx, item.data.rawpos2d.divisorx, itempos = \
                read_dimension2d_content(content, itempos, item.data.rawpos2d.unitx)
            item.data.rawpos2d.unity, item.data.rawpos2d.divisory, itempos = \
                read_dimension2d_content(content, itempos, item.data.rawpos2d.unity)

        elif path.startswith('/1_Data'):
            item.typename, content, _, pos = read_named_struct(buf, pos)
            content.position += buf.position

            item.data.rawpos1d.unit, itempos = read_quantunit_content(content, itempos, True)
            item.data.rawpos1d.count, itempos = read_int64(content, itempos)

            item.data.rawpos1d.buf = content
            item.data.rawpos1d.buf.position += itempos
            item.data.rawpos1d.buf.length -= itempos

        else:
            raise ValueError  # TODO check if should assume 1D here like gwyddion

    elif item.typeid == DEKTAK_MATRIX:
        item.typename, pos = read_name(buf, pos)
        item.data.matrix.some_int, pos = read_int32(buf, pos)
        item.data.matrix.another_name, pos = read_name(buf, pos)
        item.data.matrix.buf.length, pos = read_varlen(buf, pos)
        item.data.matrix.yres, pos = read_int32(buf, pos)
        item.data.matrix.xres, pos = read_int32(buf, pos)

        if item.data.matrix.buf.length < 8:  # 2 * sizeof int32
            raise ValueError
        item.data.matrix.buf.length -= 8
        item.data.matrix.buf.p = pos + abspos

        if len(buf) - pos < item.data.matrix.buf.length:
            raise ValueError
        pos += item.data.matrix.buf.length

    else:
        raise ValueError
    hash_table[path] = item
    path = path[:orig_path_len]
    return buf, pos, hash_table, path


def read_quantunit_content(buf, pos, is_unit):
    """
    Reads in a quantity unit: Value, name and symbol.
    :param buf: The buffer
    :param pos: The position in the buffer
    :param is_unit: Whether or not it is a unit
    :return: A quantunit item, filled with value, name and symbol
    """
    quantunit = DektakQuantUnit()
    quantunit.extra = []

    if not is_unit:
        quantunit.value, pos = read_double(buf, pos)

    quantunit.name, pos = read_name(buf, pos)
    quantunit.symbol, pos = read_name(buf, pos)

    if is_unit:
        quantunit.value, pos = read_double(buf, pos)
        res, pos = read_with_check(buf, pos, UNIT_EXTRA)
        quantunit.extra += res

    return quantunit, pos


def read_dimension2d_content(buf, pos, unit):
    """
    Reads in information about a 2d dimension.
    :param buf: The buffer
    :param pos: The position in the buffer
    :param unit: The unit
    :return: The read unit, divisor and new position in the buffer
    """
    unit.value, pos = read_double(buf, pos)
    unit.name, pos = read_name(buf, pos)
    unit.symbol, pos = read_name(buf, pos)
    divisor, pos = read_double(buf, pos)
    unit.extra, pos = read_with_check(buf, pos, UNIT_EXTRA)
    return unit, divisor, pos


def build_matrix(xres, yres, data, q=1):
    """
    Reads a float matrix of given dimensions and multiplies with a scale.
    :param xres: Resolution along x-axis
    :param yres: Resolution along y-axis
    :param data: The raw hex data
    :param q: The scale of the data, a double
    :return: A numpy array, now doubles aswell
    """
    data = ''.join(data)

    # build correct type: 4byte flat, little endian
    dt = np.dtype('f4')  # double
    dt = dt.newbyteorder('<')  # little-endian

    data = np.frombuffer(str.encode(data, "raw_unicode_escape"), dt)
    data = data.copy().reshape((yres, xres))
    data *= q
    return data


def read_name(buf, pos):
    """
    Reads a name.
    :param buf: The buffer
    :param pos: Position in buffer
    :return:
    name, new position in buffer
    """

    length, pos = read_int32(buf, pos)  # Names always have a size of 4 bytes
    if len(buf) < length or pos > len(buf) - length:
        raise ValueError("Some sizes went wrong.")
    position = pos

    name = buf[position:position+length]
    name = "".join(s for s in name)
    pos += length
    return name, pos


def read_structured(buf, pos):
    """
    Reads a length and returns a part of the buffer that long.
    :param buf: The buffer
    :param pos: Position in buffer
    :return:
    The slice of buffer, where it starts and the new position in the buffer
    """
    length, pos = read_varlen(buf, pos)
    if len(buf) < length or pos > len(buf) - length:
        raise ValueError("Some sizes went wrong.")
    start = pos
    pos += length
    return buf[start:start+length], start, pos


def read_named_struct(buf, pos):
    """
    Same as read_structured but there is a name to it.
    :param buf: The buffer
    :param pos: Position in buffer
    :return:
    Name of the buffer, that buffer, its start and the new position in the buffer
    """
    typename, pos = read_name(buf, pos)
    content, start, pos = read_structured(buf, pos)
    return typename, content, start, pos


def read_varlen(buf, pos):
    """
    Reads a length of variable length itself
    :param buf: The buffer
    :param pos: Position in the buffer
    :return:
    The read length and new position in the buffer
    """
    lenlen, pos = read_with_check(buf, pos, 1)
    lenlen = np.frombuffer(str.encode(lenlen, "raw_unicode_escape"), "<u1")[0]
    if lenlen == 1:
        length, pos = read_with_check(buf, pos, 1)
        length = np.frombuffer(str.encode(length, "raw_unicode_escape"), "<u1")[0]
    elif lenlen == 2:
        length, pos = read_int16(buf, pos)
    elif lenlen == 4:
        length, pos = read_int32(buf, pos)
    else:
        raise ValueError
    return length, pos


def read_int64(buf, pos, signed=False):
    """
    Reads a 64bit int.
    :param buf: The buffer
    :param pos: Position in the buffer
    :param signed: Whether of not the int is signed
    :return:
    The int and the new position in the buffer
    """
    out, pos = read_with_check(buf=buf, pos=pos, nbytes=8)
    out = ''.join(out)
    dt = "<i8" if signed else "<u8"
    out = np.frombuffer(str.encode(out, "raw_unicode_escape"), dt)[0]  # interpret hexadecimal -> int (little-endian)
    return out, pos


def read_int32(buf, pos, signed=False):
    """
    Reads a 32bit int.
    :param buf: The buffer
    :param pos: Position in the buffer
    :param signed: Whether of not the int is signed
    :return:
    The int and the new position in the buffer
    """
    out, pos = read_with_check(buf=buf, pos=pos, nbytes=4)
    out = ''.join(out)
    dt = "<i4" if signed else "<u4"
    out = np.frombuffer(str.encode(out, "raw_unicode_escape"), dt)[0]  # interpret hexadecimal -> int (little-endian)
    return out, pos


def read_int16(buf, pos, signed=False):
    """
    Reads a 16bit int.
    :param buf: The buffer
    :param pos: Position in the buffer
    :param signed: Whether of not the int is signed
    :return:
    The int and the new position in the buffer
    """
    out, pos = read_with_check(buf=buf, pos=pos, nbytes=2)
    out = ''.join(out)
    dt = "<i2" if signed else "<u2"
    out = np.frombuffer(str.encode(out, "raw_unicode_escape"), dt)[0]  # interpret hexadecimal -> int (little-endian)
    return out, pos


def read_double(buf, pos):
    """
    Reads a double (64bit)
    :param buf: The buffer
    :param pos: Position in the buffer
    :return:
    The double and the new position in the buffer
    """
    out, pos = read_with_check(buf=buf, pos=pos, nbytes=8)
    out = ''.join(out)
    dt = np.dtype('d')  # double
    dt = dt.newbyteorder('<')  # little-endian
    out = np.frombuffer(str.encode(out, "raw_unicode_escape"), dt)[0]  # interpret hexadecimal -> int (little-endian)
    return out, pos


def read_float(buf, pos):
    """
    Reads a float (32bit)
    :param buf: The buffer
    :param pos: Position in the buffer
    :return:
    The float and the new position in the buffer
    """
    out, pos = read_with_check(buf=buf, pos=pos, nbytes=4)
    out = ''.join(out)
    dt = np.dtype('f')  # double
    dt = dt.newbyteorder('<')  # little-endian
    out = np.frombuffer(str.encode(out, "raw_unicode_escape"), dt)[0]  # interpret hexadecimal -> int (little-endian)
    return out, pos


def read_with_check(buf, pos, nbytes):
    """
    Reads and returns n bytes.
    :param buf: The input buffer
    :param pos: The current position
    :param nbytes: number of bytes to read in
    :return: The bytes and the new position in the buffer
    """

    if len(buf) < nbytes or len(buf) - nbytes < pos:
        raise ValueError("Some sizes went wrong.")

    out = buf[pos:pos+nbytes]
    pos += int(nbytes)

    out = out[0] if nbytes == 1 else out
    return out, pos