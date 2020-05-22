#!/usr/bin/env python3

#
#	TODO: add "atexit" handler
#	TODO: add max parallel moves
#

#
#	Balance machine count = smaller systems first
#	Balance disk space = largest systems first
#	Balance both = ???
#
#

import argparse
import sys
import os
import fnmatch
import copy

#print(os.path.dirname(os.path.realpath(__file__)) + '/../lib/python3')
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../lib/python3')

import pyVmomi
import datastoreScore
import vmwareutils
import loginutils
import forgiveChoices

TOTAL_NAME ="__TOTAL__"

TASK_LIST = {}


#
#----------------------------------------------------------------------
#

FIELD_TO_LETTER = {
		"used_space"             : "u",
		"free_space"             : "f",
		"total_size"             : "s",
		"perc_used"              : "U",
		"perc_free"              : "F",
		"active_vms"             : "a",
		"inactive_vms"           : "i",
		"all_vms"                : "t",
		"total_vm_space_used"    : "v",
		"eligible_vm_space_used" : "V" }

#

FIELD_TO_DESCR = {
	"used_space"             : "Disk Used (bytes)",
	"free_space"             : "Disk Free (bytes)",
	"total_size"             : "Total Disk Size (bytes)",

	"perc_used"              : "% Disk Used (percent)",
	"perc_free"              : "% Disk Free (percent)",

	"total_vm_space_used"    : "Space Used by all VM HDs (bytes)",
	"eligible_vm_space_used" : "Space Used by SELECTED VM HDs (bytes)",

	"active_vms"             : "Active VMs (#)",
	"inactive_vms"           : "Inactive VMs (#)",
	"all_vms"                : "Total VMs [active+inactive] (#)"
	}

#		
#----------------------------------------------------------------------
#


def decode_name(s):
	s = s.replace("%2f","/")

	
	return s

#
#	Create small (4-byte) random integers
#
def random_int():
	return int.from_bytes( os.urandom(4), byteorder='big')


#
#----------------------------------------------------------------------
#

#
#	find_all_pools - Verify poolnames, and add a link to the
#	JSON object.  Returns a new version of the dictionary, with
#	pool objects, or None if an invalid poolname was given.
#

def find_all_pools(content,pools):
	found_all = True

	for p in pools:
		c = vmwareutils.get_obj(content, pyVmomi.vim.Datastore, p)

		if (c is None):
			print("No such datastore '"+p+"'", file=sys.stderr)
			found_all = False
		else:
			pools[p]["object"] = c

	return found_all


#
#----------------------------------------------------------------------
#

def recompute_percent(p):
	p["perc_used"] = p["used_space"] /  p["total_size"]
	p["perc_free"] = p["free_space"] /  p["total_size"]


def vm_has_desired_parent(vm,parentlist):
	is_desired = False
	
	# No list of parents? Then everything is ok
	if ((parentlist is None) or (len(parentlist) == 0)):
		is_desired = True
	else:
		# Check all parents, grandparents, etc of this vm to
		#  see if any matches any on the parentlist
		p = vm.parent
		while ((p is not None) and (p.name.lower() not in parentlist)):
			p = p.parent

		is_desired = (p is not None)
		
	return is_desired

#
#	gather_pool_info
#	
#	Get all of the pool stats needed for balancing them
#	  in a single step
#
#	Returns new version of the pool with the added info
#
def gather_pool_info(pools, vm_selection, folders=None, refresh=False):

	# Convert all parent names to lowercase
	if (folders is not None):
		folders = [s.lower() for s in folders]

	for p in pools:
		if (p != TOTAL_NAME):			
			active_vms = 0
			inactive_vms = 0

			c = pools[p]["object"]
		
			# Get new numbers first?
			if (refresh):
				c.RefreshDatastore()

			pools[p]["total_size"] = c.summary.capacity	# Bytes
			pools[p]["free_space"] = c.summary.freeSpace	# Bytes

			pools[p]["used_space"] = \
				pools[p]["total_size"] - pools[p]["free_space"]
	
			recompute_percent(pools[p])

			pools[p]["accessible"] = c.summary.accessible	# True/False
			pools[p]["maint_mode"] = c.summary.maintenanceMode	# Str

			pools[p]["ok_to_move"] = \
		      		(pools[p]["accessible"] and 
                       		(pools[p]["maint_mode"] == "normal"))

			pools[p]["ok_to_move"] = True		# HACK: DEBUG!!! REMOVE ME WHEN REAL

			#for h in c.host:
			#	print("Pool",p,"host",h.key.name,"accessible=",
			#	      h.mountInfo.accessible,"accessMode=",
			#	      h.mountInfo.accessMode)

			pools[p]["eligible_vms"] = []

			total_vm_space_used = 0
			eligible_vm_space_used = 0

			for vm in c.vm:
				if (vm.runtime.powerState == "poweredOn"):
					active_vms += 1
					is_active = True
				else:
					inactive_vms += 1
					is_active = False

				disk_used = 0

				for device in vm.config.hardware.device:
					if (isinstance(device,pyVmomi.vim.VirtualDisk)):
						#print(vm.name,"has a hard drive")

						disk_used += \
					  		(device.capacityInKB * 1024)

				# Add to the total space used by the pool
				total_vm_space_used += disk_used

				selected = True

				if (is_active and (vm_selection == "inactive")):
					selected = False

				if ((not is_active) and (vm_selection == "active")):
					selected = False

				# Still OK?  Now check to see if the parent is correct too
				if (selected):
					selected = vm_has_desired_parent(vm,folders)

				# 
				#  Add only VMs that match the requirement
				#
				if (selected):
					onevm = { "name" : vm.name, 
					 	"object" : vm,
					 	"is_active" : is_active, 
					 	"used_space" : disk_used,
						"pool" : p,
					 	"random_tiebreaker" : random_int()
						}

					pools[p]["eligible_vms"].append(onevm)
					eligible_vm_space_used += disk_used

	
			pools[p]["active_vms"] = active_vms
			pools[p]["inactive_vms"] = inactive_vms
			pools[p]["all_vms"] = inactive_vms + active_vms

			pools[p]["eligible_vm_space_used"] = eligible_vm_space_used
			pools[p]["total_vm_space_used"] = total_vm_space_used
		

#		
#----------------------------------------------------------------------
#

#
#	two_col - Print info into two columns
#
def two_col(a,b):
	print(a.ljust(36),":",b)

def three_col(a,b,c):
	print(a.ljust(36),":",b.ljust(20),c)

#
#	si_units - Convert a number into a SI-units number 
#	(2 digits past decimal, add suffix if given)
#
def si_units(v,suffix="B"):
	if (v < 1024):
		s = str(v) + " " + suffix

	elif (v < 1024**2):
		v = v / 1024.0
		s = "{:5.2f} K".format(v) + suffix

	elif (v < 1024**3):
		v = v / (1024.0 ** 2)
		s = "{:5.2f} M".format(v) + suffix

	elif (v < 1024**4):
		v = v / (1024.0 ** 3)
		s = "{:5.2f} G".format(v) + suffix

	else:
		v = v / (1024.0 ** 4)
		s = "{:5.2f} T".format(v) + suffix

	return s

#
#----------------------------------------------------------------------
#
def print_item(p, field, fmt="si", suffix="B"):
	l = FIELD_TO_LETTER[field]

	s1 = FIELD_TO_DESCR[field]
	s1 += " [" + l + "]"

	v = p[field]

	if (fmt == "perc"):
		s2 = str(int(v * 100)) + "%"
	elif (fmt == "si"):
		s2 = si_units(v,suffix)
	else:
		s2 = str(v)

	if ("score" in p):
		v = p["score"].get(l)

		if (v is None):
			s3 = ""
		else:
			s3 = "%not_bal = {:4.1f}".format(abs(v)* 100)

			if (v > 0):
				s3 += " [+]"
			if (v < 0):
				s3 += " [-]"

	else:
		s3 = ""


	three_col(s1,s2,s3)

#
#----------------------------------------------------------------------
#

#
#	print_one_pool
#
#	Display all of the info about a single pool
#

def print_one_pool(p, vm_selection):
	two_col("Name",p["name"])
	print("-" * 52)

	two_col("Weight", p["weight"])

	if (p["accessible"]):
		two_col("Disk Accessible?","Yes")
	else:
		two_col("Disk Accessible?","Yes")

	two_col("Mode: Normal or Maint?", p["maint_mode"])

	if (p["ok_to_move"]):
		two_col("Ready for vMotion?", "Yes")
	else:
		two_col("Ready for vMotion?", "No")

	print("")

	print_item(p,"used_space")
	print_item(p,"free_space")
	print_item(p,"total_size")

	print("")

	print_item(p,"perc_used","perc")
	print_item(p,"perc_free","perc")

	print("")
	print_item(p,"total_vm_space_used")

	if (vm_selection != "both"):
		print_item(p,"eligible_vm_space_used")

	print("")

	print_item(p,"active_vms","raw")
	print_item(p,"inactive_vms","raw")
	print_item(p,"all_vms","raw")

	if ("score" in p):
		print("")
	
		s = ""

		for v in p["goal_scores"]:
			s = s + "{:4.1f} ".format(abs(v) * 100.0)

		s = s.strip()		# Remove (initial) blanks

		two_col("Goal Score (0 = good)",s)	
		two_col("Summary Score", p["summary_score"])
#
#----------------------------------------------------------------------
#

def print_pools(pools, header, vm_selection, goals, refresh=False):
	print(header + ":::")

	if (refresh):
		gather_pool_info(pools, vm_selection, refresh=True)

	compute_totals(pools)
	compute_pool_weights(pools)
	compute_pool_scores(pools, goals)

	for p in pools:
		if (p != TOTAL_NAME):
			print_one_pool(pools[p], vm_selection)

			print("")

	
#
#----------------------------------------------------------------------
#
def tot_score_is_better_than_sum_only(old_s,new_s):
	old_sum = sum(map(abs,old_s))
	new_sum = sum(map(abs,new_s))

	return new_sum < old_sum

	

#
#       tot_score_is_better_than(a,b)
#
#       See if "a" is a better score (smaller) than "b" IN ALL CATEGORIES
#
#	(better = "better or the same" in all categories,
#	          and at least one improved category)
#
def tot_score_is_better_than(old_s,new_s):
	is_better = True
	has_diff = False

	for i in range(0,len(old_s)):
		if   (abs(old_s[i]) < abs(new_s[i])):
			is_better = False
		elif (abs(old_s[i]) > abs(new_s[i])):
			has_diff = True

	return (is_better and has_diff)

#
#	Same as above, but disallows numbers to
#	to change sign
#

def tot_score_is_better_than_nocross(old_s,new_s):
	is_better = True
	has_diff = False

	for i in range(0,len(old_s)):
		if   (abs(old_s[i]) < abs(new_s[i])):
			is_better = False

		elif (abs(old_s[i]) > abs(new_s[i])):
			has_diff = True

		# Does it cross zero? 
		#  (if so, then say it's not better)
		if ((old_s[i] > 0) and (new_s[i] < 0)):
			is_better = False

		if ((old_s[i] > 0) and (new_s[i] < 0)):
			is_better = False

	#print("is:",new_s,"better than",old_s,"? is_better=",is_better,"has_diff=",has_diff)

	return (is_better and has_diff)



#
#----------------------------------------------------------------------
#

#
#	Remove any pools that can't be a source or destination
#	(offline, zero weight, etc.)
#
def remove_nonready_pools(pools):
	newpools = {}
	tot_weight = 0.0

	#
	# Remove if weight is ZERO (or smaller), or if in Maint Mode
	#  (or if not accessible for any other reason)
	#
	for p in pools:
		if (p != TOTAL_NAME):
			if ((pools[p]["weight"] > 0) and \
			    (pools[p]["ok_to_move"])):

				newpools[p] = pools[p]

	return newpools

#
#----------------------------------------------------------------------
#

def add_to_total(pools,t,p,name):
	pools[t][name] += pools[p][name]

def compute_totals(pools): 

	pools[TOTAL_NAME] = {}

	fields = ["total_size", "free_space", "used_space", 
		  "perc_used", "perc_free",
		  "active_vms", "inactive_vms", "all_vms",
		  "total_vm_space_used", "eligible_vm_space_used" ]
	
	# Zero out
	for n in fields:
		pools[TOTAL_NAME][n] = 0

	for p in pools:
		if (p != TOTAL_NAME):
			for n in fields:
				add_to_total(pools,TOTAL_NAME,p,n)


	# Did the filter rule out all virtual machines?

	if (pools[TOTAL_NAME]["eligible_vm_space_used"] == 0):
		print("No matching VMs, cannot balance\n")
		sys.exit(1)



#
#----------------------------------------------------------------------
#

#
#	Determine each pools percentage of the total weight
#

def compute_pool_weights(pools):
	tot_weight = 0.0

	# Get the total weight
	for p in pools:
		if (p != TOTAL_NAME):
			tot_weight += pools[p]["weight"]

	# Now set the percentages
	for p in pools:
		if (p != TOTAL_NAME):
			pools[p]["perc_weight"] = \
				pools[p]["weight"] / tot_weight


#
#----------------------------------------------------------------------
#
def make_pool_changes(p,tot_pool,goals,add_vm=None,remove_vm=None,verbose=False):
	newpool = copy.copy(p)

	active_delta = 0
	inactive_delta = 0	
	bytes_delta = 0

	if (add_vm is not None):
		if (add_vm["is_active"]):
			active_delta += 1
		else:
			inactive_delta += 1

		bytes_delta += add_vm["used_space"]

	if (remove_vm is not None):
		if (remove_vm["is_active"]):
			active_delta -= 1
		else:
			inactive_delta -= 1

		bytes_delta -= remove_vm["used_space"]

	#print("Modifying pool, active=",active_delta,"inactive=",inactive_delta,"bytes=",bytes_delta)

	newpool["active_vms"] += active_delta
	newpool["inactive_vms"] += inactive_delta
	newpool["all_vms"] += active_delta + inactive_delta

	newpool["free_space"] -= bytes_delta	# Not exactly accurate (dependinging on 'holes' in files)
	newpool["used_space"] += bytes_delta	# Not exactly accurate...

	newpool["total_vm_space_used"] += bytes_delta
	newpool["eligible_vm_space_used"] += bytes_delta

	#print("old summary score=",newpool["summary_score"])
	#print("old",newpool["goal_scores"])

	# Do not show new scores if no changes wer made
	if ((add_vm is None) and (remove_vm is None)):
		verbose = False
	
	recompute_percent(newpool)
	compute_one_pool_score(newpool,tot_pool,goals,verbose)

	#print("new summary score=",newpool["summary_score"])
	#print("new",newpool["goal_scores"])

	return newpool
	

#
#
#
def compute_max_imbalanced(pools):
	max_imb = 0

	for p in pools:
		if (p != TOTAL_NAME):
			for g in pools[p]["goal_scores"]:
				g = abs(g)
				if (g > max_imb):
					max_imb = g

	return max_imb

#
#----------------------------------------------------------------------
#

def compute_one_pool_score(p,tot_pool,goals,verbose=False):
	score = datastoreScore.OneScore()

	for (f,l) in FIELD_TO_LETTER.items():
		per_item = p[f] / tot_pool[f]
		per_pool = p["perc_weight"]

		item_score = (per_item / per_pool) - 1

		score.set(l,item_score)
				
	p["score"] = score

	all_scores = goals.all_scores_w_adj(score)
	#all_scores = goals.all_scores(score)

	p["goal_scores"] = all_scores
	p["summary_score"] = sum(map(abs,all_scores))

	if (verbose):
	    print(p["name"],"now has a summary score of", p["summary_score"])

def compute_pool_scores(pools, goals,verbose=False):
	tot_pool = pools[TOTAL_NAME]

	for p in pools:
		if (p != TOTAL_NAME):
			compute_one_pool_score(pools[p], tot_pool, goals, verbose)

#
#----------------------------------------------------------------------
#
#
#	Wait for tasks to complete.  If max_concurrent_tasks > 0,
#	then allow that many tasks to work in parallel
#
def wait_for_n_tasks(task=None,descr="",verbose=True,max_concurrent_tasks = 0):
	global TASK_LIST

	if (task is not None):
		TASK_LIST[descr] = task

	delete_list = []

	while (len(TASK_LIST) > max_concurrent_tasks):
		for (d,t) in TASK_LIST.items():
			# See if there was any completed tasks
			if (t.info.state == 'error'):
				print("!!! Task: " + d + " failed!", file=sys.stderr)
				delete_list.append(d)
			if (t.info.state == 'success'):
				if (verbose):
					print("Task: " + d + " completed.")
				delete_list.append(d)

		# Now we have a list of items to remove from the dictionary, so do it

		for d in delete_list:
			if (d in TASK_LIST):
				del TASK_LIST[d]
	
#
#----------------------------------------------------------------------
#
def vmotion_vm(vm, to_pool, descr, verbose, max_concurrent):
	spec = pyVmomi.vim.VirtualMachineRelocateSpec()

	spec.datastore = to_pool
	#spec.host = vm.host
	#spec = pyVmomi.vim.vm.RelocateSpec(datastore=to_pool)

	task = vm.RelocateVM_Task(spec)

	wait_for_n_tasks(task,descr,verbose,max_concurrent)

#
#----------------------------------------------------------------------
#

def key_inactive(vm):
	if (vm["is_active"]):
		v = 2
	else:
		v = 1

	return v
	
def key_custom(vm):
	global SORT_MODE

	size = vm["used_space"]
	status = key_inactive(vm)

	v3 = vm["random_tiebreaker"]

	if (SORT_MODE["first"] == "size"):
		v1 = SORT_MODE["size"] * size
		v2 = SORT_MODE["status"] * status
	else:
		v1 = SORT_MODE["status"] * status
		v2 = SORT_MODE["size"] * size

	return (v1,v2,v3)
		

	
	
def show_top_vms(p,name):
	j = min(10,len(p["eligible_vms"]))

	# Don't print an empty list
	if (j > 0):
		print("Top",j,"VMs","in pool",name)
		print("-" * 40)

		for i in range(0,j):
			vm = p["eligible_vms"][i]

			print(i+1,"-",vm["name"], \
			      "active" if vm["is_active"] else "inactive", \
			      si_units(vm["used_space"]),
			      "Rand=" + str(vm["random_tiebreaker"]))
		
		print("")

def sort_pool_vms(pools):
	for p in pools:
		if (p != TOTAL_NAME):
			pools[p]["eligible_vms"].sort(key=key_custom)
			show_top_vms(pools[p],p)

#
#----------------------------------------------------------------------
#

def set_sorting_style(vm_mode,vm_size_select,vm_status_select):
	global SORT_MODE

	SORT_MODE = {}

	size = vm_size_select.lower()[0]
	status = vm_status_select.lower()[0]
	mode = vm_mode.lower()[0:2]

	if (size == "l"):
		SORT_MODE["size"] = -1.0	# Largest first
	elif (size == "s"):
		SORT_MODE["size"] = 1.0		# Smallest first
	else:
		SORT_MODE["size"] = 0.0		# Neither

	if (status == "i"):
		SORT_MODE["status"] = 1.0	# Inactive first
	elif (status == "a"):
		SORT_MODE["status"] = -1.0	# Active first
	else:
		SORT_MODE["status"] = 0.0	# Neither


	if (mode == "to"):
		SORT_MODE["status"] = 0.0	# Totally random
		SORT_MODE["size"] = 0.0	
		SORT_MODE["first"] = "size"	# Doesn't matter
	elif (mode == "si"):
		SORT_MODE["first"] = "size"	# Size first
	else:
		SORT_MODE["first"] = "status"	# Status first

#
#----------------------------------------------------------------------
#

def max_neg_max_pos_score(p):
	max_neg = 0
	max_pos = 0

	for v in p["goal_scores"]:
		if (v < max_neg):
			max_neg = v

		if (v > max_pos):
			max_pos = v

	return (max_pos,max_neg)

def most_unbalanced_pools(pools):
	largest_abs_v = 0.0

	sec_most_pos_p = None	# In case one pool is max pos & max neg
	most_pos_p = None
	most_pos_v = 0

	most_neg_p = None
	most_neg_v = 0

	for p in pools:
		if (p != TOTAL_NAME):
			(pos,neg) = max_neg_max_pos_score(pools[p])

			if (pos	> most_pos_v):
				most_pos_v = pos
				sec_most_pos_p = most_pos_p
				most_pos_p = p

				if (pos > largest_abs_v):
					largest_abs_v = pos

			if (neg	< most_neg_v):
				most_neg_v = neg
				most_neg_p = p

				if (-neg > largest_abs_v):
					largest_abs_v = -neg


	# If the same pool is both, then override the pos one
	if (most_pos_p == most_neg_p):
		most_pos_p = sec_most_pos_p

	return (most_pos_p,most_neg_p, largest_abs_v)

def print_scores(l):
	print("(", end="")

	for i in l:
		print("{:6.1f}%".format(i*100.0),end="")

	print(")", end="")

#
#----------------------------------------------------------------------
#
def find_best_server_move(pools, all_vms, goals, dry_run, verbose):

	best_server_to_move = None
	best_server_dest    = None
	best_score_change   = 0

	tot_pool = pools[TOTAL_NAME]

	for vm in all_vms:
		for p in pools:
			if ((p != TOTAL_NAME) and (p != vm["pool"])):
				from_s = vm["pool"]

				new_from_s = make_pool_changes(pools[from_s],tot_pool,goals,remove_vm=vm,verbose=False)
				new_to_s   = make_pool_changes(pools[p],tot_pool,goals,add_vm=vm,verbose=False)

				print("...Does moving",vm["name"],"from",vm["pool"],"to",p,"make the scores better?")

				print("  % Imbalance(src): ", end="")
				print_scores(pools[from_s]["goal_scores"])
				print(" -> ", end="")
				print_scores(new_from_s["goal_scores"])
				print("")

				print("  % Imbalance(dst): ", end="")
				print_scores(pools[p]["goal_scores"])
				print(" -> ", end="")
				print_scores(new_to_s["goal_scores"])
				print("")

				# Did this improve anything?
				if (tot_score_is_better_than_sum_only(pools[from_s]["goal_scores"],
							     	new_from_s["goal_scores"]) and

			    		tot_score_is_better_than_sum_only(pools[p]["goal_scores"],
							     new_to_s["goal_scores"])):
			
					improvement = 0

					for i in range(0,len(pools[from_s]["goal_scores"])):
						improvement += abs(pools[from_s]["goal_scores"][i] -
								   new_from_s["goal_scores"][i])

						improvement += abs(pools[p]["goal_scores"][i] -
								   new_to_s["goal_scores"][i])

					print("Yes, improved by", improvement)

					if (improvement > best_score_change):
						print("New best improvement")

						best_server_to_move = vm
						best_server_dest    = p
						best_score_change   = improvement
						

				else:
					print("No")

	return (best_server_to_move,best_server_dest)
#
#----------------------------------------------------------------------
#
def move_one_server(vm, pools, to_pool, goals, this_move_num, max_concurrent_moves, dry_run, verbose):
	from_pool = vm["pool"]

	descr = "Move VM '" + vm["name"] + \
		"' from pool '" + from_pool + \
		"' to pool '" + to_pool + "'"

	if (verbose or dry_run):
		print("vMotion(" + str(this_move_num) + 
			"): " + descr)

	tot_pool = pools[TOTAL_NAME]

	pools[from_pool] = make_pool_changes(pools[from_pool],tot_pool,goals,remove_vm=vm,verbose=verbose)
	pools[to_pool]   = make_pool_changes(pools[to_pool],tot_pool,goals,add_vm=vm,verbose=verbose)

	if (not dry_run):
		vmotion_vm(vm["object"],pools[to_pool]["object"],
			   descr, verbose, max_concurrent_moves)
	
#
#----------------------------------------------------------------------
#
def move_servers(pools, all_vms, goals, max_moves, max_imbalanced, dry_run, verbose, max_concurrent_moves):
	move_num = 0

	cur_max_imb = compute_max_imbalanced(pools)
	do_more = (max_moves > 0) and (cur_max_imb > max_imbalanced)

	while (do_more):
		(best_server,dest_pool) = find_best_server_move(pools, all_vms, goals, dry_run, verbose)

		if (best_server is not None):
			move_num += 1
			move_one_server(best_server, pools, dest_pool, goals, move_num, max_concurrent_moves, dry_run, verbose)

			all_vms.remove(best_server)
		else:
			if (verbose):
				print("No more possible moves that improve the score")

			do_more = False

	
		cur_max_imb = compute_max_imbalanced(pools)

		if (cur_max_imb <= max_imbalanced):
			do_more = False

			if (verbose):
				print("Max imbalanced goal achived, desired %",max_imbalanced * 100.0,"now %", cur_max_imb * 100.0)

		if (move_num >= max_moves):
			do_more = False

			if (verbose):
				print("Max # of moves done", move_num)

		if (len(all_vms) == 0):
			do_more = False

			if (verbose):
				print("All VMs have been moved (at least) once")

#
#----------------------------------------------------------------------
#

def csv_list(s):
	return s.split(',')

def percent(s):
	if (s.endswith("%")):
		s = s[:-1]
	
	return float(s)

def parse_args():
	parser = argparse.ArgumentParser(
			prog='balanace-storage',
			description='Balance Storage Pools using vMotion')

	parser.add_argument('--vm-status-select', default="inactive-first",
		choices=forgiveChoices.forgive_choice_list(['active-first','inactive-first','neither-first']),
		action=forgiveChoices.forgive_choice_action,
		help='Which type of VM to move first? Inactive systems, Active systems, or "neither"')

	parser.add_argument('--vm-size-select', default="largest-first",
		choices=forgiveChoices.forgive_choice_list(['largest-first','smallest-first','neither-first']),
		action=forgiveChoices.forgive_choice_action,
		help='Which size of VM to move first? Large systems, Small systems, or "neither"')

	parser.add_argument('--vm-select-mode', default="status-then-size",
		choices=forgiveChoices.forgive_choice_list(['size-then-status','status-then-size','totally-random']),
		action=forgiveChoices.forgive_choice_action,
		help='Consider size before status, the other way, or just in no order?')

	parser.add_argument('--balance-goals',
		help='Determine how to decide if pools are balanced (e.g. 2.5a+0.5i;2v)',
		default='v;a;i')

	parser.add_argument('--max-concurrent-moves',
		help='How many vMotion requests to start at the same time?',
		type=int, default=10)

	parser.add_argument('--select', 
	    choices=forgiveChoices.forgive_choice_list(['active', 'inactive', 'both']),
	    help='What VMs to include (def=all systems)',
	    action=forgiveChoices.forgive_choice_action,
	    default='both')

	parser.add_argument('--max-moves', type=int, default=100,
		help='Maximum # of VMs to move') 

	parser.add_argument('--imbalance-goal', type=percent, default=10.0,
		help='Maximum imbalance goal (0..100,0=perfectly ' + \
		     'balanced, def=10)') 

	parser.add_argument('--dry-run', default=False, action="store_true",
		help='Show the actions, but do not perform any moves')

	parser.add_argument('--info-only', default=False, action="store_true",
		help='Show current status of the pools, but take no action')

	parser.add_argument('--vm-folders', default=[], type=csv_list,
		help='Limit VMs to ones only in specific folders ' + \
		     '(comma seperated)')

	parser.add_argument('--verbose', '-v', default=False, 
		action="store_true")

	parser.add_argument('server', help="VCSA server to use")

	parser.add_argument('pools', default=[], nargs='+',
		    help='List of Storage Pools (and weights) to balance')

	return parser.parse_args()

#
#----------------------------------------------------------------------
#
def find_all_vms(pools):
	all_vms = []

	for p in pools:
		if (p != TOTAL_NAME):
			all_vms.extend(pools[p]["eligible_vms"])

	return all_vms

#
#----------------------------------------------------------------------
#
def show_weighting_cats(file=sys.stderr):
	print("Weighting catergories: u,f,s,U,F,a,i,t,v,V", file=file)

	for (f,l) in FIELD_TO_LETTER.items():
		print("\t",l,"=",FIELD_TO_DESCR[f], file=file)

def show_err_balance_weight(file=sys.stderr):
	print("Invalid --balance-weight specified", file=file)

	print("", file=file)

	show_weighting_cats(file)

	
#
#----------------------------------------------------------------------
#

def main():
	pools = {}

	args = parse_args()

	server = args.server
	verbose = args.verbose or True		# Force true for now
	dry_run = args.dry_run
	vm_selection = args.select
	info_only = args.info_only

	# Try to load the balance-goals, error out if necessary
	print("Balance Goals: ",args.balance_goals)

	goals = datastoreScore.WholeScore(args.balance_goals)

	#(has_size,has_num) = goals.score_types()
	set_sorting_style(args.vm_select_mode,args.vm_size_select,args.vm_status_select)

	if (not goals.is_ok()):
		show_error_balance_weight()
		sys.exit(1)

	for p in args.pools:
		weight = 1.0

		if (":" in p):
			(p,weight) = p.split(":")
			weight = float(weight)

		pools[p] = { 'weight' : weight, 'name' : p }

	context = loginutils.netlablogin(server)
	
	# Get the objects from the names, exit if one or more is not found
	ok = find_all_pools(context,pools)

	if (not ok):
		sys.exit(1)

	gather_pool_info(pools,vm_selection, folders=args.vm_folders)
	compute_totals(pools)

	all_vms = find_all_vms(pools)

	# Show ahead of time
	if (verbose):
		print_pools(pools,"BEFORE", vm_selection, goals)

	# Prune the list if necessary
	pools = remove_nonready_pools(pools)

	# Recompute totals (if pools were removed)
	compute_totals(pools)
	compute_pool_weights(pools)
	compute_pool_scores(pools, goals)

	#
	# You need at least two pools to do migrations
	#
	if (len(pools) > 1):
		#sort_pool_vms(pools)

		max_imbalance = args.imbalance_goal / 100.0	# Convert to a float 0..1

		move_servers(pools,all_vms, goals, args.max_moves, max_imbalance, dry_run, 
			     verbose,args.max_concurrent_moves)

		# Wait for last tasks to end
		if (not dry_run):
			wait_for_n_tasks(verbose=verbose)

		# Show after
		if ((verbose) and (not dry_run)):
			print_pools(pools,"AFTER",vm_selection, goals,True)

	else:
		print("No enough pools to migrate (need at least 2 available)")


	sambautils.disable_user(ADMIN_SVC_ACCT)


main()	
