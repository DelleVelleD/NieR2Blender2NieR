# References:
#   https://github.com/Kerilk/bayonetta_tools/wiki/Motion-Formats-(mot-files)
#   https://github.com/Kerilk/bayonetta_tools/blob/master/binary_templates/Nier%20Automata%20mot.bt
#   https://github.com/Kerilk/bayonetta_tools/blob/master/lib/bayonetta/mot.rb
#   https://github.com/Kerilk/noesis_bayonetta_pc/blob/master/bayonetta_pc/MotionBayo.h
#   https://github.com/lihaochen910/Nier2Blender
#   https://en.wikipedia.org/wiki/Cubic_Hermite_spline
# 
# Terminology:
#   MOT:         motion file
#   Record:      represents one type of value change for one bone (bayoMotItem_t in bayonetta_pc)
#   Value Index: the type of value change to apply to the record's bone
#   Record Type: determines the type of interpolation between keyframes
#   Value:       
#   pghalf:      16bit floating-point number (see notes)
# 
# Record Value Indexes:
#   Nine values per bone and per frame can be encoded (a tenth seems to be possible but is never found) 
#   each is associated to an index (6 is the unused index). These values are:
#   index | value
#   ------|-------
#     0   | translation along axis 0
#     1   | translation along axis 1
#     2   | translation along axis 2
#     3   | rotation around axis 0
#     4   | rotation around axis 1
#     5   | rotation around axis 2
#     7   | scaling along axis 0
#     8   | scaling along axis 1
#     9   | scaling along axis 2
#   When a triplet is not present its default value is used. Translations have parent relative offset
#   as default value. Rotations have 0.0 as default values. Scaling values have a default value of 1.0.
# 
# Notes:
#  -It has to be noted that bone indexes found in motion files are absolute bone index and need to be
#   converted for each model with a table given in the model file. Bone -1 is parent bone, which is 
#   useful if the motion displaces a character for example.
#  -Motion files use a special type of half floats that will be referenced as pghalf 
#   (thanks Alquazar): they are IEEE floats with 1 bit sign, 6 bit exponent, 9 bit significand and 
#   a bias of 47.
#  -This is not written with endianness or non-Nier:Automata games in mind.

import os, struct;
from ...utils.ioUtils import read_int8, read_uint8, read_int16, read_uint16, read_uint32, read_float, read_string;

class MOT(object):
	def __init__(self, mot_path):
		super(MOT, self).__init__();
		self.filepath = mot_path; # for external error messaging

		# open file
		mot_file = None
		if(os.path.exists(mot_path)):
			mot_file = open(mot_path, 'rb');
		else:
			print("[MOT-Error] File does not exist at '%s'." % mot_path);
			return;

		# parse MOT header
		self.magic          = mot_file.read(4);
		if(self.magic != b'mot\0'):
			print("[MOT-Error] %s is not a valid MOT file." % mot_path);
			return;
		self.unknown0x04    = read_uint32(mot_file);
		self.flags          = read_uint16(mot_file);
		self.frame_count    = read_int16(mot_file);
		self.records_offset = read_uint32(mot_file);
		self.records_count  = read_uint32(mot_file);
		self.unknown0x14    = read_uint32(mot_file); # usually 0 or 0x003c0000, maybe two uint16
		self.name           = read_string(mot_file); # found at most 12 bytes with terminating 0

		# parse MOT records
		self.records = [];
		for i in range(self.records_count):
			mot_file.seek(self.records_offset + 12*i);
			self.records.append(MOT_Record(mot_file));

		mot_file.close();
	#def __init__()
#class MOT

class MOT_Record(object):
	def __init__(self, mot_file):
		super(MOT_Record, self).__init__();
		self.offset = mot_file.tell();

		######################
		#### PARSE HEADER ####
		######################

		self.bone_index  = read_uint16(mot_file);
		self.value_index = read_int8(mot_file);  # 0-2 translationXYZ, 3-5 rotationXYZ, 7-9 scalingXYZ (bayoMotItem_t::index)
		self.record_type = read_int8(mot_file);  # (bayoMotItem_t::flag)
		self.value_count = read_int16(mot_file); # (bayoMotItem_t::elem_number)
		self.unknown0x06 = read_int16(mot_file); # always -1

		# only found on terminator (bone index 0x7fff)
		if(self.record_type == -1):
			return;

		# constant value for each frame
		# value: p
		if(self.record_type == 0):	
			self.p = read_float(mot_file);
			return;

		# seek to values if not 0 or -1 (last 4 bytes of record are offset)
		self.values_offset = self.offset + read_uint32(mot_file);
		mot_file.seek(self.values_offset);

		######################
		#### PARSE VALUES ####
		######################

		# Usually one value per frame
		# Missing values should repeat the last one.
		if(self.record_type == 1):
			self.values = [];
			for i in range(self.value_count):
				self.values.append(MOT_Value());
				self.values[-1].offset = mot_file.tell();
				self.values[-1].p      = read_float(mot_file); # value
			return;
		
		# sSame as 1 but with quantized data
		# value: p + dp * cp;
		if(self.record_type == 2):
			self.p      = read_float(mot_file); # value
			self.dp     = read_float(mot_file); # value delta
			self.values = [];
			for i in range(self.value_count):
				self.values.append(MOT_Value());
				self.values[-1].offset = mot_file.tell();
				self.values[-1].cp     = read_uint16(mot_file); # value quantum
				
			return;
		
		# Same as 2 but with reduced precision
		if(self.record_type == 3):
			self.p      = read_pghalf(mot_file); #value
			self.dp     = read_pghalf(mot_file); #value delta
			self.values = [];
			for i in range(self.value_count):
				self.values.append(MOT_Value());
				self.values[-1].offset = mot_file.tell();
				self.values[-1].cp     = read_uint8(mot_file); # value quantum
			return;
		
		# Spline coeffs values at key point index (hermit interpolated values)
		# value: p
		# incoming derivative: m0
		# outcoming derivative: m1
		# Missing ranges before or after should repeat the first or last value.
		if(self.record_type == 4):
			self.values = [];
			for i in range(self.value_count):
				self.values.append(MOT_Value());
				self.values[-1].offset = mot_file.tell();
				self.values[-1].index  = read_uint16(mot_file); # absolute frame index
				self.values[-1].dummy  = read_uint16(mot_file); # dummy, probably for alignment
				self.values[-1].p      = read_float(mot_file);  # value
				self.values[-1].m0     = read_float(mot_file);  # incoming derivative
				self.values[-1].m1     = read_float(mot_file);  # outgoing derivative
			return;
		
		# Same as 4 but with quantized values
		# value: p + dp * cp
		# incoming derivative: m0 + dm0 * cm0
		# outcoming derivative: m1 + dm1 * cm1
		# Missing ranges before or after should repeat the first or last value.
		if(self.record_type == 5):
			self.p      = read_float(mot_file); # value
			self.dp     = read_float(mot_file); # value delta
			self.m0     = read_float(mot_file); # incoming derivative value
			self.dm0    = read_float(mot_file); # incoming derivative value delta
			self.m1     = read_float(mot_file); # outgoing derivative value
			self.dm1    = read_float(mot_file); # outgoing derivative value delta
			self.values = [];
			for i in range(self.value_count):
				self.values.append(MOT_Value());
				self.values[-1].offset = mot_file.tell();
				self.values[-1].index  = read_uint16(mot_file); # ABSOLUTE frame index
				self.values[-1].cp     = read_uint16(mot_file); # value quantum
				self.values[-1].cm0    = read_uint16(mot_file); # incoming derivative quantum
				self.values[-1].cm1    = read_uint16(mot_file); # outgoing derivative quantum
			return;
		
		# Same as 5 with reduced precision
		if(self.record_type == 6):
			self.p      = read_pghalf(mot_file); # value
			self.dp     = read_pghalf(mot_file); # value delta
			self.m0     = read_pghalf(mot_file); # incoming derivative value
			self.dm0    = read_pghalf(mot_file); # incoming derivative value delta
			self.m1     = read_pghalf(mot_file); # outgoing derivative value
			self.dm1    = read_pghalf(mot_file); # outgoing derivative value delta
			self.values = [];
			for i in range(self.value_count):
				self.values.append(MOT_Value());
				self.values[-1].offset = mot_file.tell();
				self.values[-1].index  = read_uint8(mot_file); # ABSOLUTE frame index
				self.values[-1].cp     = read_uint8(mot_file); # value quantum
				self.values[-1].cm0    = read_uint8(mot_file); # incoming derivative quantum
				self.values[-1].cm1    = read_uint8(mot_file); # outgoing derivative quantum
			return;
		
		# Same as 6 but with relative frame index
		if(self.record_type == 7):
			self.p      = read_pghalf(mot_file); # value
			self.dp     = read_pghalf(mot_file); # value delta
			self.m0     = read_pghalf(mot_file); # incoming derivative value
			self.dm0    = read_pghalf(mot_file); # incoming derivative value delta
			self.m1     = read_pghalf(mot_file); # outgoing derivative value
			self.dm1    = read_pghalf(mot_file); # outgoing derivative value delta
			self.values = [];
			for i in range(self.value_count):
				self.values.append(MOT_Value());
				self.values[-1].offset = mot_file.tell();
				self.values[-1].index  = read_uint8(mot_file); # RELATIVE frame index
				self.values[-1].cp     = read_uint8(mot_file); # value quantum
				self.values[-1].cm0    = read_uint8(mot_file); # incoming derivative quantum
				self.values[-1].cm1    = read_uint8(mot_file); # outgoing derivative quantum
			return;
		
		# Same as 7 but with absolute frame index (at least one relative frame index
		# would have been > 255)
		if(self.record_type == 8):
			self.p      = read_pghalf(mot_file); # value
			self.dp     = read_pghalf(mot_file); # value delta
			self.m0     = read_pghalf(mot_file); # incoming derivative value
			self.dm0    = read_pghalf(mot_file); # incoming derivative value delta
			self.m1     = read_pghalf(mot_file); # outgoing derivative value
			self.dm1    = read_pghalf(mot_file); # outgoing derivative value delta
			self.values = [];
			for i in range(self.value_count):
				self.values.append(MOT_Value());
				self.values[-1].offset = mot_file.tell();
				self.values[-1].index  = read_uint16(mot_file); # ABSOLUTE frame index (big endian order)
				self.values[-1].cp     = read_uint8(mot_file); # value quantum
				self.values[-1].cm0    = read_uint8(mot_file); # incoming derivative quantum
				self.values[-1].cm1    = read_uint8(mot_file); # outgoing derivative quantum
			return;
		
		print("[MOT-Error] Unhandled record type %d for the record at offset 0x%s." % (self.record_type, hex(self.offset)));
	#def __init__()
#class MOT_Record

class MOT_Value(object):
	pass;
#class MOT_Value

def read_pghalf(file) -> float:
	C = FloatDecompressor(6,9,47);
	entry = file.read(2);
	return C.decompress(struct.unpack("<H", entry)[0]);
#def read_pghalf

# yoinked from lihaochen910, referenced from Phernost on stackoverflow, FloatDecompressor(6,9,47) for Nier
# https://stackoverflow.com/questions/1659440/32-bit-to-16-bit-floating-point-conversion/3542975#3542975
# F = float32, H = float16
class FloatDecompressor(object):
	significandFBits = 23;
	exponentFBits = 8;
	biasF = 127;
	exponentF = 0x7F800000;
	significandF = 0x007fffff;
	signF = 0x80000000;
	signH = 0x8000;

	def __init__(self, eHBits, sHBits, bH):
		self.exponentHBits = eHBits;
		self.significandHBits = sHBits;
		self.biasH = bH;

		self.exponentH = ((1 << eHBits) - 1) << sHBits;
		self.significandH = (1 << sHBits) - 1;

		self.shiftSign = self.significandFBits + self.exponentFBits - self.significandHBits - self.exponentHBits;
		self.shiftBits = self.significandFBits - self.significandHBits;
	#def __init__()

	def decompress(self, value):
		ui = value;
		sign = ui & self.signH;
		ui ^= sign;

		sign <<= self.shiftSign;
		exponent = ui & self.exponentH;
		significand = ui ^ exponent;
		significand <<= self.shiftBits;

		magic = 1.0;
		si = sign | significand;
		if(exponent == self.exponentH):
			si |= self.exponentF;
		elif(exponent != 0):
			exponent >>= self.significandHBits;
			exponent += self.biasF - self.biasH;
			exponent <<= self.significandFBits;
			si |= exponent;
		elif(significand != 0):
			magic = (2 * self.biasF - self.biasH) << self.significandFBits;
			magic = struct.unpack("<f", struct.pack("<I", magic))[0];
		f = struct.unpack("<f", struct.pack("<I", si))[0];
		f *= magic;
		return f;
	#def decompress()
#class FloatDecompressor

if __name__ == '__main__': pass;