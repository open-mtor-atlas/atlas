Subject: GitHub Pages deployment stuck in "deployment_queued" / "deployment_in_progress" for public repo open-mtor-atlas/atlas

Repository: https://github.com/open-mtor-atlas/atlas
Custom domain: https://mtor-atlas.org/
Pages source: Deploy from a branch (main), auto-managed "pages build and deployment" workflow

Summary:
GitHub Pages deployments for this repository have been unable to complete since approximately 2026-08-06 13:56 UTC. The site is still serving a build with Last-Modified: Thu, 06 Aug 2026 08:16:20 GMT, confirmed via a cache-busting fetch (cache: no-store) as of 2026-08-06 15:18 UTC — over an hour after the affected commit was pushed.

Timeline:
1. Commit bc34d81 pushed to main around 2026-08-06 ~13:56 UTC.
2. Run #164 (https://github.com/open-mtor-atlas/atlas/actions/runs/31099277534), first attempt: the `deploy` job polled "Getting Pages deployment status... Current status: deployment_queued" roughly 250 times over ~10 minutes, then the actions/deploy-pages@v5 action's own timeout fired ("Error: Timeout reached, aborting!") and it canceled the deployment itself (deployment ID bc34d81eacd67a7f3c3370f5a5e67ff2d410a535).
3. A re-run of the same run (#164, "Latest #2") was triggered ~2 hours later via the Actions UI. That re-run sat in Status: Queued with Total duration "–" for 2+ hours — none of the three jobs (build / report-build-status / deploy) ever started, not even the initial `build` job on a hosted runner.
4. Ruled out as causes: GitHub Status (githubstatus.com) showed Actions and Pages both "Normal" throughout. The `github-pages` deployment environment has no required reviewers, no wait timer, and its only branch restriction (main) is satisfied. Billing/quota is not a factor (public repo — Actions minutes usage shows 0 min consumed, $0 billable, no spending limit configured).
5. To rule out a stale deployment context tied to run #164, we pushed a brand-new empty commit (cb250af) to main to force a fresh deployment. This produced a new run, #168 (https://github.com/open-mtor-atlas/atlas/actions/runs/31114366397). This time `build` (20s) and `report-build-status` (4s) completed normally — unlike #164, the run was picked up immediately. However, the `deploy` job has now been stuck at "Current status: deployment_in_progress" (polling, not advancing) for 10+ minutes without completing or timing out.
6. Confirmed via direct no-cache fetch of https://mtor-atlas.org/ that the live site's Last-Modified header is unchanged (Thu, 06 Aug 2026 08:16:20 GMT) throughout all of the above — no deployment from either run has actually gone live.

Request:
Please investigate why Pages deployments for this repository are unable to progress past the GitHub-side deployment queue (both "deployment_queued" that times out, and now "deployment_in_progress" that doesn't complete), despite Actions/Pages showing normal status platform-wide. We'd appreciate confirmation of whether this is an account-level, repository-level, or Pages-backend-level issue, and any action needed on our side to unblock it.

Affected run URLs for reference:
- https://github.com/open-mtor-atlas/atlas/actions/runs/31099277534 (run #164, both attempts)
- https://github.com/open-mtor-atlas/atlas/actions/runs/31114366397 (run #168, currently stuck)
