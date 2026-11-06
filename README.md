# V15 repaired: installation and limitations

Replace radar.py in the existing repository. Keep the filename exactly radar.py.
Replace .github/workflows/publish.yml with the supplied workflow. No new secrets.
Settings > Pages > Source: GitHub Actions. Actions > Job Radar V15 > Run workflow.
Wait for build and deploy. Settings > Pages > Visit site.

## Oracle repair
Old code assumed a fixed site ID, main-frame links and a specific anchor path.
New code reads all frames and JSON requisition responses produced by the public
page itself. No direct calls to guessed/private endpoints. Standard browser UA.
It does not bypass robots, login or CAPTCHA. Public listing diagnostics are
published under diagnostics/UNDP.json, diagnostics/UNDP.png and IOM equivalents.
These include public links, counts and a screenshot, not tokens or cookies.
If a source still fails, inspect these diagnostics. The repair is not live-verified.

## Eligibility evidence ranking
Six checks: deadline 20, external access 20, education 20, experience 20,
work rights 15, language 5. Only supported checks earn points; UNKNOWN earns zero.
Any failed check yields INELIGIBLE; any unknown yields NEEDS VERIFICATION.
The score is evidence coverage, NOT a legal decision, probability or full ATS fit.
Full requirements may be missing from feeds. Education/experience checks are narrow
pattern matches and require human confirmation of equivalence and relevance.
Confirmed baseline: architecture degrees, 2-year construction assignment, native
Bosnian/Croatian/Serbian. No citizenship, work permits or English CEFR level inferred.
Work rights remain UNKNOWN until documented evidence and vacancy rules are supplied.
Higher experience requirements remain UNKNOWN, not automatically failed.
Ranking uses eligibility evidence first, technical keyword priority as tie-breaker.

Known expired deadlines removed. Unknown dates remain unknown. Retained jobs are
marked unverified; deadline check resets UNKNOWN. They remain at most seven days
old if previous published data is accessible. No AI, email or paid API configured.
Playwright/Chromium remain free dependencies installed by the workflow.

## Validation
43 unit/regression methods passed twice after final edits. JavaScript syntax and
workflow YAML checked. Oracle nested-JSON parsing, expiry, unknown eligibility,
external access, no inferred work rights and retained deadline reset covered.
Live run: all six sources HTTP 403 in this environment; no real browser extraction
or GitHub deployment verified. Do not interpret unit tests as proof of source repair.
Do not promise error-free operation. Source diagnostics are the next evidence needed.
