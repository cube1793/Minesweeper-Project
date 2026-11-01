"""Windows containment for the venv redirector AND actual Python worker.

Create the launcher suspended, assign it to a private kill-on-close Job Object,
then resume its single initial thread. Descendants inherit membership before
any Python code runs. No taskkill/name matching or unrelated process ownership.
Win32 contracts: https://learn.microsoft.com/windows/win32/procthread/job-objects
"""

import ctypes as C
from ctypes import wintypes as W
import os
from uuid import uuid4


CREATE_SUSPENDED = 0x4


class _Limits(C.Structure):
    _fields_ = [("process_time", C.c_longlong), ("job_time", C.c_longlong), ("flags", W.DWORD),
                ("min_working", C.c_size_t), ("max_working", C.c_size_t), ("active_limit", W.DWORD),
                ("affinity", C.c_size_t), ("priority", W.DWORD), ("scheduling", W.DWORD)]


class _IO(C.Structure):
    _fields_ = [(name, C.c_ulonglong) for name in ("read_ops", "write_ops", "other_ops", "read", "write", "other")]


class _Extended(C.Structure):
    _fields_ = [("basic", _Limits), ("io", _IO), ("process_memory", C.c_size_t), ("job_memory", C.c_size_t),
                ("peak_process", C.c_size_t), ("peak_job", C.c_size_t)]


class _Accounting(C.Structure):
    _fields_ = [(name, C.c_longlong) for name in ("user", "kernel", "period_user", "period_kernel")] + [
        (name, W.DWORD) for name in ("faults", "total", "active", "terminated")]


class _ThreadEntry(C.Structure):
    _fields_ = [("size", W.DWORD), ("usage", W.DWORD), ("id", W.DWORD), ("pid", W.DWORD),
                ("base_priority", W.LONG), ("delta_priority", W.LONG), ("flags", W.DWORD)]


def _api():
    kernel = C.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
        "OpenJobObjectW": ([W.DWORD, W.BOOL, W.LPCWSTR], W.HANDLE),
        "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
        "QueryInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
        "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
        "IsProcessInJob": ([W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)], W.BOOL),
        "GetCurrentProcess": ([], W.HANDLE),
        "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
        "CloseHandle": ([W.HANDLE], W.BOOL),
        "CreateToolhelp32Snapshot": ([W.DWORD, W.DWORD], W.HANDLE),
        "Thread32First": ([W.HANDLE, C.POINTER(_ThreadEntry)], W.BOOL),
        "Thread32Next": ([W.HANDLE, C.POINTER(_ThreadEntry)], W.BOOL),
        "OpenThread": ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
        "ResumeThread": ([W.HANDLE], W.DWORD),
    }
    for name, (args, result) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = args, result
    return kernel


def _check(value):
    if not value:
        raise C.WinError(C.get_last_error())
    return value


class WindowsWorkerScope:
    def __init__(self):
        self.api = _api()
        self.name = "Local\\MinesweeperExhibition_" + uuid4().hex
        self.handle = _check(self.api.CreateJobObjectW(None, self.name))
        try:
            limits = _Extended()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway
            _check(self.api.SetInformationJobObject(self.handle, 9, C.byref(limits), C.sizeof(limits)))
        except Exception:
            self.close()
            raise

    def assign_and_resume(self, process):
        _check(self.api.AssignProcessToJobObject(self.handle, int(process._handle)))
        snapshot = self.api.CreateToolhelp32Snapshot(0x4, 0)  # TH32CS_SNAPTHREAD
        if snapshot == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        try:
            entry = _ThreadEntry()
            entry.size = C.sizeof(entry)
            present, ids = self.api.Thread32First(snapshot, C.byref(entry)), []
            while present:
                if entry.pid == process.pid:
                    ids.append(entry.id)
                present = self.api.Thread32Next(snapshot, C.byref(entry))
            if len(ids) != 1:
                raise RuntimeError("Suspended exhibition launcher must have one initial thread.")
            thread = _check(self.api.OpenThread(0x2, False, ids[0]))  # THREAD_SUSPEND_RESUME
            try:
                if self.api.ResumeThread(thread) != 1:
                    raise RuntimeError("Could not resume the contained launcher exactly once.")
            finally:
                self.api.CloseHandle(thread)
        finally:
            self.api.CloseHandle(snapshot)

    @property
    def active_count(self):
        info = _Accounting()
        _check(self.api.QueryInformationJobObject(self.handle, 1, C.byref(info), C.sizeof(info), None))
        return info.active

    def terminate(self):
        _check(self.api.TerminateJobObject(self.handle, 1))

    def close(self):
        if self.handle is not None:
            _check(self.api.CloseHandle(self.handle))
            self.handle = None


def create_scope():
    return WindowsWorkerScope() if os.name == "nt" else None


def verify_worker_scope(name):
    """Fail closed before execution if a Windows worker escaped containment."""
    if os.name != "nt":
        return
    if not name:
        raise RuntimeError("A parent-owned Windows Job Object is required.")
    api = _api()
    handle = _check(api.OpenJobObjectW(0x4, False, name))  # JOB_OBJECT_QUERY
    try:
        member = W.BOOL()
        _check(api.IsProcessInJob(api.GetCurrentProcess(), handle, C.byref(member)))
        if not member.value:
            raise RuntimeError("Actual Python worker is outside its parent-owned Job Object.")
    finally:
        api.CloseHandle(handle)  # parent alone owns lifetime/kill-on-close
