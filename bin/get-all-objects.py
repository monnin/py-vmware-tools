#!/usr/bin/env python3

import sys
import os

#
#	This script outputs a list of ALL (managed) objects from one VCSA cluster into
#	a file.  It is used (among other things) by the move-migrated-vms script
#	when bulk copying systems
#

#print(os.path.dirname(os.path.realpath(__file__)) + '/../lib/python3')
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../lib/python3')

import pyVmomi
import vmwareutils
import loginutils

def set_full_name(obj,root):
	global obj_to_fullname
	global fullname_to_obj

	if (obj is root):
		return ""
	elif (obj is None):
		return ""
	elif (obj in obj_to_fullname):
		return obj_to_fullname[obj]
	else:
		myname = set_full_name(obj.parent,root) + "/" + obj.name

		obj_to_fullname[obj] = myname
		fullname_to_obj[myname] = obj

		print(obj.name,myname,obj.__class__.__name__,sep='\t')

		return myname

def get_full_name(obj):
	global obj_to_fullname

	return obj_to_fullname.get(obj,None)

def get_named_obj(name):
	global fullname_to_obj

	return fullname_to_obj.get(name,None)
	


#
#----------------------------------------------------------------------
#
def get_all_objects(context):
	global fullname_to_obj
	global obj_to_fullname

	fullname_to_obj = {}
	obj_to_fullname = {}

	# Get all objects (no filter, recursive=True)
	all_objects = context.viewManager.CreateContainerView(
		context.rootFolder, None, True)

	all_objs = {}

	for c in all_objects.view:
		set_full_name(c,context.rootFolder)



#
#----------------------------------------------------------------------
#

def main():
	args = sys.argv

	server = args[1]

	context = loginutils.netlablogin(server)
	vmwareutils.get_all_roles(context)

	get_all_objects(context)


main()	
