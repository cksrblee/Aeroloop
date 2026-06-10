import signal
import time
import subprocess
import os

print("Initial SIGCHLD handler:", signal.getsignal(signal.SIGCHLD))

old_handler = signal.signal(signal.SIGCHLD, signal.SIG_DFL)
print("Set to SIG_DFL. Launching sleep...")

pid = os.fork()
if pid == 0:
    time.sleep(1)
    os._exit(0)

# parent
print("Waiting for child...")
res = os.waitpid(pid, 0)
print("Waitpid returned:", res)

signal.signal(signal.SIGCHLD, old_handler)
print("Restored.")
