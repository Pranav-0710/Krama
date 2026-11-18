"""Windows "job objects": put a process in a box with limits.

A job object is a Windows feature that groups processes and limits them.
The self-check uses one so that the code Krama wrote:
    - cannot use more than a set amount of memory,
    - cannot start other programs (the job allows only 1 or 2 processes),
    - is killed, with anything it started, as soon as the job is closed.

The process is created paused, put in the job, and only then started, so it
cannot run any code before the limits apply.
"""

import ctypes
import subprocess
from ctypes import wintypes

CREATE_SUSPENDED = 0x00000004

LIMIT_ACTIVE_PROCESS = 0x00000008
LIMIT_PROCESS_MEMORY = 0x00000100
LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x00000400   # no crash pop-up windows
LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
EXTENDED_LIMIT_INFORMATION = 9


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class EXTENDED_LIMIT_INFO(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")

kernel32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
kernel32.SetInformationJobObject.restype = wintypes.BOOL
kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL
ntdll.NtResumeProcess.argtypes = (wintypes.HANDLE,)
ntdll.NtResumeProcess.restype = ctypes.c_long


def create_job(memory_limit, max_processes):
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    info = EXTENDED_LIMIT_INFO()
    info.BasicLimitInformation.LimitFlags = (LIMIT_ACTIVE_PROCESS | LIMIT_PROCESS_MEMORY
                                             | LIMIT_DIE_ON_UNHANDLED_EXCEPTION | LIMIT_KILL_ON_JOB_CLOSE)
    info.BasicLimitInformation.ActiveProcessLimit = max_processes
    info.ProcessMemoryLimit = memory_limit
    if not kernel32.SetInformationJobObject(job, EXTENDED_LIMIT_INFORMATION,
                                            ctypes.byref(info), ctypes.sizeof(info)):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(job)
        raise ctypes.WinError(error)
    return job


def run(command, options, memory_limit, max_processes, timeout):
    """Run `command` inside a limited job. Return (exit code, error text).

    Raises subprocess.TimeoutExpired if it runs too long (it is killed first).
    """
    job = create_job(memory_limit, max_processes)
    try:
        process = subprocess.Popen(command, creationflags=CREATE_SUSPENDED, **options)
        try:
            if not kernel32.AssignProcessToJobObject(job, int(process._handle)):
                raise ctypes.WinError(ctypes.get_last_error())
            status = ntdll.NtResumeProcess(int(process._handle))
            if status != 0:
                raise OSError(f"could not start the paused process (status {status & 0xFFFFFFFF:#x})")
        except OSError:
            process.kill()
            process.communicate()
            raise
        try:
            _, error = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            kernel32.CloseHandle(job)       # kills the process and anything it started
            job = None
            process.communicate()
            raise
        return process.returncode, error
    finally:
        if job:
            kernel32.CloseHandle(job)
