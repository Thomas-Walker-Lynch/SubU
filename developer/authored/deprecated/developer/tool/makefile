# after adding this file `make dependency` should be run again

RESOURCE:=$(REPO_HOME)/tool_shared/third_party/resource/developer
include $(RESOURCE)/make/environment_RT_0

# override defaults
LIBDIR=scratchpad

# assign a compiler to use
C=gcc

# _GNU_SOURCE is needed to get ucred, the credentials of the pid that connects to a socket
CFLAGS= -Werror -ggdb -D_GNU_SOURCE -DDEBUG -DDEBUGDB -include "$(RESOURCE)/make/RT_0.h" -I$(INCDIR) 
LINKFLAGS=-L$(LIBDIR) -L/usr/lib64 -L/usr/lib -l$(PROJECT) -lsqlite3

# Import the rules. The dash prefix means to ignore include errors. This is
# required because the DEPFILE might not exist yet.
include $(RESOURCE)/make/targets
-include $(DEPFILE)
