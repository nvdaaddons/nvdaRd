from hwIo.ioThread import IoThread
from typing import Callable, Iterator, List, Optional, Union
from ctypes import (
	byref,
	c_ulong,
	GetLastError,
	sizeof,
	windll,
	WinError,
)
from ctypes.wintypes import HANDLE, DWORD
from serial.win32 import (
	CreateFile,
	ERROR_IO_PENDING,
	FILE_FLAG_OVERLAPPED,
	INVALID_HANDLE_VALUE,
	OVERLAPPED,
)
import winKernel
from enum import IntFlag
import os
from glob import iglob
from appModuleHandler import processEntry32W
from hwIo.base import IoBase

ERROR_INVALID_HANDLE = 0x6
ERROR_PIPE_CONNECTED = 0x217
ERROR_PIPE_BUSY = 0xE7
PIPE_DIRECTORY = "\\\\?\\pipe\\"
RD_PIPE_GLOB_PATTERN = os.path.join(PIPE_DIRECTORY, "RdPipe_NVDA-*")
SECURE_DESKTOP_GLOB_PATTERN = os.path.join(PIPE_DIRECTORY, "NVDA_SD-*")
TH32CS_SNAPPROCESS = 0x00000002


def getParentProcessId(processId: int) -> Optional[int]:
	FSnapshotHandle = windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
	try:
		FProcessEntry32 = processEntry32W()
		FProcessEntry32.dwSize = sizeof(processEntry32W)
		ContinueLoop = windll.kernel32.Process32FirstW(FSnapshotHandle, byref(FProcessEntry32))
		while ContinueLoop:
			if FProcessEntry32.th32ProcessID == processId:
				return FProcessEntry32.th32ParentProcessID
			ContinueLoop = windll.kernel32.Process32NextW(FSnapshotHandle, byref(FProcessEntry32))
		else:
			return None
	finally:
		windll.kernel32.CloseHandle(FSnapshotHandle)


def getNamedPipes() -> Iterator[str]:
	yield from iglob(os.path.join(PIPE_DIRECTORY, "*"))


def getRdPipeNamedPipes() -> Iterator[str]:
	yield from iglob(RD_PIPE_GLOB_PATTERN)


def getSecureDesktopNamedPipes() -> Iterator[str]:
	yield from iglob(SECURE_DESKTOP_GLOB_PATTERN)


class PipeMode(IntFlag):
	READMODE_BYTE = 0x00000000
	READMODE_MESSAGE = 0x00000002
	WAIT = 0x00000000
	NOWAIT = 0x00000001


class PipeOpenMode(IntFlag):
	ACCESS_DUPLEX = 0x00000003
	ACCESS_INBOUND = 0x00000001
	ACCESS_OUTBOUND = 0x00000002
	FIRST_PIPE_INSTANCE = 0x00080000
	WRITE_THROUGH = 0x80000000
	OVERLAPPED = FILE_FLAG_OVERLAPPED
	WRITE_DAC = 0x00040000
	WRITE_OWNER = 0x00080000
	ACCESS_SYSTEM_SECURITY = 0x01000000


MAX_PIPE_MESSAGE_SIZE = 1024 * 64


class NamedPipeBase(IoBase):
	pipeProcessId: Optional[int] = None
	pipeParentProcessId: Optional[int] = None
	pipeMode: PipeMode = PipeMode.READMODE_BYTE | PipeMode.WAIT
	pipeName: str

	def __init__(
			self,
			pipeName: str,
			fileHandle: Union[HANDLE, int],
			onReceive: Callable[[bytes], None],
			onReceiveSize: int = MAX_PIPE_MESSAGE_SIZE,
			onReadError: Optional[Callable[[int], bool]] = None,
			ioThread: Optional[IoThread] = None,
			pipeMode: PipeMode = PipeMode.READMODE_BYTE,
	):
		self.pipeName = pipeName
		super().__init__(
			fileHandle,
			onReceive,
			onReceiveSize=onReceiveSize,
			onReadError=onReadError,
			ioThread=ioThread
		)

	def _get_isAlive(self) -> bool:
		return self.pipeName in getNamedPipes()


class NamedPipeServer(NamedPipeBase):
	_connected: bool = False
	_messageQueue: List[bytes]

	def __init__(
			self,
			pipeName: str,
			onReceive: Callable[[bytes], None],
			onReceiveSize: int = MAX_PIPE_MESSAGE_SIZE,
			onReadError: Optional[Callable[[int], bool]] = None,
			ioThread: Optional[IoThread] = None,
			pipeMode: PipeMode = PipeMode.READMODE_BYTE,
			pipeOpenMode: PipeOpenMode = (
				PipeOpenMode.ACCESS_DUPLEX
				| PipeOpenMode.OVERLAPPED
				| PipeOpenMode.FIRST_PIPE_INSTANCE
			),
			maxInstances: int = 1
	):
		fileHandle = windll.kernel32.CreateNamedPipeW(
			pipeName,
			pipeOpenMode,
			pipeMode,
			maxInstances,
			onReceiveSize,
			onReceiveSize,
			0,
			None
		)
		if fileHandle == INVALID_HANDLE_VALUE:
			raise WinError()
		self._messageQueue = []
		super().__init__(
			pipeName,
			fileHandle,
			onReceive,
			onReadError=onReadError,
			ioThread=ioThread,
			pipeMode=pipeMode,
		)

	def write(self, data: bytes):
		if not self._connected:
			self._messageQueue.append(data)
		else:
			return super().write(data)

	def _handleConnect(self):
		ol = OVERLAPPED()
		ol.hEvent = self._recvEvt
		connectRes = windll.kernel32.ConnectNamedPipe(self._file, byref(ol))
		error = WinError()
		if error.winerror == ERROR_PIPE_CONNECTED:
			windll.kernel32.SetEvent(self._recvEvt)
		else:
			if connectRes or error.winerror != ERROR_IO_PENDING:
				raise error
			while True:
				waitRes = winKernel.waitForSingleObjectEx(self._recvEvt, winKernel.INFINITE, True)
				if waitRes == winKernel.WAIT_OBJECT_0:
					break
				elif waitRes == winKernel.WAIT_IO_COMPLETION:
					continue
				else:
					self._ioDone(GetLastError(), 0, byref(ol))
					return
			numberOfBytes = DWORD()
			if not windll.kernel32.GetOverlappedResult(self._file, byref(ol), byref(numberOfBytes), False):
				self._ioDone(GetLastError(), 0, byref(ol))
				return
		self._connected = True
		clientProcessId = c_ulong()
		if not windll.kernel32.GetNamedPipeClientProcessId(HANDLE(self._file), byref(clientProcessId)):
			raise WinError()
		self.pipeProcessId = clientProcessId.value
		self.pipeParentProcessId = getParentProcessId(self.pipeProcessId)
		for message in self._messageQueue:
			self.write(message)
		self._messageQueue.clear()
		self._asyncRead()

	def _asyncRead(self, param: Optional[int] = None):
		if not self._connected:
			# _handleConnect will call _asyncRead when it is finished.
			self._handleConnect()
		else:
			super()._asyncRead()

	def close(self):
		super().close()
		if hasattr(self, "_file") and self._file is not INVALID_HANDLE_VALUE:
			windll.kernel32.DisconnectNamedPipe(self._file)
			winKernel.closeHandle(self._file)
			self._file = INVALID_HANDLE_VALUE


class NamedPipeClient(NamedPipeBase):

	def __init__(
			self,
			pipeName: str,
			onReceive: Callable[[bytes], None],
			onReadError: Optional[Callable[[int], bool]] = None,
			ioThread: Optional[IoThread] = None,
			pipeMode: PipeMode = PipeMode.READMODE_BYTE
	):
		fileHandle = CreateFile(
			pipeName,
			winKernel.GENERIC_READ | winKernel.GENERIC_WRITE,
			0,
			None,
			winKernel.OPEN_EXISTING,
			FILE_FLAG_OVERLAPPED,
			None
		)
		if fileHandle == INVALID_HANDLE_VALUE:
			raise WinError()
		super().__init__(
			pipeName,
			fileHandle,
			onReceive,
			onReadError=onReadError,
			ioThread=ioThread,
			pipeMode=pipeMode,
		)
		if pipeMode:
			dwPipeMode = DWORD(pipeMode)
			if not windll.kernel32.SetNamedPipeHandleState(fileHandle, byref(dwPipeMode), 0, 0):
				raise WinError()
		serverProcessId = c_ulong()
		if not windll.kernel32.GetNamedPipeServerProcessId(HANDLE(fileHandle), byref(serverProcessId)):
			raise WinError()
		self.pipeProcessId = serverProcessId.value
		self.pipeParentProcessId = getParentProcessId(self.pipeProcessId)

	def close(self):
		super().close()
		if hasattr(self, "_file") and self._file is not INVALID_HANDLE_VALUE:
			winKernel.closeHandle(self._file)
			self._file = INVALID_HANDLE_VALUE
