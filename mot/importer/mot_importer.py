import bpy, math, mathutils
from .mot import MOT

def main(mot_path:str):
	# get the armature from the selected WMB
	#TODO this is a temporary thing, make a better interface to loading anims
	armature = None
	for obj in bpy.context.selected_objects:
		#print("[MOT-Info] Selected obj: %s" % obj.name)
		armature_name = obj.name + "Amt"
		if armature_name in bpy.data.armatures:
			armature = bpy.data.armatures[armature_name]
			#print("[MOT-Info] Selected armature: %s" % armature_name)
			break
	if armature == None:
		print("[MOT-Error] armature not found")
		return {'FINISHED'}
	#print("[MOT-Info] armature.name: %s" % armature.name)
	
	# parse the mot file
	mot = MOT(mot_path)
	print("[+] importing motion %s" % mot.name)
	
	# format the mot records into per-bone motion data
	motion_data = {} #{abs_bone_index: (bone_index, POS[Vector], ROT[Euler], SCALE[Vector])}
	for record in mot.records:
		bone_index = record.bone_index(armature['translateTable'])
		if bone_index == 0x0fff:
			return {'FINISHED'}

		bone_data = motion_data.setdefault(record.abs_bone_index, (bone_index, [], [], []))
		for i in range(mot.frame_count):
			if   0 <= record.value_type <= 2: # translation
				if i >= len(bone_data[1]): bone_data[1].append(mathutils.Vector((0,0,0)))
				bone_data[1][i][record.value_type  ] = record.frames[i]
			elif 3 <= record.value_type <= 5: # rotation
				if i >= len(bone_data[2]): bone_data[2].append(mathutils.Euler((0,0,0),'XYZ'))
				bone_data[2][i][record.value_type-3] = record.frames[i] # mathutils.Euler is also in radians
			elif 7 <= record.value_type <= 9: # scale
				if i >= len(bone_data[3]): bone_data[3].append(mathutils.Vector((1,1,1)))
				bone_data[3][i][record.value_type-7] = record.frames[i]
			else:
				print("[MOT-Error] Unknown value index: %d" % record.value_type)
	
	# init the action
	if mot.name in bpy.data.actions:
		bpy.data.actions.remove(bpy.data.actions[mot.name])
	action = bpy.data.actions.new(mot.name)
	action.use_fake_user = True
	action.frame_range = [1, mot.frame_count]
	action.use_frame_range = True
	if armature.animation_data == None:
		armature.animation_data_create()
	armature.animation_data.action = action

	# clear pose data
	bpy.ops.object.mode_set(mode='POSE')
	for bone in bpy.context.view_layer.objects.active.pose.bones:
		bone.location = (0, 0, 0)
		bone.rotation_quaternion = (1, 0, 0, 0)
		bone.rotation_euler = (0, 0, 0)
		bone.scale = (1, 1, 1)
	
	# format the motion data into blender keyframes
	pose_bones = bpy.context.view_layer.objects.active.pose.bones
	for bone_index, pos_frames, rot_frames, scale_frames in motion_data.values():
		bone_name = "bone%d" % bone_index
		pose_bone = pose_bones.get(bone_name)
		if pose_bone == None:
			print("[MOT-Error] '%s' not found in bpy.context.view_layer.objects.active.pose.bones" % bone_name)
			continue

		restore_location = pose_bone.location
		for i,frame_value in enumerate(pos_frames):
			pose_bone.location = -(pose_bone.bone.head - frame_value)
			pose_bone.keyframe_insert('location', index=-1, frame=i+1)
		pose_bone.location = restore_location

		#restore_rotation = pose_bone.rotation_quaternion
		for i,frame_value in enumerate(rot_frames):
			frame_value.x = frame_value.x
			frame_value.y = frame_value.y
			frame_value.z = frame_value.z
			#pose_bone.rotation_quaternion = mathutils.Euler((frame_value.x,frame_value.y,frame_value.z)).to_quaternion()
			#pose_bone.keyframe_insert('rotation_quaternion', index=-1, frame=i+1)
			pose_bone.rotation_euler = frame_value
			pose_bone.rotation_mode  = 'ZXY'
			pose_bone.keyframe_insert('rotation_euler', index=-1, frame=i+1)
		#pose_bone.rotation_quaternion = restore_rotation

		restore_scale = pose_bone.scale
		for i,frame_value in enumerate(scale_frames):
			pose_bone.scale = frame_value
			pose_bone.keyframe_insert('scale', index=-1, frame=i+1)
		pose_bone.scale = restore_scale
		#print("[MOT-Info] Inserted keyframes for %s" % bone_name)
		
	bpy.ops.object.mode_set(mode='OBJECT')
	bpy.data.scenes["Scene"].frame_current = 1
	bpy.data.scenes["Scene"].frame_start   = 1
	bpy.data.scenes["Scene"].frame_end     = mot.frame_count
	return {'FINISHED'}
#def main()