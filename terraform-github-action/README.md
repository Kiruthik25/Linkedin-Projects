# Terraform CI/CD with GitHub Actions & AWS OIDC

This repository uses **GitHub Actions** with **AWS IAM OIDC federation** to run Terraform safely — no long-lived AWS access keys are stored in GitHub.

## Architecture

```
GitHub PR
   │
   ▼
GitHub Actions
   │
   ▼
GitHub OIDC token
   │
   ▼
AWS IAM Role
   │
   ▼
Temporary AWS credentials
   │
   ▼
Terraform init / validate / plan
```

### Recommended split: plan vs. apply

Giving every pull request a powerful AWS role is a security risk — if someone opens a PR from an untrusted fork, that workflow run could inherit dangerous permissions. This repo separates **plan** (PR) from **apply** (merge to `main`):

```
PR
 │
 ├── fmt
 ├── validate
 └── plan
       │
       ▼
  limited AWS role  (TerraformPlanRole)

MERGE TO MAIN
 │
 ▼
terraform apply
 │
 ▼
deployment AWS role  (TerraformApplyRole)
```

`cd.yaml` already restricts `apply` to pushes on `main`, which is the right direction. Using **two separate IAM roles** — one for PR plans, one for main-branch applies — is safer than reusing a single powerful role for both.

---

## Setup Guide

### Step 1 — Create the GitHub OIDC provider in AWS

**AWS Console → IAM → Identity providers → Add provider**

| Field | Value |
|---|---|
| Provider type | OpenID Connect |
| Provider URL | `https://token.actions.githubusercontent.com` |
| Audience | `sts.amazonaws.com` |

> These are GitHub's officially documented values for AWS OIDC. You only need to create this **once per AWS account**.

---

### Step 2 — Create an IAM role for GitHub Actions

**AWS Console → IAM → Roles → Create role**

| Field | Value |
|---|---|
| Trusted entity type | Web identity |
| Identity provider | `token.actions.githubusercontent.com` |
| Audience | `sts.amazonaws.com` |

Restrict the role to your repository:

| Field | Value |
|---|---|
| GitHub organization | `Kiruthik25` |
| GitHub repository | `terraform-testing` |

> AWS recommends restricting the OIDC role by GitHub organization/repository/branch rather than allowing any GitHub repository to assume it.

Suggested role name: `GitHubActionsTerraformRole`

---

### Step 3 — Configure a trust policy scoped to the workflow

⚠️ **Important:** the `sub` claim in the OIDC token differs depending on how the workflow was triggered.

- **Pull request workflows** → `repo:Kiruthik25/terraform-testing:pull_request`
- **Main branch (push) workflows** → `repo:Kiruthik25/terraform-testing:ref:refs/heads/main`

**Trust policy for the PR / plan role:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:Kiruthik25/terraform-testing:pull_request"
        }
      }
    }
  ]
}
```

For a **main-branch apply role**, use the same policy but change the `sub` condition to:

```
repo:Kiruthik25/terraform-testing:ref:refs/heads/main
```

Because these claims differ, use **two IAM roles** rather than one shared role:

```
GitHub PR
   │
   ▼
TerraformPlanRole
   │
   ▼
limited permissions


GitHub main
   │
   ▼
TerraformApplyRole
   │
   ▼
deployment permissions
```

This is edited via:
**AWS Console → IAM → Roles → your role → Trust relationships → Edit trust policy**

---

### Step 4 — Attach Terraform permissions to the role

Permissions depend on what your Terraform configuration provisions. This repository's Terraform provider is **AWS**, and if it manages resources such as:

- EC2
- VPC
- Security Groups
- IAM
- S3

...the role needs permissions matching those services.

**For learning/testing only**, you can temporarily use:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "*",
      "Resource": "*"
    }
  ]
}
```

> ⚠️ **Do not use this in production.** It grants administrator-level access. Once the workflow is verified working, replace it with least-privilege permissions scoped to your actual Terraform resources.

---

### Step 5 — GitHub Secrets & Variables

`ci.yaml` expects the following to be configured under:
**GitHub → terraform-testing → Settings → Secrets and variables → Actions**

| Name | Type | Value |
|---|---|---|
| `AWS_ROLE_ARN` | Secret | `arn:aws:iam::<YOUR_AWS_ACCOUNT_ID>:role/GitHubActionsTerraformRole` |
| `AWS_REGION` | Variable | e.g. `us-east-1` |
| `BUCKET_NAME` | Secret | `kiruthik-terrafrom-demo` (Terraform backend bucket, passed to `terraform init`) |

> ⚠️ Do **not** store AWS access keys or secret keys as secrets — that's the entire point of using OIDC federation.

---

## Summary

| Trigger | OIDC `sub` claim | IAM Role | Permissions |
|---|---|---|---|
| Pull request | `repo:Kiruthik25/terraform-testing:pull_request` | `TerraformPlanRole` | Limited (plan/validate only) |
| Push to `main` | `repo:Kiruthik25/terraform-testing:ref:refs/heads/main` | `TerraformApplyRole` | Deployment-level |

Using dedicated roles per trigger type keeps pull requests — including those from forks — from ever gaining apply-level AWS access.
