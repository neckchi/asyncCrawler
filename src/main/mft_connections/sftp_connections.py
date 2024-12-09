import paramiko
import logging
import time


class Sftp:
    def __init__(self, hostname, username, password, port=22):
        self.transport = None
        self.auth = None
        self.connection = None
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port

    def connect(self):
        """Connects to the sftp server and returns the sftp connection object"""
        try:
            self.transport = paramiko.Transport((self.hostname, self.port))
            self.auth = self.transport.connect(
                hostkey=None, username=self.username, password=self.password)
            self.connection = paramiko.SFTPClient.from_transport(
                self.transport)
        except Exception as err:
            raise Exception(err)
        finally:
            logging.info(f"Connected to {self.hostname} as {self.username}.")

    def disconnect(self):
        """Closes the sftp connection"""
        if self.connection:
            self.connection.close()
        if self.transport:
            self.transport.close()
        logging.info(f"Disconnected from host {self.hostname}")

    def upload(self, source_local_path, remote_path, file_name):
        """
        Uploads the source files from local to the sftp server.
        """
        while (retries := 10) > 0:
            try:
                # Test if remote_path exists
                self.connection.chdir(remote_path)
                logging.info('cd working directory')
                break
            except IOError:
                self.connection.mkdir(remote_path)  # Create remote_path
                self.connection.chdir(remote_path)
                logging.info('cd working directory')
                time.sleep(3)
                retries -= 1
            finally:
                logging.info(
                    f"uploading to {self.hostname} as {self.username} [(remote path: {remote_path});(file name:{file_name})(source local path: {source_local_path})]"
                )

                # Download file from SFTP
                self.connection.put(source_local_path, file_name)
                logging.info("upload completed")

        if retries == 0:
            raise PermissionError
