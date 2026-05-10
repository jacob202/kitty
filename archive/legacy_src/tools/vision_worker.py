import sys
import tempfile

import cv2
import easyocr


class Florence2Worker:
    def __init__(self):
        print("   Loading EasyOCR reader...")
        sys.stdout.flush()
        self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        print("   EasyOCR ready.")
        sys.stdout.flush()

    def run_task(self, image_path, task_prompt=None):
        print(f"   Reading image: {image_path}")
        sys.stdout.flush()
        img = cv2.imread(image_path)
        h, w = img.shape[:2]
        max_dim = 2000
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            img = cv2.resize(img, (new_w, new_h))
            print(f"   Resized from {w}x{h} to {new_w}x{new_h}")
            sys.stdout.flush()
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                resized_path = tmp.name
                cv2.imwrite(resized_path, img)
            image_path = resized_path
        print("   Running OCR...")
        sys.stdout.flush()
        results = self.reader.readtext(image_path)
        bboxes = []
        labels = []
        for (bbox, text, conf) in results:
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            bboxes.append([min(xs), min(ys), max(xs), max(ys)])
            labels.append(text)
        print(f"   OCR complete. Found {len(labels)} text regions.")
        sys.stdout.flush()
        return {"bboxes": bboxes, "labels": labels}
