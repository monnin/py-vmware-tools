import vmwareutils
import sambautils
import getpass
import atexit


ADMIN_SVC_ACCT="auth-mgr"

def netlabdisable():
	sambautils.disable_user(ADMIN_SVC_ACCT)

def netlablogin(server):
	vmwareutils.set_domain("NETLAB\\")
	sambautils.set_domain("NETLAB\\")

	passwd = sambautils.new_pass(20)

	atexit.register(netlabdisable)			# Make sure account is disabled when done

	sambautils.set_pass(ADMIN_SVC_ACCT,passwd)
	sambautils.enable_user(ADMIN_SVC_ACCT)


	context = vmwareutils.vmware_login(server,ADMIN_SVC_ACCT,passwd)

	return context


def simplelogin(server):
	username = input("Enter username: ")
	passwd   = getpass.getpass("Enter password for '" +username+"' : ")

	context = vmwareutils.vmware_login(server,username,passwd)

	return context

