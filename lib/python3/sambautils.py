import sys
import grp
import pwd
import subprocess
import random
import string

this = sys.modules[__name__]

this.GROUPCACHE = {}
DOMAIN_NAME = "NETLAB\\"

#
#----------------------------------------------------------------------
#

def set_domain(name):
	global DOMAIN_NAME

	DOMAIN_NAME = name

def strip_domain(s):
	if (s.lower().startswith(DOMAIN_NAME.lower())):
		s = s[len(DOMAIN_NAME):]
				
	return s

def add_domain(s):
	if (r"\\" not in s):
		s = DOMAIN_NAME + s

	return s

#
#----------------------------------------------------------------------
#

def get_all_groups():
	groups = {}

	for group in grp.getgrall():
		name = group[0].lower()
		name = strip_domain(name)

		groups[str(group[2])] = name

	return groups

def get_users_in_group(group):
	pipe = subprocess.run(["samba-tool","group", "listmembers", group],
			      stdout=subprocess.PIPE)

	lines = pipe.stdout.decode('utf-8').split('\n')
	del lines[-1]

	return lines


def valid_groupname(name):
	name = strip_domain(name).lower()

	realname = None

	for g in grp.getgrall():
		if (strip_domain(g.gr_name).lower() == name):
			realname = g.gr_name

	return realname


def valid_username(name):
	name = strip_domain(name)
	val = None

	try:
		val = pwd.getpwnam(name)
	except KeyError:
		val = None

	return (val is not None)

#
#----------------------------------------------------------------------
#

# If name is a user, just return a list with a single item
# If name is a group, return a list of all users within that group
# If name is invalid, return an empty list

def get_userlist_for_user_or_group(name):
	if (valid_username(name)):
		a = [ add_domain(name) ]
	else:
		
		gn = valid_groupname(name)

		if (gn is None):
			a = []
		else:
			all_groups = get_all_groups()

			gn = strip_domain(gn)

			a = recursively_get_users_in_group( gn, all_groups )

	return a

#
#----------------------------------------------------------------------
#

def recursively_get_users_in_group_hlp(group,all_groups):
	all_users = []
	
	users = get_users_in_group(group)
	
	for user in users:
		if (user.lower() in all_groups.values()):
			users2 = recursively_get_users_in_group(user,all_groups)
			if (users2 is not None):
				all_users.extend(users2)
		else:
			all_users.append(user)	

	return all_users
#
#----------------------------------------------------------------------
#


def recursively_get_users_in_group(group,all_groups):

	if (group in this.GROUPCACHE):
		all_users = this.GROUPCACHE[group]
	else:
		all_users = recursively_get_users_in_group_hlp(group,all_groups)
		this.GROUPCACHE[group] = all_users
	
	return all_users

#
#----------------------------------------------------------------------
#

def get_groups_for_user(user,groups = {}):
	pipe = subprocess.run(["wbinfo","--user-groups",user],
			      stdout=subprocess.PIPE)

	lines = pipe.stdout.decode('utf-8').split('\n')
	del lines[-1]	# Remove the one created by the ending "\n"

	for line in lines:
		if (line.isnumeric()):
			print(groups.get(line,line))

#
#----------------------------------------------------------------------
#
def new_pass(length):
	passchars = string.ascii_uppercase + string.digits + \
			string.ascii_lowercase + "!@#$%_-*,."

	newpass = ''.join(random.SystemRandom().choice(passchars) \
			for _ in range(length))

	return newpass


def set_pass(user,passwd):
	pipe = subprocess.run(["samba-tool","user", "setpassword", user,
				"--newpassword=" + passwd],
				stdout=subprocess.PIPE)

	#print(pipe)

def enable_user(user):
	pipe = subprocess.run(["samba-tool","user", "enable", user],
				stdout=subprocess.PIPE)

def disable_user(user):
	pipe = subprocess.run(["samba-tool","user", "disable", user],
				stdout=subprocess.PIPE)
	

