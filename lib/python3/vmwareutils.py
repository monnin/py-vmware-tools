#!/bin/env python3

import pyVmomi
import pyVim
import pyVim.connect

import requests
import ssl
import getpass
import datetime

#import sys

DOMAIN_NAME = ""

def set_domain(name):
	global DOMAIN_NAME

	DOMAIN_NAME = name

def strip_domain(s):
	if (s.lower().startswith(DOMAIN_NAME.lower())):
		s = s[len(DOMAIN_NAME):]

	return s


#
#----------------------------------------------------------------------
#

def get_all_folders(content,facstaff_name,student_name):
	container = content.viewManager.CreateContainerView(
		content.rootFolder, [pyVmomi.vim.Folder], True)

	facstaff = None
	student  = None

	facstaff_folders = {}
	student_folders = {}

	# Iterate once to get parent folders

	for c in container.view:
		if (c.name == facstaff_name):
			facstaff = c
		if (c.name == student_name):
			student = c

	# Iterate again to get the actual folders
	for c in container.view:

		if ((c.parent == facstaff) and (facstaff is not None)):
			#print("Found facstaff " + c.name)
			facstaff_folders[c.name] = c

		if ((c.parent == student) and (student is not None)):
			#print("Found student " + c.name)
			student_folders[c.name] = c

	return (facstaff_folders,student_folders,facstaff,student)

#
#----------------------------------------------------------------------
#
def get_all_roles(content):
	global VMWARE_ROLES
	global VMWARE_ROLEMAP

	authMgr = content.authorizationManager
	roles = authMgr.roleList
	
	VMWARE_ROLES = {}
	VMWARE_ROLEMAP = {}

	for role in roles:

		VMWARE_ROLES[role.info.label] = role.roleId
		VMWARE_ROLEMAP[role.roleId] = role.info.label

		#print(role.info.label + " = " + str(role.roleId))

	return roles

def get_roleid(name):
	name = name.lower()
	result = None

	for (k,v) in VMWARE_ROLES.items():
		if (k.lower() == name):
			result = v

	return result


def get_rolename(id):
	return VMWARE_ROLEMAP.get(id,"<unknown-" + str(id) + ">")

#
#----------------------------------------------------------------------
#


# https://github.com/vmware/pyvmomi-community-samples/blob/master/samples/create_folder_in_datacenter.py


def get_obj(content, vimtypes, name, parent=None):
	obj = None

	# If vimtypes is not a list, make it one
	if (not isinstance(vimtypes, list)):
		vimtypes = [vimtypes]

	if (parent is None):
		parent = content.rootFolder

	container = content.viewManager.CreateContainerView(
		parent, vimtypes, True)

	for c in container.view:
		if (c.name == name):
			obj = c
			break

	return obj


def create_folder(parent_folder, folder_name):
	return parent_folder.CreateFolder(folder_name)


def get_datacenter(content,name):
	return get_obj(content,[pyVmomi.vim.Datacenter],name)

def get_folder(content,name):
	return get_obj(content,[pyVmomi.vim.Folder],name)


def vmware_login(host,user,passwd = ""):
	#ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
	#ssl_ctx.verify_mode = ssl.CERT_NONE

	requests.packages.urllib3.disable_warnings(
		requests.packages.urllib3.exceptions.InsecureRequestWarning)

	#requests.packages.urllib3.disable_warnings()

	ssl._create_default_https_context = ssl._create_unverified_context

	if (passwd == ""):
		passwd = getpass.getpass("Enter " + user + " password: ")

	#print("Connecting to " + host + "...")

	c = pyVim.connect.SmartConnect(host=host,user=user,pwd=passwd,
                               	#sslContext=ssl_ctx
                               	)

	content = c.RetrieveContent()

	return content

#
#---------------------------------------------------------------------
#
def check_permissions(content,folder,user,desired_role):
	global VMWARE_ROLES

	result = -1

	if (desired_role is not None):
		result = 0
		needsChange = True

		for p in folder.permission:
			name = strip_domain(p.principal)

			#print("Testing " + name + "(want " + user + ") for " + str(p.roleId) + 
			#	" should be " + str(desired_role) + "?")

			if (name == user):
				if (p.roleId == desired_role):
					needsChange = False

		if (needsChange):
			result = 1
			authMgr = content.authorizationManager

			newPerm = pyVmomi.vim.Permission(
				principal = DOMAIN_NAME + user,
				entity = folder,
				group = False,
				propagate = True,
				roleId = desired_role
				)

			authMgr.SetEntityPermissions(folder,[newPerm])

			print("Changed the permission on " + folder.name + " for " + user)

	else:
		print("Could not find role")

	return result

#
#---------------------------------------------------------------------
#

#
#	See if there are folders to delete
#
def check_extra_folders(folders,where,admins, reallydelete=False):
    for f in folders.keys():
        # Ignore any VMWare Admins
        name = f[:f.index(" ")]

        if (name in admins):
            pass
        elif (name.startswith("student")):
            pass
        elif (name.startswith("faculty")):
            pass
        elif (reallydelete):
            print("Deleting folder",f)

            obj = folders[f]
            obj.Destroy_Task()

            #sys.exit(1)
        else:
            print("Warning! extra folder \"" + f + "\" found in \"" + where + "\"")


#
#----------------------------------------------------------------------
#

#
#	
#	folder = vim object representing folder
#	depth = max # of times to recurse
#
def get_all_vms(folder, depth=1, state=None):
	# Force a "safety" limit of 10
	if (depth > 10): 
		depth = 10

	vms = []

	if (hasattr(folder, 'childEntity')):
		children = folder.childEntity
		for c in children:
			if (isinstance(c, pyVmomi.vim.VirtualMachine)):
				#print("Found a machine")
				#print(c.summary.config.name, "=", c.summary.runtime.powerState)

				# Only add on matching systems
				if ((state is None) or 
				    (c.summary.runtime.powerState == state)):
					#print("Added",state,c.summary.config.name)
					vms.append(c)

			if (isinstance(c, pyVmomi.vim.Folder)):
				#print("Found a folder, recursing")
				if (depth > 1):
					vms += get_all_vms(c,depth-1, state)

	return vms



#
#
#	content = vim object representing object (e.g. a VirtualMachine)
#
#	since = string (in ISO format), or an int (# of days), 
#		    or None (for 7 days)
#
def get_recent_events_for_obj(content,obj,since=None):
	eventmgr = content.eventManager

	if ((since is None) or (isinstance(since,int))):
		if (since is None):
			since = 7

		dt = datetime.datetime.today() - datetime.timedelta(days=since)
		since = dt

	elif (isinstance(since,str)):
		since = datetime.datetimeA.strptime(since)

	filter_entity = pyVmomi.vim.event.EventFilterSpec.ByEntity(
			entity=obj, recursion="self")

	filter_date   = pyVmomi.vim.event.EventFilterSpec.ByTime(
			beginTime=since)

	filter_spec = pyVmomi.vim.event.EventFilterSpec()

	filter_spec.entity = filter_entity
	filter_spec.time   = filter_date

	events = eventmgr.QueryEvents(filter_spec)

	#for e in events: print(e.createdTime,e.userName,e.fullFormattedMessage)

	return events


#
#----------------------------------------------------------------------
#

def set_full_name(obj,root):
	global obj_to_fullname
	global fullname_to_obj

	if (obj is root):
		return ""
	elif (obj is None):
		return ""
	elif (obj in obj_to_fullname):
		return obj_to_fullname[obj]
	else:
		myname = set_full_name(obj.parent,root) + "/" + obj.name

		obj_to_fullname[obj] = myname
		fullname_to_obj[myname] = obj

		return myname

def set_one_full_name(obj,myname):
	global obj_to_fullname
	global fullname_to_obj

	obj_to_fullname[obj] = myname
	fullname_to_obj[myname] = obj
	

def get_full_name(obj):
	global obj_to_fullname

	return obj_to_fullname.get(obj,None)

def get_named_obj(name):
	global fullname_to_obj

	return fullname_to_obj.get(name,None)



#
#----------------------------------------------------------------------
#
def get_all_objects(context, filter=None):
	global fullname_to_obj
	global obj_to_fullname


	# If given a scalar, convert it to a list
	if ((filter is not None) and (not isinstance(filter,list))):
		filter = [ filter ]

	fullname_to_obj = {}
	obj_to_fullname = {}

	# Get all objects (no filter, recursive=True)
	all_objects = context.viewManager.CreateContainerView(
		context.rootFolder, filter, True)

	all_objs = {}

	for c in all_objects.view:
		set_full_name(c,context.rootFolder)


