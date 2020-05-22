#!/usr/bin/env python3

import sys
import os

#
#	TODO:  Newly created names are all in lowercase
#

#print(os.path.dirname(os.path.realpath(__file__)) + '/../lib/python3')
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../lib/python3')

import pyVmomi
import vmwareutils
import loginutils

#
#----------------------------------------------------------------------
#
def load_role_file(infile):
	old_privs = [
		"VirtualMachine.Config.Unlock"
		]

	roles = {}

	for l in infile:
		l = l.rstrip()
		(name,descr,priv) = l.split("\t",2)

		name = name.lower()
		
		if (name not in roles):
			roles[name] = {}
			roles[name]["descr"] = descr
			roles[name]["privs"] = []
	
		if (priv not in old_privs):
			roles[name]["privs"].append(priv)

	return roles


def all_roles_to_names(existing_roles):
	n2obj = {}


	for r in existing_roles:
		n2obj[r.name.lower()] = r

	return n2obj

def is_same_privs(active_role,file_role):
	is_same = True

	alist = []
	for p in active_role.privilege:
		if (not p.startswith("System.")):
			alist.append(p)

	flist = file_role["privs"]

	# See if they are the same length (diff otherwise)
	if (len(alist) != len(flist)):
		is_same = False
	else:
		# Same length?  See if all of one is in the second
		for s in alist:
			if (s not in flist):
				is_same = False
	

	return is_same

def handle_all_roles(roles,context,existing_roles,dry_run,verbose):

	authMgr = context.authorizationManager
	n2obj = all_roles_to_names(existing_roles)

	for r in roles:
		if (r in n2obj):
			if (not is_same_privs(n2obj[r],roles[r])):
				if (dry_run or verbose):
					print("Update role",r)

				if (not dry_run):
					try:
						authMgr.UpdateAuthorizationRole(
							n2obj[r].roleId,
							n2obj[r].name,
							roles[r]["privs"])

					except pyVmomi.vim.InvalidArgument:
						print("Invalid argument for",r,"Bad Priv Roles?")
		else:
			p = roles[r]["privs"]

			if (dry_run or verbose):
				print("Create role",r)	
				#print("Privs",",".join(p))

			if (not dry_run):
				try:
					newid = authMgr.AddAuthorizationRole(r, p)

				except pyVmomi.vim.InvalidArgument:
					print("Invalid argument for",r,"Bad Priv Roles?")

#
#----------------------------------------------------------------------
#

def main():
	dry_run = False
	verbose = False
	args = sys.argv[1:]

	while ((len(args) > 0) and (args[0].startswith("-"))):
		arg = args[0]

		if (arg.startswith("-d") or (arg.startswith("--d"))):
			dry_run = True
		elif (arg.startswith("-v") or (arg.startswith("--v"))):
			verbose = True
		else:
			print("Unrecognized option \"" + arg + "\"")
			args = args[0:0]  # Hack - force the Usage line to come up next

		args = args[1:]

	if (len(args) != 2):
		print("Usage: [--dry-run] [--verbose] <server> <file>")
		sys.exit(1)

	server = args[0]
	infile = open(args[1])

	context = loginutils.netlablogin(server)
	all_roles = vmwareutils.get_all_roles(context)

	role_file = load_role_file(infile)
	handle_all_roles(role_file,context,all_roles,dry_run,verbose)

	sambautils.disable_user(ADMIN_SVC_ACCT)


main()	
