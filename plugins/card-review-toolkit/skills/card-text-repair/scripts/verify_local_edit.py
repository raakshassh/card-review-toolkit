"""Verify that a raster edit changes only the allowed mask pixels."""
import argparse
import json
import sys
from PIL import Image
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before')
    parser.add_argument('after')
    parser.add_argument('--mask', required=True)
    args = parser.parse_args()
    with Image.open(args.before) as image:
        before = np.array(image.convert('RGBA'))
    with Image.open(args.after) as image:
        after = np.array(image.convert('RGBA'))
    with Image.open(args.mask) as image:
        allowed = np.array(image.convert('L')) > 0
    if before.shape != after.shape or allowed.shape != before.shape[:2]:
        print(json.dumps({'ok': False, 'error': 'Image or mask dimensions differ'}))
        return 1
    changed = np.any(before != after, axis=2)
    y, x = np.where(changed)
    outside = int(np.count_nonzero(changed & ~allowed))
    report = {
        'ok': outside == 0,
        'changed_pixels': int(changed.sum()),
        'outside_mask_pixels': outside,
        'change_bounds_xyxy_exclusive':
            [int(x.min()), int(y.min()), int(x.max()) + 1, int(y.max()) + 1]
            if x.size else None,
    }
    print(json.dumps(report, indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
