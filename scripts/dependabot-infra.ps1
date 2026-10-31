#Requires -Version 7.2
<#
.SYNOPSIS
  Takes one Dependabot PR through the infra-plan gate (BI-D23, #187): checks it, pushes the
  maintainer's empty commit, approves the plan, waits for wow-review, approves and merges, and
  approves the deploy the merge starts. Run on the host, from a clone of the repo.

.DESCRIPTION
  A Dependabot-triggered run gets no Actions or Environment secrets, so a Dependabot PR that
  trips plan-infra's `detect` (it changes infra/, plan-infra.yml or deploy-infra.yml) can never
  get a green `tofu-plan` on its own. The route BI-D23 records is a maintainer's empty commit on
  the Dependabot branch, which makes the next run the maintainer's. This script is that route.

  What it checks before it pushes anything:
    - the PR is open, from Dependabot, on a branch in this repo, into main;
    - every commit on it is Dependabot's and GitHub-verified (a rerun also accepts the one
      empty commit this script pushed, on top);
    - every changed line is either a workflow `uses: owner/repo@<40-hex sha> # <tag>` pin, whose
      sha this script resolves from the upstream tag and compares, or an infra/*.tf provider
      `version = "..."` line, which it prints for you to read before you confirm.
  Anything else stops the script: such a PR is reviewed by hand.

  Every write asks first (y/N): the push, the infra-plan approval, the approve-and-merge, and
  the production approval. It is safe to rerun: each step reads the PR's current state and
  skips what is already done. wow-review is not started here; the script waits for the
  architect-review status on the new head to pass.

  Identities. The push uses this clone's git credentials, which must be -Pusher's. Approvals of
  Environment deployments use -Pusher's gh login; the PR review and merge use -Approver's, the
  other code owner, because the last pusher cannot approve (require_last_push_approval). Both
  need a `gh auth login` on this machine. Tokens are read with `gh auth token -u` and never
  printed.

.PARAMETER Pr
  The Dependabot PR number. Without it the script lists the open Dependabot PRs that trip
  `detect` and stops.

.PARAMETER CheckOnly
  Run the checks and stop; nothing is pushed or approved, and the ambient gh login is used.

.EXAMPLE
  pwsh scripts/dependabot-infra.ps1 -Pr 198
#>
[CmdletBinding()]
param(
  [int]$Pr,
  [switch]$CheckOnly,
  [string]$Repo = 'glunk-works/bounty-infra',
  [string]$Pusher = 'Seuss27',
  [string]$Approver = 'JaredGroves-603',
  [string]$Clone = (Get-Location).Path,
  [int]$PollSeconds = 20
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# The same paths plan-infra's `detect` step matches.
$DetectPattern = '^(infra/|\.github/workflows/(plan|deploy)-infra\.yml$)'
# The paths that start deploy-infra on a push to main.
$DeployPattern = '^(infra/|\.github/workflows/deploy-infra\.yml$)'
# `pre` is everything up to the `@`: the indent, the list marker and the action. A removed line and
# the added line it pairs with must agree on it exactly, so only the sha and the tag can change.
$PinLine = '^[+-](?<pre>\s*(?:-\s+)?uses:\s+(?<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?<sub>/[^@\s]+)?)@(?<sha>[0-9a-f]{40})\s+#\s+(?<tag>v?\d+(?:\.\d+)*)\s*$'
# Likewise for a provider constraint: the operator must stay the same and only the version moves.
$VersionLine = '^[+-](?<pre>\s*version\s*=\s*)"(?<op>[~<>=!]*\s*)(?<ver>\d+(?:\.\d+)*)"\s*$'
$EmptyCommitMessage = 'chore(deps): run the infra plan as a maintainer'

$script:Tokens = @{}
$Read = if ($CheckOnly) { '' } else { $Pusher }

function Get-Token([string]$User) {
  if (-not $script:Tokens.ContainsKey($User)) {
    $saved = $env:GH_TOKEN
    Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue
    try { $t = gh auth token -u $User 2>$null } finally { if ($null -ne $saved) { $env:GH_TOKEN = $saved } }
    if ($LASTEXITCODE -ne 0 -or -not $t) { throw "No gh login for $User on this machine (gh auth login, then rerun)." }
    $script:Tokens[$User] = "$t".Trim()
  }
  $script:Tokens[$User]
}

# Runs gh as $As (or the ambient login when $As is empty) and throws on a non-zero exit.
function Invoke-Gh([string]$As, [string[]]$A) {
  $saved = $env:GH_TOKEN
  try {
    if ($As) { $env:GH_TOKEN = Get-Token $As }
    $out = & gh @A
    if ($LASTEXITCODE -ne 0) { throw "gh $($A[0]) $($A[1]) failed (exit $LASTEXITCODE)." }
    $out
  } finally {
    if ($null -eq $saved) { Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue } else { $env:GH_TOKEN = $saved }
  }
}

function Read-Yes([string]$Prompt) { (Read-Host "$Prompt [y/N]") -match '^(y|yes)$' }

function Get-Json([string[]]$A) { Invoke-Gh $Read $A | ForEach-Object { $_ | ConvertFrom-Json } }

function Get-PrFiles([int]$N) { @(Get-Json @('api', '--paginate', "repos/$Repo/pulls/$N/files", '--jq', '.[]')) }

# Returns the Dependabot head (the sha the checks cover) and, on a rerun, the empty commit already
# pushed on top of it.
function Test-Commits([int]$N) {
  $c = @(Get-Json @('api', '--paginate', "repos/$Repo/pulls/$N/commits", '--jq',
      '.[] | {sha, author: .author.login, verified: .commit.verification.verified, tree: .commit.tree.sha, parent: .parents[0].sha}'))
  if ($c.Count -eq 0) { throw "#$N has no commits." }
  $pushed = $null
  $last = $c[-1]
  if ($c.Count -ge 2 -and $last.author -eq $Pusher -and $last.parent -eq $c[-2].sha -and $last.tree -eq $c[-2].tree) {
    $pushed = $last.sha
    $c = $c[0..($c.Count - 2)]
  }
  foreach ($x in $c) {
    if ($x.author -ne 'dependabot[bot]' -or -not $x.verified) {
      throw "Commit $($x.sha.Substring(0, 7)) on #$N is by '$($x.author)' (verified: $($x.verified)), not a verified Dependabot commit; review this PR by hand."
    }
  }
  [pscustomobject]@{ DependabotHead = $c[-1].sha; Pushed = $pushed }
}

# Throws unless every change is a removed line paired, in order within its block, with an added
# line that differs only in the sha and tag (a workflow pin) or only in the version (a provider
# constraint in infra/*.tf). Pins are then resolved upstream: each sha must be its tag's commit.
function Test-Diff($Files) {
  $want = @{}; $providers = @()
  foreach ($f in $Files) {
    $p = $f.filename
    if ($p -cmatch '^\.github/workflows/[^/]+\.ya?ml$') { $mode = 'pin'; $rx = $PinLine }
    elseif ($p -cmatch '^infra/[^/]+\.tf$') { $mode = 'provider'; $rx = $VersionLine }
    else { throw "$p is neither a workflow nor an infra/*.tf file; review this PR by hand." }
    if ($f.status -ne 'modified') { throw "$p is $($f.status), not modified; review this PR by hand." }
    if (-not $f.PSObject.Properties['patch'] -or -not $f.patch) { throw "GitHub returned no patch for $p; review this PR by hand." }
    $removed = [Collections.Generic.List[string]]::new()
    $added = [Collections.Generic.List[string]]::new()
    $pairs = [Collections.Generic.List[object]]::new()
    $flush = {
      if ($removed.Count -ne $added.Count) { throw "${p}: a block removes $($removed.Count) lines and adds $($added.Count); review this PR by hand." }
      for ($i = 0; $i -lt $removed.Count; $i++) { $pairs.Add(@($removed[$i], $added[$i])) }
      $removed.Clear(); $added.Clear()
    }
    foreach ($l in $f.patch -split "`n") {
      if ($l.StartsWith('-')) { if ($added.Count) { & $flush }; $removed.Add($l) }
      elseif ($l.StartsWith('+')) { $added.Add($l) }
      else { & $flush }
    }
    & $flush
    foreach ($pair in $pairs) {
      $old = [regex]::Match($pair[0], $rx); $new = [regex]::Match($pair[1], $rx)
      if (-not $old.Success) { throw "${p}: not a $mode line: $($pair[0])" }
      if (-not $new.Success) { throw "${p}: not a $mode line: $($pair[1])" }
      if ($old.Groups['pre'].Value -cne $new.Groups['pre'].Value) { throw "${p}: the change is more than a version bump: $($pair[0]) -> $($pair[1])" }
      if ($mode -eq 'provider') {
        if ($old.Groups['op'].Value -cne $new.Groups['op'].Value) { throw "${p}: the constraint operator changes: $($pair[0]) -> $($pair[1])" }
        $providers += "  ${p}: $($pair[0].Substring(1).Trim()) -> $($pair[1].Substring(1).Trim())"
        continue
      }
      $action = $new.Groups['repo'].Value + $new.Groups['sub'].Value
      if (@($action -split '/' | Where-Object { $_ -match '^\.+$' }).Count) { throw "${p}: odd action path: $action" }
      $key = "$($new.Groups['repo'].Value)@$($new.Groups['tag'].Value)"
      $sha = $new.Groups['sha'].Value
      if ($want.ContainsKey($key) -and $want[$key] -ne $sha) { throw "$key is pinned to two different shas." }
      $want[$key] = $sha
    }
  }
  foreach ($key in $want.Keys | Sort-Object) {
    $r, $tag = $key -split '@', 2
    $got = "$(Invoke-Gh $Read @('api', "repos/$r/commits/$tag", '--jq', '.sha'))".Trim()
    if ($got -ne $want[$key]) { throw "$key resolves to $got upstream, but the PR pins $($want[$key])." }
    Write-Host "  ok  $key = $($got.Substring(0, 12))"
  }
  if ($providers.Count -gt 0) {
    Write-Host 'Provider version changes (read the providers'' changelogs):'
    $providers | ForEach-Object { Write-Host $_ }
  }
  $providers.Count
}

$RunShape = '{id, status, conclusion, actor: .triggering_actor.login, url: .html_url}'

function Get-Run([string]$Workflow, [string]$Sha, [string]$Event) {
  $j = Invoke-Gh $Read @('api', "repos/$Repo/actions/workflows/$Workflow/runs?head_sha=$Sha&event=$Event&per_page=1", '--jq',
    ".workflow_runs[0] // empty | $RunShape")
  if ($j) { $j | ConvertFrom-Json } else { $null }
}

function Get-RunById([string]$Id) { Get-Json @('api', "repos/$Repo/actions/runs/$Id", '--jq', $RunShape) }

# Waits for the run, approves its $EnvName deployment once (after asking), and requires success.
# The run is picked once and followed by id. -Latest refuses to approve a run that a newer run of
# the same workflow on main has overtaken: approving it would apply older config.
function Complete-Run([string]$Workflow, [string]$Sha, [string]$Event, [string]$EnvName, [string]$Actor, [switch]$Latest) {
  Write-Host "Waiting for the $Workflow run on $($Sha.Substring(0, 7))..."
  while (-not ($run = Get-Run $Workflow $Sha $Event)) { Start-Sleep -Seconds $PollSeconds }
  if ($Actor -and $run.actor -ne $Actor) { throw "$Workflow run $($run.url) was triggered by $($run.actor), not $Actor." }
  $asked = $false
  while ($run.status -ne 'completed') {
    if ($run.status -eq 'waiting' -and -not $asked) {
      $ids = @(Get-Json @('api', "repos/$Repo/actions/runs/$($run.id)/pending_deployments", '--jq', '.[] | .environment | {id, name}') |
          Where-Object { $_.name -eq $EnvName } | ForEach-Object { $_.id })
      if ($ids.Count -eq 1) {
        if ($CheckOnly) { throw "$($run.url) waits for a $EnvName approval; rerun without -CheckOnly." }
        if ($Latest) {
          $newest = "$(Invoke-Gh $Read @('api', "repos/$Repo/actions/workflows/$Workflow/runs?event=push&branch=main&per_page=1", '--jq', '.workflow_runs[0].id'))".Trim()
          if ($newest -ne "$($run.id)") { throw "A newer $Workflow run exists; $($run.url) would apply older config. Reject it in the browser." }
        }
        if (-not (Read-Yes "Approve the $EnvName deployment for $($run.url)?")) { throw 'Stopped before the approval; rerun to continue.' }
        Invoke-Gh $Pusher @('api', '-X', 'POST', "repos/$Repo/actions/runs/$($run.id)/pending_deployments",
          '-F', "environment_ids[]=$($ids[0])", '-f', 'state=approved', '-f', 'comment=Approved after the pin check (scripts/dependabot-infra.ps1).') | Out-Null
        $asked = $true
      }
    }
    Start-Sleep -Seconds $PollSeconds
    $run = Get-RunById $run.id
  }
  if ($run.conclusion -ne 'success') { throw "$Workflow run $($run.url) ended $($run.conclusion)." }
  Write-Host "  $Workflow succeeded: $($run.url)"
}

function Get-ReviewGate([string]$Sha) {
  $s = @(Get-Json @('api', "repos/$Repo/commits/$Sha/status", '--jq', '.statuses[] | {context, state}') |
      Where-Object { $_.context -eq 'architect-review' } | ForEach-Object { $_.state })
  if (-not $s) {
    $s = @(Get-Json @('api', "repos/$Repo/commits/$Sha/check-runs?check_name=architect-review", '--jq', '.check_runs[] | {status, conclusion}') |
        ForEach-Object { if ($_.conclusion) { $_.conclusion } else { $_.status } })
  }
  if ($s) { $s[0] } else { '' }
}

if ($MyInvocation.InvocationName -eq '.') { return }

# ── pick the PR ──────────────────────────────────────────────────────────────
if (-not $Pr) {
  $open = @(Get-Json @('api', '--paginate', "repos/$Repo/pulls?state=open", '--jq', '.[] | {number, title, author: .user.login}') | Where-Object { $_.author -eq 'dependabot[bot]' })
  $hits = foreach ($o in $open) { if (@(Get-PrFiles $o.number | Where-Object { $_.filename -match $DetectPattern }).Count) { $o } }
  if (-not $hits) { Write-Host 'No open Dependabot PR trips the infra-plan gate.'; exit 0 }
  Write-Host 'Open Dependabot PRs that need the infra-plan route:'
  $hits | ForEach-Object { Write-Host "  #$($_.number)  $($_.title)" }
  Write-Host 'Rerun with -Pr <number>.'
  exit 0
}

$pull = Get-Json @('api', "repos/$Repo/pulls/$Pr", '--jq',
  '{state, merged, author: .user.login, base: .base.ref, headRepo: .head.repo.full_name, branch: .head.ref, head: .head.sha, mergeSha: .merge_commit_sha}')
if ($pull.author -ne 'dependabot[bot]') { throw "#$Pr is by $($pull.author), not Dependabot." }
$files = Get-PrFiles $Pr

if (-not $pull.merged) {
  if ($pull.state -ne 'open') { throw "#$Pr is closed without merging." }
  if ($pull.base -ne 'main' -or $pull.headRepo -ne $Repo) { throw "#$Pr is not a branch of $Repo into main." }
  if (-not @($files | Where-Object { $_.filename -match $DetectPattern }).Count) {
    Write-Host "#$Pr changes nothing under infra/ or the infra workflows; it needs no infra-plan route."
    exit 0
  }

  # ── check ──────────────────────────────────────────────────────────────────
  # The head is read before the diff and again after the check: the checked diff is the head's.
  $commits = Test-Commits $Pr
  $checked = if ($commits.Pushed) { $commits.Pushed } else { $commits.DependabotHead }
  if ($pull.head -ne $checked) { throw "#$Pr moved while it was read; rerun." }
  Write-Host "#$Pr ($($pull.branch)): checking the diff of Dependabot head $($commits.DependabotHead.Substring(0, 7))"
  $providerLines = Test-Diff $files
  $now = "$(Invoke-Gh $Read @('api', "repos/$Repo/pulls/$Pr", '--jq', '.head.sha'))".Trim()
  if ($now -ne $checked) { throw "#$Pr moved during the check; rerun." }
  if ($CheckOnly) { Write-Host 'Checks passed (-CheckOnly: nothing pushed or approved).'; exit 0 }
  if ($providerLines -gt 0 -and -not (Read-Yes 'Have you read those provider changes?')) { throw 'Stopped; nothing was pushed.' }

  # ── push the empty commit ─────────────────────────────────────────────────
  $head = $commits.Pushed
  if ($head) {
    Write-Host "The empty commit $($head.Substring(0, 7)) is already pushed."
  } else {
    $origin = "$(git -C $Clone remote get-url origin)".Trim()
    if ($origin -notmatch "github\.com[:/]$([regex]::Escape($Repo))(\.git)?$") { throw "$Clone's origin is $origin, not $Repo." }
    if (-not (Read-Yes "Push an empty commit onto $($pull.branch) as $Pusher?")) { throw 'Stopped; nothing was pushed.' }
    git -C $Clone fetch --quiet origin "refs/heads/$($pull.branch)"
    if ($LASTEXITCODE -ne 0) { throw 'git fetch failed.' }
    $fetched = "$(git -C $Clone rev-parse FETCH_HEAD)".Trim()
    if ($fetched -ne $commits.DependabotHead) { throw "The branch moved to $fetched during the check; rerun." }
    $wt = Join-Path ([IO.Path]::GetTempPath()) "dependabot-infra-$Pr-$PID"
    git -C $Clone worktree add --quiet --detach $wt $fetched
    if ($LASTEXITCODE -ne 0) { throw 'git worktree add failed.' }
    try {
      git -C $wt commit --quiet --allow-empty -m $EmptyCommitMessage
      if ($LASTEXITCODE -ne 0) { throw 'git commit failed.' }
      $head = "$(git -C $wt rev-parse HEAD)".Trim()
      git -C $wt push --quiet origin "HEAD:refs/heads/$($pull.branch)"
      if ($LASTEXITCODE -ne 0) { throw 'git push failed (a non-fast-forward means Dependabot pushed meanwhile; rerun).' }
    } finally {
      git -C $Clone worktree remove --force $wt
    }
    $by = "$(Invoke-Gh $Read @('api', "repos/$Repo/commits/$head", '--jq', '.author.login'))".Trim()
    if ($by -ne $Pusher) { throw "The pushed commit's author is '$by', not $Pusher; fix this clone's git identity, then finish by hand. Nothing was approved." }
    Write-Host "Pushed $($head.Substring(0, 7))."
  }

  # ── plan, review, merge ───────────────────────────────────────────────────
  Complete-Run 'plan-infra.yml' $head 'pull_request' 'infra-plan' $Pusher

  Write-Host "Waiting for wow-review to pass on $($head.Substring(0, 7)) (the architect-review status)..."
  while ((Get-ReviewGate $head) -ne 'success') { Start-Sleep -Seconds ([Math]::Max($PollSeconds, 60)) }
  Write-Host '  architect-review passed.'

  if (-not (Read-Yes "Approve #$Pr as $Approver and squash-merge it?")) { throw 'Stopped before the merge; rerun to continue.' }
  # The approval is pinned to the checked head, so a later push does not inherit it.
  Invoke-Gh $Approver @('api', '-X', 'POST', "repos/$Repo/pulls/$Pr/reviews", '-f', "commit_id=$head", '-f', 'event=APPROVE',
    '-f', 'body=Pins checked against their upstream tags; infra plan approved and green.') | Out-Null
  Invoke-Gh $Approver @('pr', 'merge', "$Pr", '-R', $Repo, '--squash', '--match-head-commit', $head) | Out-Null
  $pull = Get-Json @('api', "repos/$Repo/pulls/$Pr", '--jq', '{merged, mergeSha: .merge_commit_sha}')
  if (-not $pull.merged) { throw "#$Pr did not merge; check its required checks and rerun." }
  Write-Host "Merged #$Pr as $($pull.mergeSha.Substring(0, 7))."
}

# ── the deploy the merge starts ──────────────────────────────────────────────
if (@($files | Where-Object { $_.filename -match $DeployPattern }).Count) {
  Complete-Run 'deploy-infra.yml' $pull.mergeSha 'push' 'production' '' -Latest
} else {
  Write-Host 'The merge changes nothing deploy-infra watches; no deploy to approve.'
}
Write-Host "Done: #$Pr."
