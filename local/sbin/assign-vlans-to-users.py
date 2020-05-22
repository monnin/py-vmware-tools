#!/usr/bin/env python3

import collections
import sys
import os
import fnmatch
import re

#print(os.path.dirname(os.path.realpath(__file__)) + '/../lib/python3')
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../lib/python3')

import pyVmomi
import vmwareutils
import sambautils
import loginutils


def decode_name(s):
	s = s.replace("%2f","/")

	
	return s


#
#----------------------------------------------------------------------
#
def assign_to_users(context, users, count, free_nets, user_count, dry_run):

	all_groups = sambautils.get_all_groups()
	all_admins = sambautils.recursively_get_users_in_group(
			"VMWare Admins", all_groups)

	authMgr = context.authorizationManager

	netconsum = vmwareutils.get_roleid("Network consumer")
	admin     = vmwareutils.get_roleid("Administrator")

	for u in users:

		# See how many we need for this person
		netcount = user_count.get(u,0)

		#print(u,"wants",count,"has",netcount)

		# Give them one if necessary
		while (netcount < count):

			# Need to give a net, and none left?
			#  If so, then abort!

			if (len(free_nets) == 0):
				print("No more matching networks, cannot allocate a free network to", u)
				sys.exit(1)

			(netname,c) = free_nets.popitem(last=False)
			
			if (u in all_admins):
				my_perms = admin
				extra = "(admin)"
			else:
				my_perms = netconsum
				extra = ""

			print("ASSIGN", netname,"TO", u, extra)

			if (not dry_run):
				#newAdminPerm = pyVmomi.vim.Permission(
				#	principal = sambautils.add_domain("VMWare Admins"),
				#	entity = c,
				#	group = True,
				#	propagate = True,
				#	roleId = admin
				#	)
			
				newUserPerm = pyVmomi.vim.Permission(
					principal = sambautils.add_domain(u),
					entity = c,
					group = False,
					propagate = True,
					roleId = my_perms
					)

				authMgr.SetEntityPermissions(c,[newUserPerm])


			netcount += 1


#
#
#
def name_sort(item):
	s = item[0]
	olds = ""

	# Replace all single #'s with 00#
	while (s != olds):
		olds = s
		s = re.sub(r"([\.\-])(\d)(\.| )", r"\g<1>00\g<2>\g<3>", s)

	olds = ""
	# Replace all double #'s with 0##
	while (s != olds):
		olds = s
		s = re.sub(r"([\.\-])(\d\d)(\.| )", r"\g<1>0\g<2>\g<3>", s)

	#print(item[0],"=>",s)

	return s
#
#----------------------------------------------------------------------
#

def get_nets_and_users(context,poolname,altpoolname):
	# Get network objects (no filter, recursive=True)
	all_nets_view = context.viewManager.CreateContainerView(
		context.rootFolder, [pyVmomi.vim.Network], True)

	free_nets = {}
	user_count = {}

	#
	# Find all networks that are not taken by anyone
	#  (aka have no permissions assigned to them)
	#
	for c in all_nets_view.view:
		n = decode_name(c.name).lower()
		
		#print("Found",n,"Does it match",poolname)

		# Ignore any networks that don't match the pool pattern
		if (not fnmatch.fnmatch(n, poolname)):
			continue
		
		# No permissions?  Then consider this network "available"
		if (len(c.permission) == 0):

			# Only match free networks with the secondary pool
			if (fnmatch.fnmatch(n,altpoolname)):
				free_nets[n.lower()] = c
				#print("Found matching free net",n)

		else:
			for p in c.permission:
				holder = sambautils.strip_domain(p.principal)

				user_count[holder] = user_count.get(holder,0) + 1 

				#print("Found net for",holder, "now",user_count[holder])

	# Now sort the free_nets

	sorted_free_nets = collections.OrderedDict( 
		sorted(free_nets.items(),key=name_sort ) 
		)
		

	#print("End of test")
	#sys.exit(0)

	return (sorted_free_nets,user_count)




#
#----------------------------------------------------------------------
#

def main():
	really_do_it = False

	args = sys.argv

	if (len(args) < 4):
		print("Usage: [--dry_run|-d] <server> <group|user> [-n #] " + \
			"<pool-name> [<subpool-name>]")

		sys.exit(1)

	i = 1

	if ((args[i].startswith("--d")) or (args[i].startswith("-d"))):
		i += 1
		dry_run = True
	else:
		dry_run = False

	server = args[i]; i += 1
	userorgroup = args[i]; i += 1

	if (args[i].startswith("-n")):
		i += 1
		count = int(args[i]); i += 1
	else:
		count = 1

	poolname = args[i].lower(); i += 1
	if (len(args) > i):
		altpoolname = args[i].lower(); i += 1
	else:
		altpoolname = poolname

	vmwareutils.set_domain("NETLAB\\")
	sambautils.set_domain("NETLAB\\")

	users = sambautils.get_userlist_for_user_or_group(userorgroup)

	if (len(users) == 0):
		print("No such user or group '" + userorgroup + "'")
		sys.exit(1)

	context = loginutils.netlablogin(server)

	vmwareutils.get_all_roles(context)

	(free_nets,user_count) = get_nets_and_users(context,poolname,altpoolname)

	assign_to_users(context, users, count, free_nets, user_count, dry_run)


main()	
