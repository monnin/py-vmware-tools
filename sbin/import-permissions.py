#!/usr/bin/env python3

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
def get_file_perms(f, dry_run, ignore_missing):
	global file_perms
	
	has_error = False

	file_perms = {}

	for l in f:
		l = l.rstrip()

		# Ignore (full-line) comments
		if (l.rstrip().startswith("#")):
			continue

		(name,type,principal,prop,role) = l.split("\t")
		key = name + "\t" + principal

		roleId = vmwareutils.get_roleid(role)

		if (roleId is None):
			if (not ignore_missing):
				print("Role \"" + role + "\" does not exist, offending line:", file=sys.stderr)
				print("    " + l,file=sys.stderr)
				has_error = True
			else:
				print("Skipping line due to missing role \"" + role + "\"")
				print("    " + l,file=sys.stderr)

		else:
			obj = get_named_obj(name)

			if (obj is None):
				if (not ignore_missing):
					print("Object \"" + name + "\" does not exist, offending line:", file=sys.stderr)
					print("    " + l,file=sys.stderr)
					has_error = True
				else:
					print("Skipping line due to missing object \"" + name + "\"")
					print("    " + l,file=sys.stderr)

			else:
				file_perms[key] = { "name" : name,
				     "principal" : principal,
				     "isGroup" : (type.upper() == "GROUP"),
				     "propagate" : (prop.upper() == "TRUE"),
				     "roleName" : role ,
				     "roleId" : roleId }

	if (has_error):
		if (dry_run):
			print("...would exit now if not in dry-run mode", file=sys.stderr)
		else:
			sys.exit(1)


def get_live_perms(context):
	global live_perms

	live_perms = {}

	# Get all objects with permissions
	all_perms = context.authorizationManager.RetrieveAllPermissions()

	for p in all_perms:
		name = set_full_name(p.entity,context.rootFolder)
		key = name + "\t" + p.principal

		live_perms[key] = { "obj" : p.entity,
				     "name" : name,
				     "used" : False,
				     "principal" : p.principal,
				     "isGroup" : p.group,
				     "propagate" : p.propagate,
				     "roleName" : 
					vmwareutils.get_rolename(p.roleId) }

#
#----------------------------------------------------------------------
#

#
#	Compare two permission dict's (typically one from live_perm
#	and one from file_perm)
#
def is_diff(perm1,perm2):
	diff_found = False

	diff_found = diff_found or (perm1["name"]      != perm2["name"])
	diff_found = diff_found or (perm1["principal"] != perm2["principal"])
	diff_found = diff_found or (perm1["isGroup"]   != perm2["isGroup"])
	diff_found = diff_found or (perm1["propagate"] != perm2["propagate"])
	diff_found = diff_found or (perm1["roleName"]  != perm2["roleName"])

	return diff_found

#
#----------------------------------------------------------------------
#


def compare_perms(context,dry_run, delete_extra, ignore_missing):
	global live_perms
	global file_perms

	authMgr = context.authorizationManager

	for k in file_perms:
		if (k not in live_perms):
			print("ADD",file_perms[k]["name"],file_perms[k]["principal"], file_perms[k]["roleName"])
	
			if (not dry_run):
				obj = get_named_obj(file_perms[k]["name"])

				newPerm = pyVmomi.vim.Permission(
					entity = obj,

					principal = file_perms[k]["principal"],
					group = file_perms[k]["isGroup"],
					propagate = file_perms[k]["propagate"],
					roleId = file_perms[k]["roleId"]
					)

				try:
					authMgr.SetEntityPermissions(obj,[newPerm])

				except pyVmomi.vim.fault.UserNotFound:
					print("!!! Can't ADD, no such user \"" + file_perms[k]["principal"] + "\" for ", 
					      file_perms[k]["name"])

					if (not ignore_missing):
						sys.exit(1)


		elif (is_diff(file_perms[k],live_perms[k])):
			print("REPLACE",file_perms[k]["name"],file_perms[k]["principal"],file_perms[k]["roleName"])

			live_perms[k]["used"] = True

			if (not dry_run):
				newPerm = pyVmomi.vim.Permission(
					entity = live_perms[k]["obj"],

					principal = file_perms[k]["principal"],
					group = file_perms[k]["isGroup"],
					propagate = file_perms[k]["propagate"],
					roleId = file_perms[k]["roleId"]
					)

				try:
					authMgr.SetEntityPermissions(live_perms[k]["obj"],[newPerm])

				except pyVmomi.vim.fault.UserNotFound:
					print("!!! Can't REPLACE, no such user \"" + file_perms[k]["principal"] + "\" for ", 
					      file_perms[k]["name"])

					if (not ignore_missing):
						sys.exit(1)

		else:
			live_perms[k]["used"] = True
			

	if (delete_extra):
		for k in live_perms:
			if (not live_perms[k]["used"]):
				print("REMOVE",live_perms[k]["name"],live_perms[k]["principal"])

				if (not dry_run):
					authMgr.RemoveEntityPermission(live_perms[k]["obj"],
								      live_perms[k]["principal"],
								      live_perms[k]["isGroup"])

#
#----------------------------------------------------------------------
#


def main():
	really_do_it = False

	args = sys.argv[1:]   # Ignore the name

	ignore_missing = False
	dry_run = False
	remove_extra = False


	while ((len(args) > 0) and (args[0].startswith("-"))):
		arg = args[0]

		if (arg.startswith("-d") or (arg.startswith("--d"))):
			dry_run = True
		elif (arg.startswith("-r") or (arg.startswith("--r"))):
			remove_extra = True
		elif (arg.startswith("-i") or (arg.startswith("--i"))):
			ignore_missing = True
		else:
			print("Unrecognized option \"" + arg + "\"")
			args = args[0:0]  # Hack - force the Usage line to come up next

		args = args[1:]

	if (len(args) != 2):
		print("Usage: [--dry-run] [--remove-extra] [--ignore-missing] <server> <file>")
		sys.exit(1)

	server = args[0]
	infile = open(args[1])

	context = loginutils.netlablogin(server)
	vmwareutils.get_all_roles(context)
	
	get_all_objects(context)
	get_live_perms(context)
	get_file_perms(infile, dry_run, ignore_missing)

	compare_perms(context,dry_run,remove_extra, ignore_missing)

	sambautils.disable_user(ADMIN_SVC_ACCT)


main()	
