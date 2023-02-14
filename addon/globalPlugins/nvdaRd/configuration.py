from utils.displayString import DisplayStringIntFlag
from enum import unique
from addonHandler import getCodeAddon
import config
from typing import Any, Dict

_cachedConfig: Dict[str, Any] = {}


@unique
class OperatingMode(DisplayStringIntFlag):
	SERVER = 0x1
	CLIENT = 0x2
	SERVER_AND_CLIENT = 0x3

	@property
	def _displayStringLabels(self):
		return {
			OperatingMode.SERVER: _("Incoming connections (Remote Desktop Server)"),
			OperatingMode.CLIENT: _("Outgoing connections (Remote Desktop Client)"),
			OperatingMode.SERVER_AND_CLIENT: _("Bidirectional connections (Remote Desktop Server and Client)"),
		}


CONFIG_SECTION_NAME = getCodeAddon().name
OPERATING_MODE_SETTING_NAME = "operatingMode"
PERSISTENT_REGISTRATION_SETTING_NAME = "persistentRegistration"
RECOVER_REMOTE_SPEECH_SETTING_NAME = "recoverRemoteSpeech"
CONFIG_SPEC = {
	OPERATING_MODE_SETTING_NAME: 'integer(default=3, min=1, max=3)',
	PERSISTENT_REGISTRATION_SETTING_NAME: "boolean(default=false)",
	RECOVER_REMOTE_SPEECH_SETTING_NAME: "boolean(default=true)",
}


def getOperatingMode(fromCache: bool = False) -> OperatingMode:
	section = _cachedConfig if fromCache else config.conf[CONFIG_SECTION_NAME]
	return OperatingMode(section[OPERATING_MODE_SETTING_NAME])


def getPersistentRegistration(fromCache: bool = False) -> bool:
	section = _cachedConfig if fromCache else config.conf[CONFIG_SECTION_NAME]
	return section[PERSISTENT_REGISTRATION_SETTING_NAME]


def getRecoverRemoteSpeech(fromCache: bool = False) -> bool:
	section = _cachedConfig if fromCache else config.conf[CONFIG_SECTION_NAME]
	return section[RECOVER_REMOTE_SPEECH_SETTING_NAME]


def initializeConfig():
	if CONFIG_SECTION_NAME not in config.conf:
		config.conf[CONFIG_SECTION_NAME] = {}
	config.conf[CONFIG_SECTION_NAME].spec.update(CONFIG_SPEC)
	updateConfigCache()


def updateConfigCache():
	global _cachedConfig
	_cachedConfig = config.conf[CONFIG_SECTION_NAME].copy()