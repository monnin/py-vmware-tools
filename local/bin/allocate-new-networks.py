#!/usr/bin/env python3
import sys
import ipaddress



def next_subnet(this_subnet):
	return ipaddress.ip_network((int(this_subnet.broadcast_address+1),
				     this_subnet.prefixlen))
	

	
#
#----------------------------------------------------------------------
#


def generate_netname(server,vlannum,ipbase):
	name = server + "-"

	if (ipbase is None):
		name += "bridged-"
	elif (server == "virtc"):
		name += "routed-"
	elif (server == "virtd"):
		name += "simulated-"
	else:
		name += "unknown-"

	if (ipbase is None):
		name += "vlan" + str(vlannum)
	else:
		name += str(ipbase) + ")"
		name = name.replace("/"," (/")	# Add a leading space and a opening par before /28

	return name

#
#----------------------------------------------------------------------
#

def create_vlans(server,switch,startv,endv,ipbase):

	for i in range(startv,endv+1):
		netname = generate_netname(server,i,ipbase)

		if (ipbase is None):
			print(server,switch,netname,i, sep="\t")
		else:
			print(server,switch,netname,i,str(ipbase), sep="\t")

			ipbase = next_subnet(ipbase)

#
#----------------------------------------------------------------------
#

def main():
	args = sys.argv

	if (len(args) < 5):
                print("Usage: <server> <switch> <start-vlan#> <end-vlan#|+numnets> [ip-base/prefix]")
                sys.exit(1)

	i = 1

        #if (args[i] == "-y"):
        #        really_do_it = True
        #        i += 1

	server = args[i]; i += 1
	switch = args[i]; i += 1

	startv = int(args[i]); i += 1
	
	if (args[i].startswith("+")):
		endv   = startv + int(args[i][1:]); i += 1
	else:
		endv   = int(args[i]); i += 1

	# Did they include an IP address?
	if (i < len(args)):
		ipbase = ipaddress.ip_network(args[i]); i += 1
	else:
		ipbase = None

	create_vlans(server,switch,startv,endv,ipbase)

main()
