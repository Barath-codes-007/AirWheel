# Hand landmark model

`hand_landmarker.task` is not committed to the repo (it's a binary model
file, tens of MB). Run:

```bat
python scripts\download_model.py
```

This downloads the official float16 Hand Landmarker model from Google's
MediaPipe model store. If the script's URL ever 404s (Google occasionally
moves model paths), get the current link from the official docs:
https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker
(Models section) and save it as `models/hand_landmarker.task`.
