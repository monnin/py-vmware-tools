
class OneScore:
	letters = "ufsUFvVait"
	lettype = "sSssSssnnn"	# What each letter is

	def __init__(self,s=""):
		if (s != ""):
			ok = self.parse(s)
		else:
			self.zero()

	def zero(self):
		self.items = {}
		self.total_weight = 0.0

		# Restart with an empty goal
		for ch in self.letters:
			self.items[ch] = 0.0


	# Count the # of "disk size" or "number of systems" items in one goal
	def has_types(self):
		has_num = 0
		has_size = 0
	
		for i in range(0,len(self.letters)):
			ch = letters[i]
			ty = lettype[i]

			if (self.items[ch] != 0.0):
				if (ty == "n"):
					has_num += 1
				if ((ty == "s") or (ty == "S")):
					has_size += 1

		return (has_size,has_num)

	def __str__(self):
		s = ""

		for ch in self.letters:
			if (self.items[ch] != 0.0):
				s += str(self.items[ch]) + ch + '+'
		
		if (len(s) > 0):
			s = s[:-1]	# Remove final +
		else:
			s = "0"

		return s

	def get(self,letter):
		return self.items.get(letter,None)

	def get0(self,letter):
		return self.items.get(letter,0.0)

	def set(self,letter,weight):
		ok = True
		#print("Trying to set",letter,"to",weight)

		if (letter in self.letters):
			oldweight = self.items[letter]

			self.items[letter] = weight

			# Recompute the total of the weighting
			self.total_weight += weight
			self.total_weight -= oldweight
			
		else:
			print("Illegal letter",letter)

			# An error!  Erase and return an error
			self.zero()
			ok = False

		return ok

	# Multiply = multiply the individual items together and add up
	# (Used to multiply current values to weights)

	def __mul__(self,other):
		total = 0.0

		#print("Start")

		for ch in self.letters:
			v = self.items[ch] * other.items[ch]
			#print("...",ch,self.items[ch],other.items[ch],"=",v)
			total += v

		#print("tot=",total,"weight=",self.total_weight)

		return total / self.total_weight

	#
	# Similar to __mul__ but accounts for the fact that
	#   a "free space" and a "used space" should not be counted in the same direction
	#
	def mul_w_adj(self,other):
		total = 0.0

		for i in range(0,len(self.letters)):
			ch = self.letters[i]
			ty = self.lettype[i]

			if (str.isupper(ty)):
				#v = self.items[ch] * (1.0-other.items[ch])
				v = -self.items[ch] * other.items[ch]
			else:
				v = self.items[ch] * other.items[ch]

			total += v	

		return total / self.total_weight

		

	def parse(self,s):
		ok = True
	
		# Restart with an empty goal
		self.zero()

		s = s.replace(" ","")

		all_items = s.split("+")

		total_weight = 0.0

		for s in all_items:
			letter = s[-1]	# Get the last character

			if (letter not in self.letters):
				ok = False
			else:
				weight = 1.0

				# Did the person include a weight?
				#  If so, then use that
				if (len(s) > 1):
					s = s[:-1]
					try:
						weight = float(s)
					except ValueError:
						ok = False
			
				if (ok):
					self.items[letter] = weight
					total_weight += weight

		self.total_weight = total_weight

		return ok

class WholeScore:
	def __init__(self,s = ""):
		ok = True

		if (s != ""):
			ok = self.parse(s)
		else:
			self.zero()

	def zero(self):
		self.goals = []

	def all_scores(self,poolScore):
		total = []

		for one_goal in self.goals:
			v = one_goal * poolScore
			#print("Got",v)

			total.append(v)

		return tuple(total)

	def all_scores_w_adj(self,poolScore):
		total = []

		for one_goal in self.goals:
			v = one_goal.mul_w_adj(poolScore)
			#print("Got",v)

			total.append(v)

		return tuple(total)

	# Count the # of "disk size" or "number of systems" items in all goals
	def has_types(self):
		has_num = 0
		has_size = 0

		for one_goal in self.goals:
			(size1,num1) = one_goal.has_types()

			has_num += num1
			has_size += size1
		
		return (has_size,has_num)

	def parse(self,s):
		ok = True

		# Restart with no goals
		self.zero()

		s = s.replace(" ","")

		all_goals = s.split(";")
		
		for s in all_goals:
			one_goal = OneScore(s)

			# If we can't parse it, then indicate a problem
			#  and erase the goals

			if (one_goal is None):
				ok = False
				self.goals = []	   # Erase partial

			# Once we get a "not ok", never re-create the list
			elif (ok == True):		
				self.goals.append(one_goal)

		return ok

	# Multiply = multiply the individual items together and add up
	def is_ok(self):
		return (len(self.goals) > 0)

	def __str__(self):
		s = ""
		i = 1

		for g in self.goals:
			if (s != ""):
				s += "\n"

			s += "Score #" + str(i) + "\n   " + str(g)	
			i += 1

		if (s == ""):
			s = "No Scores Defined"

		return s
