"""
Face swap tool using InsightFace.
Requires: pip install insightface opencv-python
Also requires the inswapper_128.onnx model in ./data/models/
Download: https://github.com/deepinsight/insightface/releases
"""
from pathlib import Path


class FaceSwapper:
    def __init__(self, model_path="./data/models/inswapper_128.onnx"):
        self.model_path = Path(model_path)
        self._swapper = None
        self._app = None
        self._try_init()

    def _try_init(self):
        if not self.model_path.exists():
            print(
                f"[FaceSwapper] Model not found at {self.model_path}. "
                "Download inswapper_128.onnx and place it in ./data/models/"
            )
            return
        try:
            import insightface
            self._app = insightface.app.FaceAnalysis(name="buffalo_l")
            self._app.prepare(ctx_id=0, det_size=(640, 640))
            self._swapper = insightface.model_zoo.get_model(str(self.model_path), download=False)
            print("[FaceSwapper] InsightFace initialized.")
        except Exception as e:
            print(f"[FaceSwapper] InsightFace not available: {e}")

    def swap(self, source_face_path, target_img_path):
        if not self._swapper or not self._app:
            return "FaceSwapper not initialized. See ./data/models/ setup instructions."
        import cv2
        source_img = cv2.imread(source_face_path)
        target_img = cv2.imread(target_img_path)
        source_faces = self._app.get(source_img)
        target_faces = self._app.get(target_img)
        if not source_faces:
            return "No face detected in source image."
        if not target_faces:
            return "No face detected in target image."
        result = target_img.copy()
        for face in target_faces:
            result = self._swapper.get(result, face, source_faces[0], paste_back=True)
        out_path = Path("./data/outputs/swapped.png")
        cv2.imwrite(str(out_path), result)
        return str(out_path)
