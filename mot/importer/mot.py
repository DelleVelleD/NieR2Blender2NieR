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
#   Record:      represents a group of value changes for one bone (bayoMotItem_t in bayonetta_pc)
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
#  -Bone indexes found in motion files are absolute bone index and need to be converted for each model with a table
#   given in the model file. Bone -1 is parent bone, which is useful if the motion displaces a character for example.
#  -Motion files use a special type of half floats that will be referenced as pghalf 
#   (thanks Alquazar): they are IEEE floats with 1 bit sign, 6 bit exponent, 9 bit significand and 
#   a bias of 47.
#  -This is not written with endianness or non-Nier:Automata games in mind.
#  -Rotation values are in radians.

#TODO(delle) remove this before pull request
#from NieR2Blender2NieR.mot.importer.mot import *
#mot = MOT("E:\\NierA\\unpacked\\data016.cpk_unpacked\\pl\\nier2blender_extracted\\pl0500.dat\\pl1040_0014.mot")

import os, struct
from ...utils.ioUtils import read_int8, read_uint8, read_int16, read_uint16, read_uint16_be, read_uint32, read_pghalf, read_float, read_string
from ...wmb.importer.wmb import WMB3

class MOT(object):
	def __init__(self, mot_path:str):
		super(MOT, self).__init__()
		self.filepath = mot_path # for external error messaging

		# open file
		mot_file = None
		if os.path.exists(mot_path):
			mot_file = open(mot_path, 'rb')
		else:
			print("[MOT-Error] File does not exist at '%s'." % mot_path)
			return

		# parse MOT header
		self.magic          = mot_file.read(4)
		if self.magic != b'mot\0':
			print("[MOT-Error] %s is not a valid MOT file." % mot_path)
			return
		self.hash           = read_uint32(mot_file)
		self.flags          = read_uint16(mot_file)
		self.frame_count    = read_int16(mot_file)
		self.records_offset = read_uint32(mot_file)
		self.records_count  = read_uint32(mot_file)
		self.unknown        = read_uint32(mot_file) # usually 0 or 0x003c0000, maybe two uint16
		self.name           = read_string(mot_file) # found at most 12 bytes with terminating 0
		print("MOT:")
		print("  hash:          ", self.hash)
		print("  flags:         ", self.flags)
		print("  frame_count:   ", self.frame_count)
		print("  records_offset:", self.records_offset)
		print("  records_count: ", self.records_count)
		print("  unknown:       ", self.unknown)
		print("  name:          ", self.name)

		# parse MOT records
		self.records = []
		for i in range(self.records_count):
			print("  Record %d:" % len(self.records))
			mot_file.seek(self.records_offset + 12*i)
			self.records.append(MOT_Record(mot_file, self))
			print("    frames:", self.records[-1].frames)

		mot_file.close()
	#def __init__()
#class MOT

class MOT_Record(object):
	def __init__(self, mot_file:str, mot:MOT):
		super(MOT_Record, self).__init__()
		self.offset = mot_file.tell()
		self.frames = []

		######################
		#### PARSE HEADER ####
		######################

		self.bone_index  = read_int16(mot_file)
		self.value_type  = read_int8(mot_file)  # 0-2 translationXYZ, 3-5 rotationXYZ, 7-9 scalingXYZ (bayoMotItem_t::index)
		self.record_type = read_int8(mot_file)  # (bayoMotItem_t::flag)
		self.value_count = read_int16(mot_file) # (bayoMotItem_t::elem_number)
		self.unknown     = read_int16(mot_file) # always -1
		print("    offset:     ", self.offset)
		print("    bone_index: ", self.bone_index)
		print("    value_type: ", self.value_type)
		print("    record_type:", self.record_type)
		print("    value_count:", self.value_count)
		print("    unknown:    ", self.unknown)

		# only found on terminator (bone index 0x7fff)
		if self.record_type == -1:
			return

		# constant value for each frame
		# value: p
		if self.record_type == 0:
			# parse file
			self.p = read_float(mot_file)
			print("      p:", self.offset)
			
			# generate frames
			for frame_index in range(mot.frame_count):
				self.frames.append(self.p)

			return

		# seek to values if not 0 or -1 (last 4 bytes of record are offset)
		self.values_offset = self.offset + read_uint32(mot_file)
		mot_file.seek(self.values_offset)

		######################
		#### PARSE VALUES ####
		######################

		# Usually one value per frame
		# Missing values should repeat the last one.
		if self.record_type == 1:
			# parse file
			self.values = []
			for i in range(self.value_count):
				print("      value %d:" % len(self.values))
				self.values.append(MOT_Value())
				self.values[-1].offset = mot_file.tell()
				self.values[-1].p      = read_float(mot_file) # value
				print("        p:", self.values[-1].p)
			
			# generate frames
			for frame_index in range(mot.frame_count):
				if frame_index < len(self.values):
					self.frames.append(self.values[value_index].p)
				else:
					self.frames.append(self.values[         -1].p)

			return
		
		# Same as 1 but with quantized data
		# value: p + dp * cp
		if self.record_type == 2:
			# parse file
			self.p      = read_float(mot_file) # value
			self.dp     = read_float(mot_file) # value delta
			print("      p: ", self.p)
			print("      dp:", self.dp)
			self.values = []
			for i in range(self.value_count):
				print("      value%d:" % len(self.values))
				self.values.append(MOT_Value())
				self.values[-1].offset = mot_file.tell()
				self.values[-1].cp     = read_uint16(mot_file) # value quantum
				print("        cp:", self.values[-1].cp)
			
			# generate frames
			for frame_index in range(mot.frame_count):
				if frame_index >= len(self.values):
					self.frames.append(self.p + (self.dp * self.values[-1].cp))
				else:
					self.frames.append(self.p + (self.dp * self.values[frame_index].cp))
			
			return
		
		# Same as 2 but with reduced precision
		if self.record_type == 3:
			# parse file
			self.p      = read_pghalf(mot_file) #value
			self.dp     = read_pghalf(mot_file) #value delta
			print("      p:  ", self.p)
			print("      dp: ", self.dp)
			self.values = []
			for i in range(self.value_count):
				print("      value %d:" % len(self.values))
				self.values.append(MOT_Value())
				self.values[-1].offset = mot_file.tell()
				self.values[-1].cp     = read_uint8(mot_file) # value quantum
				print("        cp:", self.values[-1].cp)
			
			# generate frames
			for frame_index in range(mot.frame_count):
				if frame_index >= len(self.values):
					self.frames.append(self.p + (self.dp * self.values[-1].cp))
				else:
					self.frames.append(self.p + (self.dp * self.values[frame_index].cp))
			
			return
		
		# Spline coeffs values at key point index (hermit interpolated values)
		# value: p
		# incoming derivative: m0
		# outcoming derivative: m1
		# Missing ranges before or after should repeat the first or last value.
		if self.record_type == 4:
			# parse file
			self.values = []
			for i in range(self.value_count):
				print("      value %d:" % len(self.values))
				self.values.append(MOT_Value())
				self.values[-1].offset = mot_file.tell()
				self.values[-1].index  = read_uint16(mot_file) # absolute frame index
				self.values[-1].dummy  = read_uint16(mot_file) # dummy, probably for alignment
				self.values[-1].p      = read_float(mot_file)  # value
				self.values[-1].m0     = read_float(mot_file)  # incoming derivative
				self.values[-1].m1     = read_float(mot_file)  # outgoing derivative
				print("        offset:", self.values[-1].offset)
				print("        index: ", self.values[-1].index)
				print("        dummy: ", self.values[-1].dummy)
				print("        p:     ", self.values[-1].p)
				print("        m0:    ", self.values[-1].m0)
				print("        m1:    ", self.values[-1].m1)
			
			# generate frames
			frame_index = 0
			while frame_index <= self.values[0].index:
				self.frames.append(self.values[0].p)
				frame_index += 1
			for value_index in range(1, len(self.values)):
				p0 = self.values[value_index-1].p
				p1 = self.values[value_index  ].p
				m0 = self.values[value_index-1].m1
				m1 = self.values[value_index  ].m0
				while frame_index <= self.values[value_index].index:
					t = 1.0 * (frame_index - self.values[value_index-1].index) / (self.values[value_index].index - self.values[value_index-1].index)
					f = (2*t*t*t - 3*t*t + 1)*p0 + (t*t*t - 2*t*t + t)*m0 + (-2*t*t*t + 3*t*t)*p1 + (t*t*t - t*t)*m1
					self.frames.append(f)
					frame_index += 1
			last_frame = self.frames[-1]
			while frame_index < mot.frame_count:
				self.append(last_frame)
				frame_index += 1
			
			return
		
		# Same as 4 but with quantized values
		# value: p + dp * cp
		# incoming derivative: m0 + dm0 * cm0
		# outcoming derivative: m1 + dm1 * cm1
		# Missing ranges before or after should repeat the first or last value.
		if self.record_type == 5:
			# parse file
			self.p      = read_float(mot_file) # value
			self.dp     = read_float(mot_file) # value delta
			self.m0     = read_float(mot_file) # incoming derivative value
			self.dm0    = read_float(mot_file) # incoming derivative value delta
			self.m1     = read_float(mot_file) # outgoing derivative value
			self.dm1    = read_float(mot_file) # outgoing derivative value delta
			print("      p:  ", self.p)
			print("      dp: ", self.dp)
			print("      m0: ", self.m0)
			print("      dm0:", self.dm0)
			print("      m1: ", self.m1)
			print("      dm1:", self.dm1)
			self.values = []
			for i in range(self.value_count):
				print("      value %d:" % len(self.values))
				self.values.append(MOT_Value())
				self.values[-1].offset = mot_file.tell()
				self.values[-1].index  = read_uint16(mot_file) # ABSOLUTE frame index
				self.values[-1].cp     = read_uint16(mot_file) # value quantum
				self.values[-1].cm0    = read_uint16(mot_file) # incoming derivative quantum
				self.values[-1].cm1    = read_uint16(mot_file) # outgoing derivative quantum
				print("        offset:", self.values[-1].offset)
				print("        index: ", self.values[-1].index)
				print("        cp:    ", self.values[-1].cp)
				print("        cm0:   ", self.values[-1].cm0)
				print("        cm1:   ", self.values[-1].cm1)
			
			# generate frames
			frame_index = 0
			first_frame = self.p + (self.dp * self.values[0].cp)
			while frame_index <= self.values[0].index:
				self.frames.append(first_frame)
				frame_index += 1
			for value_index in range(1, len(self.values)):
				p0 = self.p  + (self.dp  * self.values[value_index-1].cp)
				p1 = self.p  + (self.dp  * self.values[value_index  ].cp)
				m0 = self.m1 + (self.dm1 * self.values[value_index-1].cm1)
				m1 = self.m0 + (self.dm0 * self.values[value_index  ].cm0)
				while frame_index <= self.values[value_index].index:
					t = 1.0 * (frame_index - self.values[value_index-1].index) / (self.values[value_index].index - self.values[value_index-1].index)
					f = (2*t*t*t - 3*t*t + 1)*p0 + (t*t*t - 2*t*t + t)*m0 + (-2*t*t*t + 3*t*t)*p1 + (t*t*t - t*t)*m1
					self.frames.append(f)
					frame_index += 1
			last_frame = self.frames[-1]
			while frame_index < mot.frame_count:
				self.append(last_frame)
				frame_index += 1
			
			return
		
		# Same as 5 but with reduced precision
		if self.record_type == 6:
			# parse file
			self.p      = read_pghalf(mot_file) # value
			self.dp     = read_pghalf(mot_file) # value delta
			self.m0     = read_pghalf(mot_file) # incoming derivative value
			self.dm0    = read_pghalf(mot_file) # incoming derivative value delta
			self.m1     = read_pghalf(mot_file) # outgoing derivative value
			self.dm1    = read_pghalf(mot_file) # outgoing derivative value delta
			print("      p:  ", self.p)
			print("      dp: ", self.dp)
			print("      m0: ", self.m0)
			print("      dm0:", self.dm0)
			print("      m1: ", self.m1)
			print("      dm1:", self.dm1)
			self.values = []
			for i in range(self.value_count):
				print("      value %d:" % len(self.values))
				self.values.append(MOT_Value())
				self.values[-1].offset = mot_file.tell()
				self.values[-1].index  = read_uint8(mot_file) # ABSOLUTE frame index
				self.values[-1].cp     = read_uint8(mot_file) # value quantum
				self.values[-1].cm0    = read_uint8(mot_file) # incoming derivative quantum
				self.values[-1].cm1    = read_uint8(mot_file) # outgoing derivative quantum
				print("        offset:", self.values[-1].offset)
				print("        index: ", self.values[-1].index)
				print("        cp:    ", self.values[-1].cp)
				print("        cm0:   ", self.values[-1].cm0)
				print("        cm1:   ", self.values[-1].cm1)
			
			# generate frames
			frame_index = 0
			first_frame = self.p + (self.dp * self.values[0].cp)
			while frame_index <= self.values[0].index:
				self.frames.append(first_frame)
				frame_index += 1
			for value_index in range(1, len(self.values)):
				p0 = self.p  + (self.dp  * self.values[value_index-1].cp)
				p1 = self.p  + (self.dp  * self.values[value_index  ].cp)
				m0 = self.m1 + (self.dm1 * self.values[value_index-1].cm1)
				m1 = self.m0 + (self.dm0 * self.values[value_index  ].cm0)
				while frame_index <= self.values[value_index].index:
					t = 1.0 * (frame_index - self.values[value_index-1].index) / (self.values[value_index].index - self.values[value_index-1].index)
					f = (2*t*t*t - 3*t*t + 1)*p0 + (t*t*t - 2*t*t + t)*m0 + (-2*t*t*t + 3*t*t)*p1 + (t*t*t - t*t)*m1
					self.frames.append(f)
					frame_index += 1
			last_frame = self.frames[-1]
			while frame_index < mot.frame_count:
				self.append(last_frame)
				frame_index += 1
			
			return
		
		# Same as 6 but with relative frame index
		if self.record_type == 7:
			# parse file
			self.p      = read_pghalf(mot_file) # value
			self.dp     = read_pghalf(mot_file) # value delta
			self.m0     = read_pghalf(mot_file) # incoming derivative value
			self.dm0    = read_pghalf(mot_file) # incoming derivative value delta
			self.m1     = read_pghalf(mot_file) # outgoing derivative value
			self.dm1    = read_pghalf(mot_file) # outgoing derivative value delta
			print("      p:  ", self.p)
			print("      dp: ", self.dp)
			print("      m0: ", self.m0)
			print("      dm0:", self.dm0)
			print("      m1: ", self.m1)
			print("      dm1:", self.dm1)
			self.values = []
			for i in range(self.value_count):
				print("      value %d:" % len(self.values))
				self.values.append(MOT_Value())
				self.values[-1].offset = mot_file.tell()
				self.values[-1].index  = read_uint8(mot_file) # RELATIVE frame index
				self.values[-1].cp     = read_uint8(mot_file) # value quantum
				self.values[-1].cm0    = read_uint8(mot_file) # incoming derivative quantum
				self.values[-1].cm1    = read_uint8(mot_file) # outgoing derivative quantum
				print("        offset:", self.values[-1].offset)
				print("        index: ", self.values[-1].index)
				print("        cp:    ", self.values[-1].cp)
				print("        cm0:   ", self.values[-1].cm0)
				print("        cm1:   ", self.values[-1].cm1)
			
			# generate frames
			frame_index = 0
			first_frame = self.p + (self.dp * self.values[0].cp)
			while frame_index <= self.values[0].index:
				self.frames.append(first_frame)
				frame_index += 1
			for value_index in range(1, len(self.values)):
				p0 = self.p  + (self.dp  * self.values[value_index-1].cp)
				p1 = self.p  + (self.dp  * self.values[value_index  ].cp)
				m0 = self.m1 + (self.dm1 * self.values[value_index-1].cm1)
				m1 = self.m0 + (self.dm0 * self.values[value_index  ].cm0)
				while frame_index <= (frame_index - 1 + self.values[value_index].index): # different from 6
					t = 1.0 / self.values[value_index].index # different from 6
					f = (2*t*t*t - 3*t*t + 1)*p0 + (t*t*t - 2*t*t + t)*m0 + (-2*t*t*t + 3*t*t)*p1 + (t*t*t - t*t)*m1
					self.frames.append(f)
					frame_index += 1
			last_frame = self.frames[-1]
			while frame_index < mot.frame_count:
				self.append(last_frame)
				frame_index += 1
			
			return
		
		# Same as 6 but with a BE uint16 frame index
		if self.record_type == 8:
			# parse file
			self.p      = read_pghalf(mot_file) # value
			self.dp     = read_pghalf(mot_file) # value delta
			self.m0     = read_pghalf(mot_file) # incoming derivative value
			self.dm0    = read_pghalf(mot_file) # incoming derivative value delta
			self.m1     = read_pghalf(mot_file) # outgoing derivative value
			self.dm1    = read_pghalf(mot_file) # outgoing derivative value delta
			print("      p:  ", self.p)
			print("      dp: ", self.dp)
			print("      m0: ", self.m0)
			print("      dm0:", self.dm0)
			print("      m1: ", self.m1)
			print("      dm1:", self.dm1)
			self.values = []
			for i in range(self.value_count):
				print("      value %d:" % len(self.values))
				self.values.append(MOT_Value())
				self.values[-1].offset = mot_file.tell()
				self.values[-1].index  = read_uint16_be(mot_file) # ABSOLUTE frame index (big endian order)
				self.values[-1].cp     = read_uint8(mot_file)     # value quantum
				self.values[-1].cm0    = read_uint8(mot_file)     # incoming derivative quantum
				self.values[-1].cm1    = read_uint8(mot_file)     # outgoing derivative quantum
				print("        offset:", self.values[-1].offset)
				print("        index: ", self.values[-1].index)
				print("        cp:    ", self.values[-1].cp)
				print("        cm0:   ", self.values[-1].cm0)
				print("        cm1:   ", self.values[-1].cm1)
			
			# generate frames
			frame_index = 0
			first_frame = self.p + (self.dp * self.values[0].cp)
			while frame_index <= self.values[0].index:
				self.frames.append(first_frame)
				frame_index += 1
			for value_index in range(1, len(self.values)):
				p0 = self.p  + (self.dp  * self.values[value_index-1].cp)
				p1 = self.p  + (self.dp  * self.values[value_index  ].cp)
				m0 = self.m1 + (self.dm1 * self.values[value_index-1].cm1)
				m1 = self.m0 + (self.dm0 * self.values[value_index  ].cm0)
				while frame_index <= self.values[value_index].index:
					t = 1.0 * (frame_index - self.values[value_index-1].index) / (self.values[value_index].index - self.values[value_index-1].index)
					f = (2*t*t*t - 3*t*t + 1)*p0 + (t*t*t - 2*t*t + t)*m0 + (-2*t*t*t + 3*t*t)*p1 + (t*t*t - t*t)*m1
					self.frames.append(f)
					frame_index += 1
			last_frame = self.frames[-1]
			while frame_index < mot.frame_count:
				self.append(last_frame)
				frame_index += 1
			
			return
		
		print("[MOT-Error] Unhandled record type %d for the record at offset 0x%s." % (self.record_type, hex(self.offset)))
	#def __init__()

	# MotionBayo.h::Model_Bayo_DecodeMotionIndex()
	def absolute_bone_index(self, translate_table, bone_count:int) -> int:
		if self.bone_index == -1: return bone_count
		index = translate_table[ (self.bone_index >> 8) & 0xf]
		if index == -1: return 0x0fff
		index = translate_table[((self.bone_index >> 4) & 0xf) + index]
		if index == -1: return 0x0fff
		index = translate_table[ (self.bone_index       & 0xf) + index]
		return index
	#def absolute_bone_index()
#class MOT_Record

class MOT_Value(object):
	pass
#class MOT_Value

if __name__ == '__main__': pass