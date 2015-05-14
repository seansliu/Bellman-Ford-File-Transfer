Bellman-Ford File Transfer Host
written by Sean Liu sl3497


NOTES: I am using my late days for this assignment!

INTRODUCTION

This program implements the Bellman-Ford algorithm to maintain links between 
other hosts running the same program in the same system. The links can be 
updated, and a user may use this network to send files from one host to 
another. All communication is implemented with UDP sockets.


HOW TO RUN

0. Confirm client settings in client.txt files and configuration.py.

1. Start the Host: python bf_host.py <client file name>

2. Enter commands as specified below to view and update the network, as well 
as transfer files between hosts.

3. The program can be gracefully shut down by entering the command "CLOSE" or 
sending the SIGINT signal with Control-C.


PROGRAM DESIGN

The main challenge was implementing the Bellman-Ford algorithm for maintaining 
the network of hosts. I had to think carefully about how to update the 
forwarding table after receiving a ROUTE_UPDATE message from a neighbor. 

Bellman-Ford File Transfer Host - bf_host.py
The host had 3 main tasks: allow a user to update the host's information 
regarding its neighbors, automatically update the forwarding table constantly, 
and transfer files for the user. To listen to the user and process commands, I 
used a non-blocking accept method with the select module, only accepting from 
stdin when the user entered a command. To automatically udpate the network 
information, I had the host send ROUTE_UPDATE messages anytime the forwarding 
table was updated and every TIMEOUT. When receiving a ROUTE_UPDATE message, the 
host first updates the link between itself and the sender neighbor, then the 
rest of the table. I also implemented poison reverse as specified in the 
assignment. Once the Bellman-Ford algorithm was successfully implemented, file 
transfer was simple. My program creates a header, with sequence number, and 
sends the file in packets, hop by hop. To save file information, the 
destination saves the packets in a dictionary, only reconstructing the file 
once all packets have been received. Since this is done over UDP, some packets
can be lost. Any filetype can be sent, since I read and write in binary mode. 
However, larger files are harder to send successfully, since larger files 
mean more packets and therefore higher probability of one or more lost packets. 

Configuration - configuration.py
To make it easy to change configuration values, such as MSS and user commands, 
I placed all constants in configuration.py. Therefore, if a user/admin wants 
to change these settings, one just has to open this file and alter its values.

Host and Neighbor Specifications - clientN.txt
clientN.txt files contain information as specified in the assignment to 
initialize a host. The host reads the file and initializes its information. To
speed up the updating process, I used TIMEOUT value of 5 in my client files.


COMMANDS

The user can use the following commands:

- SHOWRT
	prints the forwarding table

- LINKDOWN [IP address] [port number]
	terminates a link to a neighbor

- LINKUP [IP address] [port number]
	revives a link to a neighbor

- CHANGECOST [IP address] [port number] [new cost]
	changes a cost to a neighbor

- TRANSFER [file name] [IP address] [port number]
	sends the file to desination

- CLOSE
	terminates the host


TEST CASES

I have attached clientN.txt files for testing. They contain information for 
the test case specified in the assignment PDF. Use any file for file 
transmission testing.
