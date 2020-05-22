#!/usr/bin/env python3

#
#
#	This was part of a process to migrate from Windows vSphere to VCSA in
#	a piece-by-piece manner.   This can be used to recreate the directory
#	structure on one vCenter to another
#
#	Uses a config file created by get-all-objects.py (or otherwise similar)
#

import sys
import os

#print(os.path.dirname(os.path.realpath(__file__)) + '/../lib/python3')
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../lib/python3')

import pyVmomi
import vmwareutils
import loginutils


#
#----------------------------------------------------------------------
#

def check_folder(folder):
	obj = vmwareutils.get_named_obj(folder)

	if (obj is None):
		(base,ending) = folder.rsplit("/",1)

		check_folder(base)

		print("Creating",ending,"in",base)

		obj =  vmwareutils.get_named_obj(base)
		newobj = obj.CreateFolder(ending)

		vmwareutils.set_one_full_name(newobj,folder)



#
#----------------------------------------------------------------------
#


def main():
	really_do_it = False

	args = sys.argv[1:]   # Ignore the name

	if (len(args) != 2):
		print("Usage: <server> <file>")
		sys.exit(1)

	i = 0
	server = args[i]
	i += 1

	infile = open(args[i])
	i += 1

	context = loginutils.netlablogin(server)
	vmwareutils.get_all_roles(context)
	
	vmwareutils.get_all_objects(context)

	for line in infile:
		if (line.startswith("#")):
			continue

	
		line = line.rstrip()

		(shortname,fullname,type) = line.split("\t")

		if (type == "vim.Folder"):
			check_folder(fullname)

	sambautils.disable_user(ADMIN_SVC_ACCT)


main()	
