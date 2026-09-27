# Screenshots of the live site

Captured from https://d157m2vmtz6y3j.cloudfront.net on 2026-09-27 at 1280x1000 and served from the site bucket (the PNGs are not kept in git because the forge's chunked review cannot inspect binary patches). Each URL, size and SHA-256 below is the file as uploaded.

| page | URL | bytes | sha256 |
|---|---|---|---|
| about | https://d157m2vmtz6y3j.cloudfront.net/screenshots/about.png | 148907 | 0824472e2b9159b4183748242b4aa14359fb286b71b7b320f23525c1b5c0c40d |
| ask | https://d157m2vmtz6y3j.cloudfront.net/screenshots/ask.png | 62830 | bf9086f74113974e79ab7be246dcd8570aef8688ae46bea89c1b139448d03b6f |
| dashboard | https://d157m2vmtz6y3j.cloudfront.net/screenshots/dashboard.png | 104740 | ae6428334e833402bd1fb5eca1eae10f59b30c930d51ee0f0e10c6a89190e2e6 |
| deep-link-licences-cenovus | https://d157m2vmtz6y3j.cloudfront.net/screenshots/deep-link-licences-cenovus.png | 227601 | 472ced8380b4f359ec79f390d37d5631a2e5510a7005daca2e924dd5a5c9db20 |
| licences | https://d157m2vmtz6y3j.cloudfront.net/screenshots/licences.png | 220456 | deb7da6a9f1d81b92582570f12cecae487be73ae27a8021818681257eb49472f |
| map-filtered-cenovus | https://d157m2vmtz6y3j.cloudfront.net/screenshots/map-filtered-cenovus.png | 710870 | a9feb8eefa10887814500ca7a855a05a52a46064c0148c0ab389ff96ec7c30ff |
| map | https://d157m2vmtz6y3j.cloudfront.net/screenshots/map.png | 868894 | 562d96fbf61122a64174ba0f8c3ec7a489a9f1114ad86bf60679cb8fabe298ae |

Recapture (from the repository root):

    npx playwright@latest screenshot --browser chromium --viewport-size=1280,1000 --wait-for-timeout=20000 https://d157m2vmtz6y3j.cloudfront.net/map docs/screenshots/map.png
    python3 scripts/aws_task.py s3 sync docs/screenshots s3://wellspring-demo-sitebucket-qepuhrtijij0/screenshots --exclude "*" --include "*.png" --content-type image/png --cache-control no-cache --only-show-errors
    python3 scripts/aws_task.py cloudfront create-invalidation --distribution-id E2OWOTRIGM4VB1 --paths "/screenshots/*"

docs/screenshots/*.png is git-ignored so a recapture never lands in a diff.
