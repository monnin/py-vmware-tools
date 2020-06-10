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

def main():
	args = sys.argv

	if (len(args) < 2):
		print("Usage: <server>")
		sys.exit(1)

	server = args[1]

	context = loginutils.netlablogin(server)
	all_roles = vmwareutils.get_all_roles(context)

	for r in all_roles:
		# Ignore the system roles
		if (r.roleId < 1):
			continue

		for p in r.privilege:
			if (not p.startswith("System.")):
				print(r.name,r.info.label,p,sep="\t")


main()	
