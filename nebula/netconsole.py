import logging
import select
import socket
import threading
import time

log = logging.getLogger(__name__)


class netconsole:
    """ Net Console """

    def __init__(self, port=23456, logfilename="log.txt"):
        self.port = port
        self.host = "127.0.0.1"
        self.sockets = []
        self.rxbuff_max = 1024
        self.listen_thread_run = True
        self.logfilename = logfilename
        self.select_timeout = 2.0
        self.print_to_console = True

        file = open(self.logfilename, "w")
        file.close()

    def start_log(self):
        """ Trigger monitoring with network interface """
        self.listen_thread_run = True
        log.info("Launching listening thread")
        self.thread = threading.Thread(target=self.listen, args=())
        self.thread.start()

    def stop_log(self):
        """ Stop monitoring with network interface """
        self.listen_thread_run = False
        log.info("Waiting for thread")
        self.thread.join()
        log.info("Thread joined")

    def listen(self):
        file = open(self.logfilename, "w")
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self.sock.settimeout(10)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(1)
        self.sockets = [self.server_sock]
        log.info("Started listening")
        while self.listen_thread_run:
            time.sleep(1)
            read_sockets, write_sockets, error_sockets = select.select(
                self.sockets, [], [], self.select_timeout
            )

            for sock in read_sockets:
                if sock == self.server_sock:
                    sockfd, addr = self.server_sock.accept()
                    self.sockets.append(sockfd)
                    log.info("Connected by " + addr[0] + " " + str(addr[1]))
                else:
                    try:
                        data = sock.recv(self.rxbuff_max)
                        if data:
                            log.info("Got data of length " + str(len(data)) + " bytes")
                            file.write(str(data))
                            if self.print_to_console:
                                print("OK... " + str(data))
                    except Exception as ex:
                        log.warning("Exception occurred: " + str(ex.msg))
                        sock.close()
                        self.server_sock.remove(sock)
                        log.info("Closing connection")
                        continue
        self.server_sock.close()
        file.close()
        log.info("Listening thread closing")


if __name__ == "__main__":
    nc = netconsole()
    nc.start_log()
    time.sleep(30)
    nc.stop_log()
