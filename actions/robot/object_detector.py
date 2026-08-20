# YOLOv7-tiny/COCO on an in-memory BGR frame; shared by all robot backends.
# Interface: detect(frame) -> (class_ids, centers, areas, annotated_frame).

from pathlib import Path

import numpy as np


class YoloV7TinyDetector:
    def __init__(self, confidence=0.5, nms_threshold=0.4):
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OpenCV is required for object detection") from exc

        # Shared perception assets for all robots (actions/robot/models/);
        # the Go1 SDK keeps its own vendored copy under go1/free_dog_sdk/.
        models_dir = Path(__file__).resolve().parent / "models"
        self.cv2 = cv2
        major_version = int(cv2.__version__.split(".", 1)[0])
        if major_version >= 5:
            raise RuntimeError(
                f"OpenCV {cv2.__version__} removed Darknet model import. "
                "Install the supported build with `pip install 'opencv-python>=4.8,<4.12'`."
            )
        self.confidence = confidence
        self.nms_threshold = nms_threshold
        self.classes = (models_dir / "coco.names").read_text().splitlines()
        self.model = cv2.dnn.readNet(
            str(models_dir / "yolov7-tiny.weights"),
            str(models_dir / "yolov7-tiny.cfg"),
        )
        layer_names = self.model.getLayerNames()
        self.output_layers = [layer_names[int(i) - 1] for i in self.model.getUnconnectedOutLayers()]

    def detect(self, frame):
        # Returns (class_ids, centers, areas, annotated):
        #   centers: normalized (cx, cy) in [0, 1];  areas: box area as a fraction of the frame.
        cv2 = self.cv2
        height, width = frame.shape[:2]
        self.model.setInput(
            cv2.dnn.blobFromImage(frame, 1 / 255.0, (416, 416), swapRB=True, crop=False)
        )
        boxes, confidences, class_ids, centers, areas = [], [], [], [], []
        for output in self.model.forward(self.output_layers):
            for detection in output:
                scores = detection[5:]
                class_id = int(np.argmax(scores))
                confidence = float(scores[class_id])
                if confidence <= self.confidence:
                    continue
                center_x, center_y = int(detection[0] * width), int(detection[1] * height)
                box_width, box_height = int(detection[2] * width), int(detection[3] * height)
                boxes.append([
                    int(center_x - box_width / 2), int(center_y - box_height / 2),
                    box_width, box_height,
                ])
                confidences.append(confidence)
                class_ids.append(class_id)
                centers.append((float(detection[0]), float(detection[1])))
                areas.append(float(detection[2]) * float(detection[3]))

        indexes = cv2.dnn.NMSBoxes(boxes, confidences, self.confidence, self.nms_threshold)
        kept = {int(index) for index in np.asarray(indexes).reshape(-1)}
        annotated = frame.copy()
        kept_ids, kept_centers, kept_areas = [], [], []
        for index in sorted(kept):
            x, y, box_width, box_height = boxes[index]
            class_id = class_ids[index]
            kept_ids.append(class_id)
            kept_centers.append(centers[index])
            kept_areas.append(areas[index])
            label = f"{self.classes[class_id]} {confidences[index]:.2f}"
            cv2.rectangle(annotated, (x, y), (x + box_width, y + box_height), (60, 220, 120), 2)
            cv2.putText(annotated, label, (x, max(y - 6, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 220, 120), 1)
        return kept_ids, kept_centers, kept_areas, annotated
