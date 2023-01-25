import braille
import typing
import addonHandler
from typing import List
import inputCore

if typing.TYPE_CHECKING:
	from ..lib import driver
	from ..lib import protocol
else:
	addon: addonHandler.Addon = addonHandler.getCodeAddon()
	driver = addon.loadModule("lib.driver")
	protocol = addon.loadModule("lib.protocol")


class RemoteBrailleDisplayDriver(driver.RemoteDriver, braille.BrailleDisplayDriver):
	# Translators: Name for a remote braille display.
	description = _("Remote Braille")
	isThreadSafe = True
	driverType = protocol.DriverType.BRAILLE

	def _handleRemoteDisconnect(self):
		# Raise an exception because handleDisplayUnavailable expects one
		try:
			raise RuntimeError("XOFF received, remote client disconnected")
		except RuntimeError:
			braille.handler.handleDisplayUnavailable()

	def __init__(self, port="auto"):
		super().__init__()

	@protocol.attributeReceiver(protocol.BrailleAttribute.NUM_CELLS, defaultValue=0)
	def _handleNumCellsUpdate(self, payload: bytes) -> int:
		assert len(payload) == 1
		return ord(payload)

	def _get_numCells(self) -> int:
		return self._attributeValueProcessor[protocol.BrailleAttribute.NUM_CELLS].value

	@protocol.attributeReceiver(protocol.BrailleAttribute.GESTURE_MAP, defaultValue=inputCore.GlobalGestureMap())
	def _handleGestureMapUpdate(self, payload: bytes) -> inputCore.GlobalGestureMap:
		assert len(payload) > 0
		return self._unpickle(payload)

	def _get_gestureMap(self) -> inputCore.GlobalGestureMap:
		return self._attributeValueProcessor[protocol.BrailleAttribute.GESTURE_MAP].value

	@protocol.commandHandler(protocol.BrailleCommand.EXECUTE_GESTURE)
	def _handleExecuteGesture(self, payload: bytes):
		assert len(payload) > 0
		gesture = self._unpickle(payload)
		inputCore.manager.executeGesture(gesture)

	def display(self, cells: List[int]):
		# cells will already be padded up to numCells.
		arg = bytes(cells)
		self.writeMessage(protocol.BrailleCommand.DISPLAY, arg)


BrailleDisplayDriver = RemoteBrailleDisplayDriver