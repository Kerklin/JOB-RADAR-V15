# Job Radar V15: audit, setup and validation

## Two repository files
radar.py at root; .github/workflows/publish.yml.
Use the ZIP filenames as supplied. No renaming required.

## Browser-only setup
1. Create NEW public repository job-radar-v15, default branch main.
2. Upload radar.py and commit.
3. Add file > Create new file. Name .github/workflows/publish.yml.
4. Paste full contents of supplied publish.yml; commit.
5. Settings > Pages > Source: GitHub Actions.
6. Actions > Job Radar V15 > Run workflow. Wait for build AND deploy.
7. Settings > Pages > Visit site. Bookmark that page.
No user secrets, AI tokens, email passwords or repository-write permission.
Do NOT keep previous workflows active alongside this one.

## V12 audit
- UNDP adapter read static HTML only, so JavaScript-rendered listings were missed.
- UNICEF response cap was 3 MB, an application-imposed limit, not a site failure.
- Exact phrase scoring missed broader titles. Zero matches did not establish no relevant jobs.
- No rejected-title examples were shown, making false negatives hard to diagnose.
- UNjobs robots exclusion is a permission boundary, not a parsing defect to bypass.
- UNJobsFeed HTML did not match the assumed job-link pattern; no validated replacement
  adapter was available. It is now explicitly manual-only, not advertised as repaired.
- Individual V12 downloads had suffixes requiring renaming; ZIP names were correct.

## V15 changes
- UNDP and NEW IOM source render public pages using Playwright/Chromium. Bounded
  Show More/scroll attempts; not exhaustive pagination. No guessed Oracle APIs.
- Workflow installs pinned playwright 1.64.1 and matching Chromium automatically.
  This is a NEW free dependency. V15 is not standard-library-only.
- UNICEF maximum response raised from 3 MB to 32 MB, still bounded for safety.
- Broader construction/field-engineer/WASH titles; procurement requires works context.
- Source health shows up to ten rejected titles for scoring diagnosis.
- UNjobs and UNJobsFeed retained as manual links, not automatic integrations.
- Impactpool, UNOPS and UN Careers remain automatic adapters.
- Prior results retained at most seven days when previous published data is reachable.
- No JOBS.md. Dashboard generated with embedded data; jobs.json is only for recovery.

## Test and run results
Final regression suite: 36 methods passed twice, 0.094 and 0.166 seconds.
Workflow YAML parsed; generated dashboard JavaScript passed node --check.
Live collector was executed: 0/6 sources responding, all HTTP 403 in this environment.
Playwright package exists locally, but matching Chromium binary is absent. Therefore
Oracle browser execution and live GitHub deployment are NOT verified here.
The workflow installs Chromium on GitHub, as documented by Playwright.
No claim that all unavailable sources are repaired or production-verified.

## Important limitations
No access-control/CAPTCHA/robots bypass. A source can remain unavailable.
Rendering public pages costs more runner time than RSS; six-hour schedule is best-effort.
Use public repository and standard hosted runners for the intended free setup.
Scores are discovery priorities, not eligibility decisions. Broad construction/WASH
terms can produce false positives; review requirements, nationality and deadline.
Unknown deadlines remain unknown. Cross-site duplicate jobs may remain.
Browser adapter reads titles/links only; not full descriptions or structured dates.
The first GitHub run is the live acceptance test. Read source health, not just green status.

## Expected first-run checks
- Install browser dependency step succeeds.
- Regression tests pass.
- Build dashboard reports records, matches, rejected examples or precise errors.
- Deploy succeeds and Visit site opens the page.
- UNDP/IOM may still fail if blocked or their rendered DOM differs; inspect actual log.
