# Screenshots of the live site

Captured from https://d157m2vmtz6y3j.cloudfront.net on 2026-09-27 at 1280x1000 (the `mobile-` captures at 390x844, device scale 2, after the 390px accessibility pass; `about` recaptured after the authorship paragraph was aligned with the README) and served from the site bucket (the PNGs are not kept in git because the forge's chunked review cannot inspect binary patches). Each URL, size and SHA-256 below is the file as uploaded.

| page | URL | bytes | sha256 |
|---|---|---|---|
| about | https://d157m2vmtz6y3j.cloudfront.net/screenshots/about.png | 145317 | d60997319ba538ef0f8028e76d65f3afb05fe050660413f2b4619c471d73bcb0 |
| ask | https://d157m2vmtz6y3j.cloudfront.net/screenshots/ask.png | 62830 | bf9086f74113974e79ab7be246dcd8570aef8688ae46bea89c1b139448d03b6f |
| dashboard | https://d157m2vmtz6y3j.cloudfront.net/screenshots/dashboard.png | 104740 | ae6428334e833402bd1fb5eca1eae10f59b30c930d51ee0f0e10c6a89190e2e6 |
| deep-link-licences-cenovus | https://d157m2vmtz6y3j.cloudfront.net/screenshots/deep-link-licences-cenovus.png | 227601 | 472ced8380b4f359ec79f390d37d5631a2e5510a7005daca2e924dd5a5c9db20 |
| licences | https://d157m2vmtz6y3j.cloudfront.net/screenshots/licences.png | 220456 | deb7da6a9f1d81b92582570f12cecae487be73ae27a8021818681257eb49472f |
| map-filtered-cenovus | https://d157m2vmtz6y3j.cloudfront.net/screenshots/map-filtered-cenovus.png | 710870 | a9feb8eefa10887814500ca7a855a05a52a46064c0148c0ab389ff96ec7c30ff |
| map | https://d157m2vmtz6y3j.cloudfront.net/screenshots/map.png | 868894 | 562d96fbf61122a64174ba0f8c3ec7a489a9f1114ad86bf60679cb8fabe298ae |
| mobile-about | https://d157m2vmtz6y3j.cloudfront.net/screenshots/mobile-about.png | 251784 | e787e77c77a89eed00e758707e7a631a656f8f578ab5f71a1d6d25a3e53c8b15 |
| mobile-ask | https://d157m2vmtz6y3j.cloudfront.net/screenshots/mobile-ask.png | 168588 | 0e82f1ef9018732e1758fd68d8edd74038c4962168fbecbd40ccdc57a447e58a |
| mobile-dashboard | https://d157m2vmtz6y3j.cloudfront.net/screenshots/mobile-dashboard.png | 118556 | 15b1efb17230e05be5c2a4a16ea737e55b0456800daa609d54372d4e60e4d282 |
| mobile-licences | https://d157m2vmtz6y3j.cloudfront.net/screenshots/mobile-licences.png | 162675 | 0d3d98a876cc42df66340708a6ac7e62f57c2ec4492c882f7aa75139b34da6bc |
| mobile-map | https://d157m2vmtz6y3j.cloudfront.net/screenshots/mobile-map.png | 625246 | 4ae4aada6d9dcf778d99ba1489bc3e154e68a0b056bef9062b7a7c6a2f55da66 |

Recapture (from the repository root):

    npx playwright@latest screenshot --browser chromium --viewport-size=1280,1000 --wait-for-timeout=20000 https://d157m2vmtz6y3j.cloudfront.net/map docs/screenshots/map.png
    python3 scripts/aws_task.py s3 sync docs/screenshots s3://wellspring-demo-sitebucket-qepuhrtijij0/screenshots --exclude "*" --include "*.png" --content-type image/png --cache-control no-cache --only-show-errors
    python3 scripts/aws_task.py cloudfront create-invalidation --distribution-id E2OWOTRIGM4VB1 --paths "/screenshots/*"

docs/screenshots/*.png is git-ignored so a recapture never lands in a diff.
