import braille
import brailleInput
from enum import IntEnum, Enum
from typing import Optional


class BrailleCommand(IntEnum):
	DISPLAY = ord(b'D')
	EXECUTE_GESTURE = ord(b'G')


class BrailleAttribute(bytes, Enum):
	NUM_CELLS = b"numCells"
	GESTURE_MAP = b"gestureMap"
	OBJECT_GESTURE_MAP = b"_gestureMap"


class BrailleInputGesture(braille.BrailleDisplayGesture, brailleInput.BrailleInputGesture):

	def __init__(
			self,
			source: str,
			id: str,
			routingIndex: Optional[int] = None,
			model: Optional[str] = None,
			dots: int = 0,
			space: bool = False,
			**kwargs
	):
		super().__init__()
		self.source = source
		self.id = id
		self.routingIndex = routingIndex
		self.model = model
		self.dots = dots
		self.space = space
		for attr, val in kwargs.items():
			setattr(self, attr, val)
