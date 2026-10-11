import numpy as np

from app.camera.capture import mirror, to_rgb


def test_to_rgb_swaps_channel_order():
    bgr = np.zeros((2, 2, 3), dtype=np.uint8)
    bgr[0, 0] = [10, 20, 30]  # B, G, R
    rgb = to_rgb(bgr)
    assert list(rgb[0, 0]) == [30, 20, 10]


def test_mirror_flips_horizontally():
    frame = np.zeros((1, 3, 3), dtype=np.uint8)  # 1x3 BGR image
    frame[0, 0] = [1, 1, 1]
    frame[0, 1] = [2, 2, 2]
    frame[0, 2] = [3, 3, 3]
    flipped = mirror(frame)
    assert list(flipped[0, :, 0]) == [3, 2, 1]
