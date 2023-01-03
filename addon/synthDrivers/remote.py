import typing
import addonHandler
import synthDriverHandler
import queueHandler
from hwIo import boolToByte
import sys

if typing.TYPE_CHECKING:
	from ..lib import driver
	from ..lib import protocol
else:
	addon: addonHandler.Addon = addonHandler.getCodeAddon()
	driver = addon.loadModule("lib.driver")
	protocol = addon.loadModule("lib.protocol")


class remoteSynthDriver(driver.WTSRemoteDriver, synthDriverHandler.SynthDriver):
	name = "remote"
	# Translators: Name for a remote braille display.
	description = _("Remote speech")
	supportedNotifications = {synthDriverHandler.synthIndexReached, synthDriverHandler.synthDoneSpeaking}
	supportedSettings = ()

	def _handleRemoteDisconnect(self):
		queueHandler.queueFunction(queueHandler.eventQueue, synthDriverHandler.findAndSetNextSynth, self.name)

	def __init__(self):
		synthDriverHandler.SynthDriver.__init__(self)
		driver.WTSRemoteDriver.__init__(self, protocol.DriverType.SPEECH)

	def speak(self, speechSequence):
		self.writeMessage(protocol.SpeechCommand.SPEAK, self.pickle(speechSequence))

	def cancel(self):
		self.writeMessage(protocol.SpeechCommand.CANCEL)

	def pause(self, switch):
		self.writeMessage(protocol.SpeechCommand.PAUSE, boolToByte(switch))

	@protocol.attributeHandler(protocol.SpeechAttribute.SUPPORTED_COMMANDS, defaultValue=frozenset())
	def _handleSupportedCommandsUpdate(self, payLoad: bytes):
		if len(payLoad) == 0:
			return frozenset()
		return self.unpickle(payLoad)

	def _get_supportedCommands(self):
		return self._attributeHandlers[protocol.SpeechAttribute.SUPPORTED_COMMANDS].value

	@protocol.commandHandler(protocol.SpeechCommand.INDEX_REACHED)
	def _handleIndexReached(self, incomingPayload: bytes):
		assert len(incomingPayload) == 2
		index = int.from_bytes(incomingPayload, sys.byteorder)
		synthDriverHandler.synthIndexReached.notify(synth=self, index=index)


SynthDriver = remoteSynthDriver
