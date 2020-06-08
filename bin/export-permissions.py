#!/usr/bin/env python3

import sys
import os

#print(os.path.dirname(os.path.realpath(__file__)) + '/../lib/python3')
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../lib/python3')

import pyVmomi
import vmwareutils
import loginutils

def full_name(obj,root):
	if (obj is root):
		return ""
	elif (obj is None):
		return ""
	else:
		return full_name(obj.parent,root) + "/" + obj.name


#
#----------------------------------------------------------------------
#

def main():
	really_do_it = False

	args = sys.argv

	if (len(args) < 2):
		print("Usage: <server>")
		sys.exit(1)

	server = args[1]

	context = loginutils.netlablogin(server)
	vmwareutils.get_all_roles(context)

	# Get all objects with any permissions
	all_perms = context.authorizationManager.RetrieveAllPermissions()

	for p in all_perms:
		name = full_name(p.entity,context.rootFolder)

		if (p.group):
			type = "GROUP"
		else:
			type = "USER"
		
		if (p.propagate):
			prop = "TRUE"
		else:
			prop = "FALSE"
	
		print(name,type,p.principal,
			prop,vmwareutils.get_rolename(p.roleId),sep="\t")


main()	
