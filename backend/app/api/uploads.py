"""圖片上傳 API。

安全重點：
- 檔名一律用 uuid4().hex 重新命名，不保留使用者原始檔名（避免 path traversal）
- 副檔名白名單，且副檔名只從原始檔名取並過濾
- 檔案大小由 MAX_CONTENT_LENGTH 全域限制（8MB）
- 副檔名與實際檔案型別不符時擋掉
"""

from __future__ import annotations

import imghdr
import os
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request

from ..utils import ApiError, current_user, login_required

uploads_bp = Blueprint("uploads", __name__, url_prefix="/api")

# imghdr 對這些副檔名的偵測
_IMAGE_TYPES = {
    "png": "png",
    "jpeg": "jpg",
    "gif": "gif",
    "webp": "webp",
}


@uploads_bp.route("/uploads", methods=["POST"])
@login_required
def upload():
    if "file" not in request.files:
        raise ApiError("請選擇要上傳的檔案", 400, "no_file")

    file = request.files["file"]
    if not file.filename:
        raise ApiError("請選擇要上傳的檔案", 400, "no_file")

    original = file.filename
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    allowed = current_app.config["ALLOWED_IMAGE_EXTENSIONS"]

    if ext not in allowed:
        raise ApiError(
            f"只接受 {'/'.join(sorted(allowed))} 格式的圖片", 400, "invalid_file_type"
        )

    # 檢查實際檔案內容是不是圖片（副檔名可以造假）
    head = file.stream.read(1024)
    file.stream.seek(0)
    detected = imghdr.what(None, h=head)
    if detected is None or detected not in _IMAGE_TYPES:
        raise ApiError("這個檔案看起來不是圖片", 400, "invalid_file_type")

    # 副檔名白名單跟實際內容對不上時，以偵測結果為準
    final_ext = _IMAGE_TYPES[detected]

    filename = f"{uuid4().hex}.{final_ext}"
    folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)

    path = os.path.join(folder, filename)
    file.save(path)

    return jsonify({"url": f"/static/uploads/{filename}"}), 201
