#!/usr/bin/env python3

#
#	This script is used on the destination VCSA cluster to rename VMs to their
#	original location (as copied by an "get-all-objects.py" file [get-all-objects]) and
#	a specific folder to look for newly migrated systems
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
def load_desired_locations(infile):
	
	desired_locs = {}

	for l in infile:
		l = l.rstrip()
		(name,loc,type) = l.split("\t",2)
		
		# Only keep track of the virtual machines
		if (type == "vim.VirtualMachine"):

			if (name in desired_locs):
				print("!!! There is more than one VM with the name '"+name+"'", file=sys.stderr)
				desired_locs[name] = "DUPLICATE-FOUND"
			else:	
				(loc,name2) = loc.rsplit("/",1)
				desired_locs[name] = loc

	return desired_locs

#
#----------------------------------------------------------------------
#
def move_systems(source_folder,desired_locs,dry_run,verbose):
	vms = vmwareutils.get_all_vms(source_folder)

	for vm in vms:
		loc = desired_locs.get(vm.name,"")
		if (loc == ""):
			print("!!! Cannot find a desired location for '"+vm.name+"'", file=sys.stderr)
		else:
			if (verbose or dry_run):
				print("Move",vm.name,"to",loc)

			if (not dry_run):
				fold_obj = vmwareutils.get_named_obj(loc)
				if (fold_obj is None):
					print("!!! Did not find",loc,"on the server", file=sys.stderr)
				else:
					fold_obj.MoveIntoFolder_Task([ vm ])

					#print("Exiting")
					#sys.exit(0)

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

	if (len(args) != 3):
		print("Usage: [--dry-run] [--verbose] <server> <source-folder> <file>")
		sys.exit(1)

	server = args[0]
	folder = args[1]
	infile = open(args[2])

	vmwareutils.set_domain("NETLAB\\")
	sambautils.set_domain("NETLAB\\")

	context = loginutils.netlablogin(server)

	desired_locs = load_desired_locations(infile)
	vmwareutils.get_all_objects(context, filter=pyVmomi.vim.Folder)

	if (folder == ""):
		source_folder = context.rootFolder
	else:
		source_folder = vmwareutils.get_obj(context,[pyVmomi.vim.Folder, pyVmomi.vim.Datacenter],folder)

		# If this is a DC, then look for the special vmFolder within it
		if (isinstance(source_folder,pyVmomi.vim.Datacenter)):
			source_folder = source_folder.vmFolder

	if (source_folder is None):
		print("No such folder '"+folder+"' on ",server,file=sys.stderr)
		sys.exit(1)

	move_systems(source_folder,desired_locs,dry_run,verbose)


main()	
