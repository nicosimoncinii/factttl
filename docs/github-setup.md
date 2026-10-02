# GitHub setup checklist

The local workspace is not connected to a GitHub remote and the available `gh` account token is invalid. No remote repository, branch, label, milestone, issue, topic, or protection rule was created.

After authenticating the intended GitHub account, create a **public** repository named `factttl` with this description:

> Give AI facts a time-to-live. Detect stale and time-sensitive claims before they become outdated answers.

Enable Issues and Discussions. Use the README and MIT license already present. Add the topics listed in [git strategy](git-strategy.md). Create `main` as the default branch; do not create `develop`. Create milestones and labels from [the backlog](backlog.md) and [`labels.json`](../.github/labels/labels.json). For a personal repository, begin with light branch protection as described in `git-strategy.md`.

The project name has not been changed. Recheck exact repository and package registry availability before creating the public resources. This file is an operational checklist, not an indication that GitHub resources already exist.
