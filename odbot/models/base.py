

class BaseModel:

	CLASS_MAP = {}

	def __init__(self, model, names:dict) -> None:
		self.model = model
		self.names = names

	def get_predictions(self, img):
		raise NotImplementedError("Please subclass this method")

	