"""Optional pretrained image classification with explicit demo fallback."""

from __future__ import annotations

import hashlib
import io

from PIL import Image


def classify_image(image_bytes: bytes, use_pretrained: bool = True) -> dict:
    """Run ResNet-18 if its optional packages/weights are available.

    The fallback is labelled demo mode and deliberately returns no confidence.
    """
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    if use_pretrained:
        try:
            import torch
            from torchvision.models import ResNet18_Weights, resnet18
            weights = ResNet18_Weights.DEFAULT
            model = resnet18(weights=weights)
            model.eval()
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            tensor = weights.transforms()(image).unsqueeze(0)
            with torch.inference_mode():
                probabilities = model(tensor).softmax(dim=1)[0]
            confidence, index = probabilities.max(dim=0)
            return {"prediction": weights.meta["categories"][int(index)],
                    "confidence": float(confidence), "mode": "pretrained_resnet18",
                    "model_sha256": hashlib.sha256(b"torchvision:ResNet18_Weights.DEFAULT").hexdigest(),
                    "note": "Model identity hash is a stable identifier for the named weights, not a hash of cached weight bytes."}
        except Exception as exc:
            return {"error": f"Pretrained inference unavailable: {type(exc).__name__}: {exc}", "image_sha256": image_hash}
    return {"prediction": "Demo result — no model prediction", "confidence": None,
            "mode": "demo", "model_sha256": hashlib.sha256(b"trustcv-demo-mode-v1").hexdigest(),
            "note": "Demo mode does not perform image classification."}
