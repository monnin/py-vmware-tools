VMWare Tools

I use the tools to help me automate some activities for a vSphere cluster. They
are likely not going to work for you without some modifications.  You will
at least need to change the login code 

from:

	context = loginutils.netlablogin(server)

to:

	context = loginutils.simplelogin(server)

The "simplelogin" just (always) prompts for the username and password, while 
the netlablogin is what I use locally.  (It creates a random password for
a specific account, and then enables/disables the account.)

Layout:

	lib/		The python modules needed to run the code
	bin/		Tools that do not alter VMWare, just queries it
	sbin/		Tools that will make changes to VMWare (be careful here)

