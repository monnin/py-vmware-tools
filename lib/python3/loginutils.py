import vmwareutils
import sambautils
import getpass

ADMIN_SVC_ACCT="auth-mgr"

def netlablogin(server):
	vmwareutils.set_domain("NETLAB\\")
	sambautils.set_domain("NETLAB\\")

	passwd = sambautils.new_pass(20)

	sambautils.set_pass(ADMIN_SVC_ACCT,passwd)
	sambautils.enable_user(ADMIN_SVC_ACCT)


	context = vmwareutils.vmware_login(server,ADMIN_SVC_ACCT,passwd)

	return context


def simplelogin(server):
	username = input("Enter username: ")
	passwd   = getpass.getpass("Enter password for '" +username+"' : ")

	context = vmwareutils.vmware_login(server,username,passwd)

	return context

