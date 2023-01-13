from odbot.models.base import BaseModel
import torch

from odbot.utils import resource_path


class YoloV5Model(BaseModel):
	def __init__(self, version='yolov5s') -> None:
		model = torch.hub.load(
			'ultralytics/yolov5',
			'custom',
			path=resource_path(f"weights/{version}.pt"),
			trust_repo=True,
			force_reload=True
		)
		super().__init__(model, model.names)

	def get_predictions(self, img):
		preds = self.model(img)
		return preds.xyxy[0]
