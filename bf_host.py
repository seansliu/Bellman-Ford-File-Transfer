# Bellman-Ford File Transfer Host
#
# Written by Sean Liu

import socket
import select
import signal
import sys
from Queue import Queue
from threading import Thread
import datetime as dt
from configurations import *
import time


TIMEOUT = 0				# seconds, timeout for updating neighbors with vectors
forwarding_table = {}	# maps destinations to costs and links
neighbors = {}			# maps neighbors to costs and update times
last_update = 0			# time of last ROUTE UPDATE message sent
inbox = Queue()			# queue for received segments
outbox = Queue()		# queue for outgoing segments
host_sock = 0			# host socket
send_sock = 0			# socket for sending
host_addr = 0			# host IP address and port number
incoming_files = {}		# maps filenames to dicts containing segments


def sighandler(signum, frame):
	"""graceful exit"""
	shutdown()


def shutdown():
	"""shuts down the program"""
	print 'Closing Bellman-Ford Host...\n'
	try:
		host_sock.close()
		send_sock.close()
	except:
		pass
	print '--------------------Bellman-Ford Host closed--------------------\n'
	sys.exit(1)


def die(msg):
	"""exits the program with given error message"""
	print 'ERROR:', msg
	raise sys.exit()


def create_UDP_socket():
	"""initializes and returns a UDP socket"""
	return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def addr_to_str(addr):
	"""converts an address to string"""
	return ':'.join((addr[0], str(addr[1])))


def addr_from_str(addr_str):
	"""converts an address from a string"""
	info = addr_str.split(':')
	addr = (info[0], int(info[1]))
	return addr


def check_commandline(args, msg):
	"""checks the command line"""
	if args != len(sys.argv):
		die(msg)


def initialize_host():
	"""initializes host"""
	try:
		f = open(sys.argv[1], 'r')
	except:
		die('could not open file %s' %sys.argv[1])

	try:
		info = f.readline().rstrip().split()
		host_port = int(info[0])
		global TIMEOUT
		TIMEOUT = int(float(info[1]))

		# initialize forwarding table
		for line in f:
			line = line.rstrip()
			if line == '':
				continue
			info = line.split()
			neighbor_addr = info[0]
			cost = float(info[1])
			neighbors[neighbor_addr] = [cost, dt.datetime.now(), True]
			forwarding_table[neighbor_addr] = [cost, neighbor_addr]

		global last_update
		last_update = dt.datetime.now()
	except:
		die('could not initialize host from file %s' %sys.argv[1])

	global host_addr
	host_addr = (socket.gethostbyname(socket.gethostname()), host_port)
	global host_sock
	host_sock = create_UDP_socket()
	try:
		host_sock.bind(host_addr)
	except:
		die('could not bind host UDP socket')
	global send_sock
	send_sock = create_UDP_socket()


def send_packet(packet, dest_str):
	"""sends a packet to dest_str"""
	if (not dest_str in neighbors) or (not neighbors[dest_str][2]) or \
	forwarding_table[dest_str][0] == INFINITY:
		return False
	send_sock.sendto(packet, (addr_from_str(dest_str)))
	return True


# thread
def update_neighbors():
	"""checks last update sent to neighbors and checks for their inactivity"""
	limit = dt.timedelta(seconds=3*TIMEOUT)
	timeout = dt.timedelta(seconds=TIMEOUT)
	while 1:
		now = dt.datetime.now()
		if now - last_update > timeout:
			broadcast_vtable()			# send distance vector
		n_addrs = neighbors.keys()
		for addr in n_addrs:
			n = neighbors[addr]
			if not n[2]:
				continue
			if now - n[1] > limit:
				deactivate_link(addr)	# deactivate neighbots that timed out


def broadcast_vtable():
	"""sends distance vector to active nieighbors"""
	vectors = []
	host_addr_str = addr_to_str(host_addr)
	addresses = neighbors.keys()
	dests = forwarding_table.keys()
	for address in addresses:
		if not neighbors[address][2]:
			continue
		for dest in dests:
			vector = forwarding_table[dest]
			if vector[1] == address and dest != address:
				v = (dest, 'inf', vector[1])	# poison reverse
			else:
				v = (dest, str(vector[0]), vector[1])
			vectors.append(','.join(v))
		v_table_packet = ' '.join((H_ROUTE_UPDATE, host_addr_str, \
			' '.join(vectors)))
		send_packet(v_table_packet, address)

	global last_update
	last_update = dt.datetime.now()


# thread
def process_packets():
	"""processes incoming packets from inbox queue"""
	while 1:
		packet = inbox.get()
		p_contents = packet.split(' ', 2)
		p_type = p_contents[0]

		if p_type == H_ROUTE_UPDATE:
			update_table(p_contents[1], p_contents[2])
		
		elif p_type == H_LINK_UP:
			activate_link(p_contents[1])
		
		elif p_type == H_LINK_DOWN:
			deactivate_link(p_contents[1])
		
		elif p_type == H_CHGCOST:
			update_cost(p_contents[1], p_contents[2])
		
		elif p_type == H_FILE:
			handle_file(packet)
		
		else:
			print 'WARNING: unrecognized packet received.\n'


def update_table_neighbors():
	"""updates forwarding_table with neighbors information"""
	changed = False
	addresses = neighbors.keys()
	for a in addresses:
		vector = forwarding_table[a]
		n = neighbors[a]
		if (n[0] < vector[0]) and n[2]:
			vector[0] = n[0]
			vector[1] = a
			changed = True
	return changed


def update_table(source_str, vector_msg):
	"""updates the forwarding table from a ROUTE UPDATE message"""
	# update neighbors dictionary
	if source_str in neighbors:
		neighbors[source_str][2] = True
		neighbors[source_str][1] = dt.datetime.now()
	else:
		neighbors[source_str] = [INFINITY, dt.datetime.now(), True]

	# update source entry in forwarding table
	host_addr_str = ':'.join((host_addr[0], str(host_addr[1])))
	vectors = vector_msg.split(' ')	
	for i in range(len(vectors)):
		vectors[i] = vectors[i].split(',')
		if vectors[i][0] != host_addr_str:
			continue
		cost = float(vectors[i][1])
		link = vectors[i][2]
		if source_str in forwarding_table:
			entry = forwarding_table[source_str]
			if link == host_addr_str and entry[1] == source_str:
				entry[0] = cost
				neighbors[source_str][0] = cost
		else:
			forwarding_table[source_str] = [cost, source_str]
			neighbors[source_str][0] = cost

	# update the rest of forwarding table
	cost1 = forwarding_table[source_str][0]
	link = forwarding_table[source_str][1]
	for vector in vectors:
		dest = vector[0]
		if dest == host_addr_str or vector[2] == host_addr_str:
			continue
		cost = cost1 + float(vector[1])
		if dest in forwarding_table:
			entry = forwarding_table[dest]
			current_cost = entry[0]
			if entry[1] == source_str:
				entry[0] = cost
			elif cost < current_cost:
				entry[0] = cost
				entry[1] = link
		else:
			forwarding_table[dest] = [cost, link]

	update_table_neighbors()


def activate_link(addr_str):
	"""activates a link to given neighbor"""
	neighbors[addr_str][2] = True
	neighbors[addr_str][1] = dt.datetime.now()
	vector = forwarding_table[addr_str]
	cost = neighbors[addr_str][0]
	if cost < vector[0]:
		vector[0] = cost
		vector[1] = addr_str
		broadcast_vtable()


def deactivate_link(addr_str):
	"""deactivates a link to given neighbor"""
	neighbors[addr_str][2] = False
	changed = False
	neighbors[addr_str][1] = dt.datetime.now()
	addresses = forwarding_table.keys()
	for addr in addresses:
		vector = forwarding_table[addr]
		if vector[1] == addr_str:
			vector[0] = INFINITY
			changed = True
	changed = changed or update_table_neighbors()
	if changed:
		broadcast_vtable()


def update_cost(addr_str, cost):
	"""updates the cost to a link"""
	c = float(cost)
	old = neighbors[addr_str][0]
	neighbors[addr_str][0] = c
	diff = c - old
	addresses = forwarding_table.keys()
	changed = False
	for addr in addresses:
		vector = forwarding_table[addr]
		if vector[1] == addr_str:
			vector[0] += diff
			changed = True
	changed = changed or update_table_neighbors()
	if changed:
		broadcast_vtable()


def handle_file(ft_packet):
	"""handles a file transfer"""
	p_contents = ft_packet.split(' ', 5)
	dest_str = p_contents[1]
	source_str = p_contents[2]
	filename = p_contents[3]
	seq_num = int(p_contents[4])

	print 'Packet %d received for %s' %(seq_num, filename)
	print '\tSource: %s' %source_str
	print '\tDestination %s '%dest_str

	host_str = addr_to_str(host_addr)
	if dest_str == host_str:
		if not filename in incoming_files:
			incoming_files[filename] = {}
		f_dict = incoming_files[filename]
		try:
			f_dict[seq_num] = p_contents[5]
		except: # EOF
			f_dict['size'] = seq_num
		if ('size' in f_dict) and (len(f_dict) == f_dict['size']+1):
			del f_dict['size']
			save_file(filename, f_dict)
			del incoming_files[filename]

	# forward packet
	else:
		vector = forwarding_table[dest_str]
		if vector[0] == INFINITY:
			print 'Packet dropped - destination no longer reachable.'
			return
		link = vector[1]
		print '\tNext hop: %s' %link
		if send_packet(ft_packet, link):
			print '\tPacket sent.\n'
		else:
			print '\tPacket dropped.\n'
		


def save_file(filename, file_dict):
	"""saves a file from its components in a dictionary"""
	try:
		fp = open(filename, 'wb')
		for i in sorted(file_dict.keys()):
			fp.write(file_dict[i])
		fp.close()
		print 'File %s successfully received and saved.\n' %filename
	except:
		print 'Failed to save file %s\n' %filename


# thread
def recv_packets():
	"""receives packets and puts them in the inbox queue"""
	# non-blocking message reception
	input_socks = [host_sock]
	while 1:
		read, write, error = select.select(input_socks, [], [])
		if error:
			die('socket select error')
		for s in read:
			packet, from_addr = s.recvfrom(MSS)
			inbox.put(packet)


def show_routes():
	"""prints the forwarding_table"""
	print 'Timestamp:', dt.datetime.now()
	print 'Destination\t\t| Cost\t\t| Link'
	addresses = forwarding_table.keys()
	for addr in addresses:
		vector = forwarding_table[addr]
		print '%s\t| %7f\t| %s' %(addr, vector[0], vector[1])
	print ''


def link_up(ip_addr, port):
	"""restores a link with another host"""
	addr = ':'.join((ip_addr, port))
	if not addr in neighbors:
		print 'No neighbor at %s\n' %addr
		return

	if neighbors[addr][2]:
		print 'Link to %s already up.\n' %addr
		return

	packet = ' '.join((H_LINK_UP, addr_to_str(host_addr)))
	send_packet(packet, addr)
	activate_link(addr)


def link_down(ip_addr, port):
	"""kills a link with another host"""
	addr = ':'.join((ip_addr, port))
	if not addr in neighbors:
		print 'No neighbor at %s\n' %addr
		return

	if not neighbors[addr][2]:
		print 'Link to %s already down.\n' %addr
		return

	packet = ' '.join((H_LINK_DOWN, addr_to_str(host_addr)))
	send_packet(packet, addr)
	deactivate_link(addr)


def change_cost(ip_addr, port, cost):
	"""updates the cost of a link"""
	addr = ':'.join((ip_addr, port))
	if not addr in neighbors:
		print 'No neighbor at %s\n' %addr
		return

	if not neighbors[addr][2]:
		print 'Link to %s currently down. Could not change cost.\n' %addr
		return

	packet = ' '.join((H_CHGCOST, addr_to_str(host_addr), cost))
	send_packet(packet, addr)
	update_cost(addr, cost)


def transfer_file(filename, ip_addr, port):
	"""transfers a file to another host"""
	# checks
	to_addr   = ':'.join((ip_addr, port))
	if not to_addr in forwarding_table:
		print 'ERROR: unknown destination %s\n' %to_addr
		return
	vector = forwarding_table[to_addr]
	if vector[0] == INFINITY:
		print 'ERROR: destination is currently currently unreachable.\n'
		return
	try:
		fp = open(filename, 'rb')
	except:
		print 'ERROR: could not open file %s\n' %filename
		return

	# create header
	print 'Initiating file transfer for %s ...\n' %filename
	from_addr = addr_to_str(host_addr)
	header = ' '.join((H_FILE, to_addr, from_addr, filename))
	data_size = MSS - len(header) - 20	# extra padding for sequence number

	# create packets and send
	seq_num = 0
	f_seg = fp.read(data_size)
	while f_seg != '':
		print 'File Sequence Number: %3d\tNext hop: %s' %(seq_num, vector[1])
		segment = ' '.join((header, str(seq_num), f_seg))
		if not send_packet(segment, vector[1]):
			print 'File transfer failed.\n'
			fp.close()
			return
		f_seg = fp.read(data_size)
		seq_num += 1
	print 'EOF  Sequence Number: %3d\tNext hop: %s' %(seq_num, vector[1])
	eof = ' '.join((header, str(seq_num)))
	if send_packet(eof, vector[1]):
		print 'File sent successfully.\n'
	else:
		print 'File transfer failed.\n'

	fp.close()


def main():
	"""runs the bf_host"""
	signal.signal(signal.SIGINT, sighandler)
	check_commandline(2, 'correct use: python bf_host.py <host file>')
	
	print 'Starting Bellman-Ford Host...\n'
	initialize_host()
	print 'Listening on: %s\n' %addr_to_str(host_addr)

	receive_thread = Thread(target=process_packets)
	receive_thread.daemon = True
	receive_thread.start()

	listen_thread = Thread(target=recv_packets)
	listen_thread.daemon = True
	listen_thread.start()

	update_thread = Thread(target=update_neighbors)
	update_thread.daemon = True
	update_thread.start()

	broadcast_vtable()
	print '-------------------Bellman-Ford Host started--------------------\n'

	input_fd = [sys.stdin]
	while 1:
		# non-blocking reading from stdin
		read, write, error = select.select(input_fd, [], [])
		if not (sys.stdin in read):
			continue

		user_input = sys.stdin.readline().strip()
		command = user_input.split(' ', 3)
		c = command[0]

		if c == '':
			continue

		elif c == C_SHOWRT:
			show_routes()

		elif c == C_CLOSE:
			shutdown()

		elif c == C_LINK_UP:
			if len(command) < 3:
				print 'Correct use: %s <IP address> <port>\n' %C_LINK_IP
				continue
			link_up(command[1], command[2])
		
		elif c == C_LINK_DOWN:
			if len(command) < 3:
				print 'Correct use: %s <IP address> <port>\n' %C_LINK_DOWN
				continue
			link_down(command[1], command[2])
		
		elif c == C_CHGCOST:
			if len(command) < 4:
				print 'Correct use: %s <IP address> <port> <cost>\n' \
				%C_CHGCOST
				continue
			change_cost(command[1], command[2], command[3])
		
		elif c == C_TRANSFER:
			if len(command) < 4:
				print 'Correct use: %s <filename> <IP address> <port> \n' \
				%C_TRANSFER
				continue
			transfer_file(command[1], command[2], command[3])
		
		else:
			print 'ERROR: unrecognized command.\n'



if __name__ == '__main__':
	main()
