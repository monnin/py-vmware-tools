#!/usr/bin/env python3

import sys
import os
import pyVmomi

sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/../lib/python3'))

import vmwareutils
import loginutils


def has_recent_events(context,vm,days=7):
	hasEvents = False

	events = vmwareutils.get_recent_events_for_obj(context,vm,days)

	for e in events:
		if ((e.userName != "") and (e.userName != "User") and (ADMIN_SVC_ACCT not in e.userName)) :
			hasEvents = True
			#print(v.summary.config.name,"user=",e.userName,"mesg=",e.fullFormattedMessage)

	return hasEvents
	

#
#----------------------------------------------------------------------
#

def main():
	really_do_it = False

	args = sys.argv

	if (len(args) < 5):
		print("Usage: [-y] <server> <folder-name> <suspend-days> <poweroff-days>")
		sys.exit(1)

	i = 1

	if (args[i] == "-y"):
		really_do_it = True
		i += 1

	server = args[i]; i += 1
	folderName = args[i]; i += 1
	suspendDays = int(args[i]); i += 1
	powerOffDays = int(args[i]); i += 1

	context = loginutils.netlablogin(server)
	#vmwareutils.get_all_roles(context)

	#all_groups = sambautils.get_all_groups()


	folder = vmwareutils.get_folder(context, folderName)

	poweredon_vms = vmwareutils.get_all_vms(folder, 10, "poweredOn")
	suspended_vms = vmwareutils.get_all_vms(folder, 10, "suspended")

	# If the user doesn't want to suspend systems, then lump all non-poweredoff systems together
	if (suspendDays <= 0):
		suspended_vms = suspended_vms + poweredon_vms

	if (suspendDays > 0):
		for v in poweredon_vms:
			if (not has_recent_events(context,v,7)):
				print("Suspend",v.summary.config.name)

				if (really_do_it):
					v.SuspendVM_Task()

	if (powerOffDays > 0):
		for v in suspended_vms:
			if (not has_recent_events(context,v,14)):
				print("Shutdown",v.summary.config.name)

				if (really_do_it):
					#v.ShutdownGuest()
					v.PowerOffVM_Task()

	sambautils.disable_user(ADMIN_SVC_ACCT)


main()	
