# UNA firmware build feasibility

This isolated branch checks whether the official, pinned UNA SDK HelloWorld LVGL example can produce a `.uapp` with an open GNU ARM compiler on a standard public GitHub Actions runner.

It is an environment experiment for possible participation in the [October 2026 UNA app competition](https://unawatch.com/blogs/news/una-apps-competition-october-2026). It is not a new app, contest submission, acceptance, award, device validation or payment. No human review is claimed.

The workflow uses a standard Ubuntu 24.04 runner, no external actions, no secrets or repository token permissions, no cache, no artifact upload and a 12-minute timeout. [GitHub documents standard hosted runners as free for public repositories](https://docs.github.com/en/billing/concepts/product-billing/github-actions). No larger runner or billing change is requested.

The official public SDK is pinned to `d71d0dc3bad7d47282fcf5a4c53a3f0f2031afb1`, LVGL to `85aa60d18b3d5e5588d7b247abf90198f07c8a63`. Dependencies keep their own licenses; this branch does not relicense or redistribute the SDK. The build only prints package size and SHA-256. A successful compile would not prove that a package loads or works on a watch.

Prepared by Codex for brodyga45. Cash prize payment to the Serbian sole proprietor's business bank, account terms and an actual original app remain unresolved; no private or banking data are present.
