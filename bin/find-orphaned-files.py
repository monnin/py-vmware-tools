#!/usr/bin/env python3


import sys
import os

#print(os.path.dirname(os.path.realpath(__file__)) + '/../lib/python3')
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../lib/python3')

import pyVmomi
import pyVim.task
import vmwareutils
import loginutils
import re
import argparse

OUTPUT_LEVEL      = 3		# Default to "medium" amount of info

VM_FILES          = {}		# Any/all files associated with any VM
VM_BASES          = {}		# VM directory (with and without the datastore)
ALL_DIRECTORIES   = {}		# All directories found on any datastore 
POTENTIAL_ORPHAN  = {}		# Potential orphans - (later) directories will get removed
FILENAME_COUNT    = {}		# Given a filename (w/o datastore name), how many copies exist
FILENAME_LOCATION = {}		# "      ", where does the file exist

def output(level,s):
	if (level >= OUTPUT_LEVEL):
		print(s)

#
#----------------------------------------------------------------------
#

def find_all_datastores(context):
	all_datastores  = context.viewManager.CreateContainerView(
		context.rootFolder, [pyVmomi.vim.Datastore], True)


	#for ds in all_datastores.view:
	#	print(ds.info.name)

	return all_datastores.view

def find_all_vms(context):
	all_vms  = context.viewManager.CreateContainerView(
		context.rootFolder, [pyVmomi.vim.VirtualMachine], True)

	return all_vms.view

def store_vm_file(filetype,filename):
	VM_FILES[filename] = filetype

	output(1,"VM File: " + filetype + " :: " + filename)

	if ("/" in filename):
		(vm_base,x) = filename.rsplit("/",1)
	
		if ("] " in vm_base):
			(ds,vm_small_base) = vm_base.split("] ",1)

			# Remove the leading [
			if (ds[0] == "["):
				ds = ds[1:]

			VM_BASES[vm_small_base] = ds

#
#	Get all of the files associated with all of the virtual machines
#

def find_all_vm_files(context):
	all_vms = find_all_vms(context)

	for one_vm in all_vms:
		path = one_vm.config.files.vmPathName
		output(2,"VM System: " + path)

		(path,x) = path.rsplit("/",1)
		path = path + "/"

		logpath = one_vm.config.files.logDirectory

		if (logpath is None):
			logpath = path

		store_vm_file("L",logpath.rstrip("/"))
		store_vm_file("V",path.rstrip("/"))

		#print("Creating base of",path.rstrip("/"))

		store_vm_file("v",one_vm.config.files.vmPathName)

		for disks in one_vm.layout.disk:

			for one_disk in disks.diskFile:
				store_vm_file("d",one_disk)

		for snap in one_vm.layout.snapshot:
			for one_snap in snap.snapshotFile:
				store_vm_file("s",one_snap)

		for log in one_vm.layout.logFile:
			#print(logpath + log)

			store_vm_file("l",logpath + log)

		for config in one_vm.layout.configFile:
			store_vm_file("c",path + config)

		if (one_vm.layout.swapFile is not None):
			store_vm_file("p",one_vm.layout.swapFile)

def check_if_ignored(filename, ignore_path, prefix, extra = "", printit=True):
	ignored = False
	count = 0

	for regex in ignore_path:
		#print("Testing",filename,"vs",regex)
		if (re.search(regex, prefix + " " + filename) is not None):
			ignored = True
			#print("Matched")


	if (not ignored):
		if (extra != ""):
			extra = " :: (" + extra + ")"

		if (printit):
			output(5,prefix + " " + filename + extra)

		count = 1

	return count
#
#
#
def store_directory(filename):
	my_dir = filename
	count = 0		# Assume we are adding a directory (not file)

	if ("/" in my_dir):
		(my_dir,x) = my_dir.rsplit("/",1)
		count = 1				# Incr # of files

	if (my_dir not in ALL_DIRECTORIES):
		ALL_DIRECTORIES[my_dir] = 0

	ALL_DIRECTORIES[my_dir] += 1


def store_potential_orphan(filename, extra):
	POTENTIAL_ORPHAN[filename] = extra

def ds_basename(filename):
	basename = filename
	ds = ""

	if ("] " in basename):
		(ds,basename) = basename.split("] ")  # Remove the datastore
		ds = ds.lstrip("[")

	return (ds,basename)

#
#	Keep track of the number of times a specific file appears on
#	multiple datastores
#

def store_basename(filename):
	(ds,basename) = ds_basename(filename)

	if (basename not in FILENAME_COUNT):
		FILENAME_COUNT[basename] = 0
		FILENAME_LOCATION[basename] = set()

	FILENAME_COUNT[basename] += 1
	FILENAME_LOCATION[basename].add(ds)
#
#----------------------------------------------------------------------
#
def get_store_files(ds,ignore_path):
	output(2,"Working on " + ds.summary.name)

	search_spec = pyVmomi.vim.HostDatastoreBrowserSearchSpec()
	
	task = ds.browser.SearchDatastoreSubFolders_Task(
		"[" + ds.summary.name + "]",
		search_spec
		)

	pyVim.task.WaitForTask(task)

	all_files = task.info.result

	for search_result in all_files:
		# This will be a direrctory, with a list of files in it

		prefix = search_result.folderPath

		# Fix the "issue" with files in the root directory being squashed next to the datastore
		if (prefix.endswith("]")):
			prefix = prefix + " "

		# Handle all of the files in this directory
		for info in search_result.file:
			filename = prefix + info.path

			store_directory(filename)
			store_basename(filename)

			output(1,"DS File: " + filename)

			if (filename not in VM_FILES):
				# Add in the extra two properties in info.* if they are not blank
				# (they appear to be blank for me [NFSv4 mounted shares for vSphere 6.7])

				extra = ""
				if (info.modification is not None):
					extra = "Last Modified: " + str(info.modification)

				if (info.fileSize is not None):
					if (extra != ""):
						extra += ", "

					extra += "Length: " + str(info.fileSize)

				store_potential_orphan(filename, extra)

			else:
				# Keep track of files that were matched
				VM_FILES[filename] = "!" + VM_FILES[filename]	

#
#	See if any files are listed as being used by a VM that
#	do not actually exist on the datastore(s)
#
def show_missing(ignore_path):
	count = 0
	for filename in VM_FILES:

		# Only check unmatched files
		if (VM_FILES[filename][0] != "!"):
			count += check_if_ignored(filename, ignore_path, "Missing(Has VM):")

	if (count == 0):
		output(3,":: No missing files (for existing VMs) found...")


#
#----------------------------------------------------------------------
#

#
#	Find files that are on the datastore and that are not part
#	of any VM
#
def find_orphaned(ignore_path, show_options):
	count = 0

	for filename in POTENTIAL_ORPHAN:
		# Ignore directories
		if (filename not in ALL_DIRECTORIES):
			(ds,basename) = ds_basename(filename)

			(vm_base,x) = filename.rsplit("/",1)

			# Check for existing VMs without the datastore too
			vm_small_base = None
			if ("] " in vm_base):
				(x,vm_small_base) = vm_base.split("] ",1)


			if (vm_base in VM_FILES):
				count += check_if_ignored(filename, 
						  ignore_path, 
						  "Extra(Has VM):",
						  POTENTIAL_ORPHAN[filename],
						  "extra" in show_options)

			elif (FILENAME_COUNT[basename] > 1):
				# See where else the file is
				this_ds = set()
				this_ds.add(ds)

				other_ds = FILENAME_LOCATION[basename] - this_ds

				if (vm_small_base in VM_BASES):
					count += check_if_ignored(filename, 
						  ignore_path, 
						  "Duplicate(Has VM):",
						  "Current is on " + VM_BASES[vm_small_base],
						  "duplicate" in show_options) 
				else:
					count += check_if_ignored(filename, 
						  ignore_path, 
						  "Duplicate(No VM):",
						  "Also on " + ",".join(other_ds),
						  "duplicate" in show_options or
						  "orphaned"  in show_options) 

			elif ((vm_small_base is not None) and (vm_small_base in VM_BASES)):
				count += check_if_ignored(filename, 
						  ignore_path, 
						  "Remnant(Has VM):",
						  "Current is on " + VM_BASES[vm_small_base],
						  "remnant" in show_options)


			else:
				count += check_if_ignored(filename, 
						  ignore_path, 
						  "Orphaned(No VM):",
						  POTENTIAL_ORPHAN[filename],
						  "orphaned" in show_options)

	#if (count == 0):
	#	output(3,"No missing files (for existing VMs) found...")


#
#----------------------------------------------------------------------
#
def show_empty_directories(ignore_path):
	count = 0

	for one_dir in ALL_DIRECTORIES:
		if (ALL_DIRECTORIES[one_dir] <= 1):

			if (one_dir in VM_BASES):
				count += check_if_ignored(one_dir,
							  ignore_path,"Empty(Has VM):")
			else:
				count += check_if_ignored(one_dir,
							  ignore_path,"Empty(No VM):")

	if (count == 0):
		output(3,"No empty directories found...")
			

#
#----------------------------------------------------------------------
#

def arg_show_options(s):
	show_plus  = set()
	show_minus = set()

	if (s.strip() != ""):
		for item in s.split(","):
			word = item.strip().lower()	# Clean it up
			is_plus = True

			# Remove the + at the beginning if present
			if (word[0] == '+'):
				word = word[1:]

			# Remove the - at the beginning if present
			if ((word[0] == '!') or (word[0] == '-')):
				word = word[1:]
				is_plus = False

			if (word[0] == 'm'):
				word = 'missing'

			elif (word[0] == 'a'):
				word = 'all'

			elif (word[0] == 'd'):
				word = 'duplicate'

			elif (word[0] == 'o'):
				word = 'orphaned'

			elif (word[0] == 'r'):
				word = 'remnant'

			elif (word[0:2] == 'em'):
				word = 'empty-dirs'

			elif (word[0:2] == 'ex'):
				word = 'extra'

			else:
				print("Unrecognized option '"+word+"' ignored", 
			      	file=sys.stderr)


			if (is_plus):
				show_plus.add(word)
			else:
				show_minus.add(word)

	# If all, then reset the list so that the len() == 0 does it's magic
	if ("all" in show_plus):
		show_plus = set()

	# Nothing in the "plus" list?  Default to all
	if (len(show_plus) == 0):
		show_plus.add("duplicate")
		show_plus.add("extra")
		show_plus.add("empty-dirs")
		show_plus.add("missing")
		show_plus.add("orphaned")
		show_plus.add("remnant")

	# If -all, then don't show anything (which is likely not useful)
	if ("all" in show_minus):
		show_plus = set()

	# Now compute the difference between the two
	l = list(show_plus - show_minus)

	return l

def parse_args():
	parser = argparse.ArgumentParser(
			prog='find-orphaned-files',
			description='Compare files on DataStores to VMs')


	#parser.add_argument('--dry-run', default=False, action="store_true",
	#	help='Show the actions, but do not perform any moves')

	parser.add_argument('--default-ignore', '-x', 
		default=False, 
		action="store_true",
		help='Include a default list of files to ignore'
		)

	parser.add_argument('--output-level', '-l', 
		type=int, 
		default=3,
		help='Controls amount (level) of output to show (lower # = more)'
		)

	parser.add_argument('--show', 
		type=arg_show_options,
                help='What items to show ' + 
		     '(missing,extra,duplicate,empty-dir,orphaned)'
		)

	parser.add_argument('--type', 
		default='both',
		choices=['has-vm','no-vm','both'],
                help='Show items related to existing VMs or non-existent VMs?'
		)

	parser.add_argument('server', help="VCSA server to use")

	parser.add_argument('ignore_list',
		metavar='ignore-list', 
		default=[], 
		nargs='*',
		help='One or more regular expressions to use to ignore'
		)


	return parser.parse_args()


#
#----------------------------------------------------------------------
#

def main():
	global OUTPUT_LEVEL

	ignore_path = []

	args = parse_args()

	OUTPUT_LEVEL = args.output_level
	server       = args.server

	if (args.default_ignore):
		#print("Adding default ignore list")

		ignore_path.append(r": \[[^\]]+\] ?\.")		# Any file in / staring with a .
		ignore_path.append(r"\.[iI][Ss][oO]$")		# ISO files
		ignore_path.append(r"\.[zZ][Ii][Pp]$")		# Zip files

		ignore_path.append(r"/\.lck-[01-9a-f]+$")	# VMWare Lock files
		ignore_path.append(r"\] vmkdump/")		# ESXi dumpfiles

		ignore_path.append(r"\] @Recently-Snapshot/")	# QNAP snapshot location

		ignore_path.append(r": \[Install Media\] ")	# My location for .iso's
		ignore_path.append(r": \[CyberSecurity SW\] ")	# My location for (special) .iso's
		ignore_path.append(r": \[[^\]]*Content Library\] ")	# My locartion for pushed .vmdk's
	# Fix the type if type=both was not specified
	if (args.type == 'no-vm'):
		ignore_path.append(r"\(Has VM\)")

	if (args.type == 'has-vm'):
		ignore_path.append(r"\(No VM\)")


	for regx in args.ignore_list:
		#print("Will ignore",reg)
		ignore_path.append(regx)

	show_options = args.show
	# Take the default if no "--show" given
	if (show_options is None):
		show_options = arg_show_options("")

	output(2,"::Logging level = " + str(OUTPUT_LEVEL))

	output(2,"::Logging into server "+server)

	context = loginutils.netlablogin(server)
	
	output(2,"::Finding all VM files...")
	find_all_vm_files(context)

	output(2,"::Finding all Datastores...")
	stores = find_all_datastores(context)

	output(2,"::Finding all files...")
	for ds in stores:
		get_store_files(ds, ignore_path)

	output(2,"::Checking for orphaned files...")
	find_orphaned(ignore_path, show_options)

	if ('missing' in show_options):
		output(2,"::Checking for missing files...")
		show_missing(ignore_path)

	if ('empty-dirs' in show_options):
		output(2,"::Checking for empty directories...")
		show_empty_directories(ignore_path)
	

main()
