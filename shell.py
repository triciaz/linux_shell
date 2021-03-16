import os
import sys
import subprocess
import shlex
import signal

class Job:
    next_job_number = 1

    def __init__(self, process_id, command, status=True):
        self.process_id = process_id
        self.job_number = Job.next_job_number
        Job.next_job_number += 1
        self.command = command
        self.status = status

    def __str__(self):
        return str(self.process_id) + " " + str(self.job_number) + " " + str(self.command) + " " + str(self.status)

    def __repr__(self):
        return self.__str__()

class Shell:
    def __init__(self, current_directory=os.getcwd(), jobs=[], messages=[], foreground_job=None):
        self.current_directory = current_directory
        self.jobs = jobs
        self.messages = messages
        self.foreground_job = foreground_job
        self.environment = {"PATH":"/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"}
        signal.signal(signal.SIGINT, self.get_sigint_handler())
        signal.signal(signal.SIGCHLD, self.get_sigchld_handler())
        signal.signal(signal.SIGTSTP, self.get_sigstop_handler())

    def get_sigint_handler(self):
        def sigint_handler(sig, frame):
            if self.foreground_job:
                os.kill(self.foreground_job, signal.SIGINT)
        return sigint_handler

    def get_sigchld_handler(self):
        def sigchld_handler(sig, frame):
            if self.foreground_job:
                self.foreground_job = None
        return sigchld_handler

    def get_sigstop_handler(self):
        def sigstop_handler(sig, frame):
            if self.foreground_job:
                os.kill(self.foreground_job, signal.SIGTSTP)
                self.foreground_job = None
                for j in self.jobs:
                    if j.process_id == self.foreground_job:
                        j.status = False
            else:
                print("no foreground")
        return sigstop_handler

    def wait_for_process(self):
        signal.pause()
        self.foreground_job = None

    def loop(self):
        while True:
            print(os.path.basename(os.getcwd()) + ">", end = "")
            command = input()
            print(command)
            command_list = shlex.split(command)
            if command == "exit":
                break
            elif len(command_list) == 0:
                continue
            elif command_list[0] == "cd":
                try:
                    os.chdir(command_list[1])
                    self.current_directory = os.getcwd()
                except FileNotFoundError:
                    print("no such file or directory: " + command_list[1])
                except NotADirectoryError:
                    print("not a directory: " + command_list[1])
            elif command_list[0] == "ls":
                for fileName in [l for l in os.listdir() if l[0] != '.']:
                    print(fileName)
            elif command_list[0] == "pwd":
                print(os.getcwd())
            elif command_list[0] == "jobs":
                print(self.jobs)
            elif command_list[0] == "fg":
                try:
                    job_number = int(command_list[1])
                    for j in self.jobs:
                        if j.job_number == job_number:
                            os.kill(j.process_id, signal.SIGCONT)
                            j.status = True
                            self.foreground_job = j.process_id
                            self.wait_for_process()
                except ValueError:
                    print("fg requires integer argument")
            elif command_list[0]  == "bg":
                try:
                    job_number = int(command_list[1])
                    for j in self.jobs:
                        if j.job_number == job_number:
                            os.kill(j.process_id, signal.SIGCONT)
                            j.status = True
                            self.foreground_job = j.process_id
                            self.wait_for_process()
                except ValueError:
                    print("bg requires integer argument")
            else:
                pid = os.fork()
                if pid == 0: #i am the child
                    os.setpgid(0, 0)
                    executable = os.path.join(self.current_directory, command_list[0])
                    if not os.access(executable, os.X_OK):
                        for p in self.environment["PATH"].split(":"):
                            if os.access(os.path.join(p, command_list[0]), os.X_OK):
                                executable = os.path.join(p, command_list[0])
                                break
                    os.execve(executable, command_list, {})
                else:
                    self.jobs.append(Job(pid, command))
                    self.foreground_job = pid
                    self.wait_for_process()
                #subprocess.run(command_list, stdin=sys.stdin, stdout=sys.stdout, shell=False)

            if " | " in command:
                std_in, std_out = (0, 0)
                std_in = os.dup(0)
                std_out = os.dup(1)

                fd1 = os.dup(std_in)
                for c in command.split("|"):
                    os.dup2(fd1, 0)
                    os.close(fd1)
                    if c == command.split("|")[-1]:
                        fd2 = os.dup(std_out)
                    else:
                        fd1, fd2 = os.pipe()
                    os.dup2(fd2, 1)
                    os.close(fd2)
                    try:
                        subprocess.run(c.strip().split())
                    except Exception:
                        print("psh: command not found: {}".format(c.strip()))
                os.dup2(std_in, 0)
                os.dup2(std_out, 1)
                os.close(std_in)
                os.close(std_out)

            jobs_to_remove = []
            for j in self.jobs:
                pid, status = os.waitpid(j.process_id, os.WNOHANG)
                if os.WIFSIGNALED(status):
                    continue
                if os.WIFEXITED(status):
                    jobs_to_remove.append(j)
                    print("done: " + str(j))
            self.jobs = [j for j in self.jobs if not j in jobs_to_remove]
shell = Shell()
shell.loop()
