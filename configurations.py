# Bellman-Ford File Transfer Host Configurations
#
# Written by Sean Liu

# infinity
INFINITY = float('inf')

# maximum segment size
MSS = 4096	# bytes

# user commands
C_LINK_DOWN = 'LINKDOWN'
C_LINK_UP = 'LINKUP'
C_CHGCOST = 'CHANGECOST'
C_SHOWRT = 'SHOWRT'
C_CLOSE = 'CLOSE'
C_TRANSFER = 'TRANSFER'

# packet headers
H_FILE = 'f'
H_LINK_DOWN = 'ld'
H_LINK_UP = 'lu'
H_CHGCOST = 'c'
H_ROUTE_UPDATE = 'ru'