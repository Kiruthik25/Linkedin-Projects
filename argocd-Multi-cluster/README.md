# Argo CD ApplicationSet — Multi-Cluster GitOps Guide

A hands-on, end-to-end guide to Argo CD **ApplicationSets** — what they are, why they exist, and how to configure them using the **List**, **Cluster**, and **Matrix** generators across multiple Kubernetes clusters.

---

## Table of Contents

1. [What Is an ApplicationSet?](#1-what-is-an-applicationset)
2. [Why Use ApplicationSet?](#2-why-use-applicationset)
3. [How It Works](#3-how-it-works)
4. [Prerequisites](#4-prerequisites)
5. [Environment Setup](#5-environment-setup)
6. [Core Building Blocks: Generators & Template](#6-core-building-blocks-generators--template)
7. [Demo 1 — List Generator](#7-demo-1--list-generator)
8. [Demo 2 — Cluster Generator](#8-demo-2--cluster-generator)
9. [Demo 3 — Matrix Generator (Git × Clusters)](#9-demo-3--matrix-generator-git--clusters)
10. [goTemplate & goTemplateOptions](#10-gotemplate--gotemplateoptions)
11. [Generator Decision Matrix](#11-generator-decision-matrix)
12. [Architectural Patterns](#12-architectural-patterns)
13. [Application vs. ApplicationSet](#13-application-vs-applicationset)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. What Is an ApplicationSet?

An **ApplicationSet** is a Kubernetes custom resource that automatically **generates and manages multiple Argo CD `Application` resources** from a single template and a set of inputs.

Instead of hand-writing many `Application` manifests, you define **one** `ApplicationSet`, and its controller creates, updates, and deletes the corresponding `Application` resources for you.

## 2. Why Use ApplicationSet?

Suppose you have:

- 20 microservices
- 5 Kubernetes clusters
- 3 environments (dev, staging, prod)

Without ApplicationSet, you'd need to hand-maintain **up to 300 individual `Application` manifests**.

With ApplicationSet, you define just:

- a **template**
- a **generator** (which supplies the list of apps, clusters, or directories)

The controller generates every `Application` for you, and keeps them in sync as the inputs change.

**Benefits**

| Benefit | Description |
|---|---|
| Less duplication | No more hundreds of near-identical `Application` manifests |
| Scales easily | Add apps, clusters, or environments without hand-editing YAML |
| Stays in sync | Applications track changes in Git or Argo CD's cluster registrations |
| Centralized logic | One place defines how every Application is generated |

## 3. How It Works

An ApplicationSet has two main parts:

### Generator
Produces a list of key/value inputs. Common generator types:

| Generator | Use Case |
|---|---|
| **List** | Static list of values |
| **Git** | Generate Applications from directories or files in a Git repo |
| **Clusters** | Deploy the same app to multiple Kubernetes clusters |
| **Matrix** | Combine multiple generators (e.g. apps × clusters) |
| **Pull Request** | Create preview environments for Git PRs |
| **SCM Provider** | Discover repositories from GitHub, GitLab, Bitbucket, etc. |

### Template
Defines how each generated Argo CD `Application` should look — source repo, sync policy, destination, and namespace.

```
ApplicationSet
     │
     ├── Generator
     │      ├── app1
     │      ├── app2
     │      └── app3
     │
     └── Template
             │
             ├── Application app1
             ├── Application app2
             └── Application app3
```

### Minimal example — Git directory generator

Given a repo laid out as:

```
apps/
   frontend/
   backend/
   payment/
```

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: apps
spec:
  generators:
  - git:
      repoURL: https://github.com/example/gitops.git
      revision: main
      directories:
      - path: apps/*

  template:
    metadata:
      name: '{{path.basename}}'

    spec:
      project: default

      source:
        repoURL: https://github.com/example/gitops.git
        targetRevision: main
        path: '{{path}}'

      destination:
        server: https://kubernetes.default.svc
        namespace: '{{path.basename}}'

      syncPolicy:
        automated: {}
```

This automatically creates:

```
Application
 ├── frontend
 ├── backend
 └── payment
```

No need to define each `Application` separately.

### Multi-cluster example — Clusters generator

Given registered clusters `dev`, `staging`, `prod`, a Clusters generator can automatically create:

```
Application
├── myapp-dev
├── myapp-staging
└── myapp-prod
```

Add a new cluster (e.g. `qa`) to Argo CD, and the ApplicationSet automatically generates `myapp-qa` — no manual step required.

---

## 4. Prerequisites

Before working through the demos below, make sure you have:

- [ ] Argo CD installed on your "hub"/management cluster, with the `argocd` CLI installed locally
- [ ] `kubectl` configured with contexts for **every** cluster you plan to register (e.g. Mumbai, N. Virginia)
- [ ] Admin/cluster-admin access on each target cluster (required because Argo CD provisions a privileged `ServiceAccount` on each one — see [Section 5](#5-environment-setup))
- [ ] A Git repository containing your application manifests, reachable from the Argo CD cluster
  - If the repo is **private**, register it first: `argocd repo add https://github.com/<org>/<repo>.git --username <user> --password <token>`
- [ ] Network connectivity from the Argo CD cluster to every target cluster's Kubernetes API server

---

## 5. Environment Setup

### 5.1 Log in to Argo CD

```bash
# Login to Argo CD using local port-forwarded endpoint
argocd login localhost:8080

# List clusters registered with Argo CD
argocd cluster list
```

### 5.2 Register an external cluster

```bash
argocd cluster add varun.joshi@cwvj-nvirginia.us-east-1.eksctl.io
```

**What actually happens under the hood:**

```
WARNING: This will create a service account `argocd-manager`
on the cluster referenced by context `mumbai-dev`
with full cluster level privileges.
```

Argo CD needs credentials to talk to the target cluster, so it provisions:

1. **ServiceAccount** — `argocd-manager` created in the `kube-system` namespace. This is the identity Argo CD authenticates as.

   ```yaml
   apiVersion: v1
   kind: ServiceAccount
   metadata:
     name: argocd-manager
     namespace: kube-system
   ```

2. **ClusterRole** — `argocd-manager-role` defines *what* actions are allowed, cluster-wide (not namespace-scoped). "Full cluster level privileges" means cluster-admin-like access, since Argo CD must be able to deploy, create namespaces, update Deployments, delete resources, and watch cluster state anywhere.

3. **ClusterRoleBinding** — `argocd-manager-role-binding` connects the ServiceAccount to the ClusterRole:

   ```
   ServiceAccount (argocd-manager)
           │
           ▼
   ClusterRole (argocd-manager-role)
   ```

4. **Bearer token** — `argocd-manager-long-lived-token` is created and stored by Argo CD, then sent in the `Authorization` header on every API call to that cluster:

   ```
   ServiceAccount → Bearer Token → Stored by Argo CD → Used for API authentication
   ```

5. **Cluster registration** — Argo CD stores the API server endpoint plus the bearer token and TLS certificate, e.g.:

   ```
   Cluster 'https://507065156D9C55FDCF516D15FFFD3895.gr7.ap-south-1.eks.amazonaws.com' added
   ```

   This is persisted as a `Secret` in the Argo CD namespace (commonly `argocd`).

> **Tip — friendly cluster names:** By default, Argo CD names a registered cluster after its API server URL or kube context (e.g. `varun.joshi@cwvj-nvirginia.us-east-1.eksctl.io`), which is long and unwieldy in templates. Give it a short, stable alias at registration time:
> ```bash
> argocd cluster add <context> --name us-prod --upsert
> ```
> The `--name` value is what later appears in `destination.name` inside your ApplicationSet templates (see [Demo 3](#9-demo-3--matrix-generator-git--clusters)).

### 5.3 Verify cluster registration

```bash
# Verify all clusters registered with Argo CD
argocd cluster list
```

You should see two entries:

- `in-cluster` (Mumbai)
- `varun.joshi@cwvj-nvirginia.us-east-1.eksctl.io` (N. Virginia)

---

## 6. Core Building Blocks: Generators & Template

An ApplicationSet has two fundamental building blocks:

### Generators
Generators define the **scope** of the ApplicationSet. They answer:

- How many Applications need to be created?
- For which targets?
- Based on what source of truth?

> **Generators do not define application behavior.** They say nothing about Git repositories, sync policies, namespaces, or how an app behaves. Their only responsibility is to define **where and for whom** Applications should exist.

### Template
The template is the blueprint for an Argo CD `Application`. It defines:

- what the Application should look like
- where it pulls manifests from
- how it syncs
- where it deploys

> **Key rule:** the template is evaluated **once per generator element**. A generator that produces 2 elements renders the template twice → 2 Applications. A generator that produces 10 elements → 10 Applications.

---

## 7. Demo 1 — List Generator

The **list generator** is the most explicit and beginner-friendly generator — every element is written directly in YAML.

```yaml
generators:
- list:
    elements:
    - region: mumbai
      destinationName: in-cluster
      namespace: app1-mumbai-ns
    - region: nvirginia
      destinationName: varun.joshi@cwvj-nvirginia.us-east-1.eksctl.io
      namespace: app1-nvirginia-ns
```

Two elements → the template renders twice → two Argo CD Applications are created, one per region.

**Best for:** small, static sets of targets where explicit, reviewable YAML is more valuable than automation.

---

## 8. Demo 2 — Cluster Generator

The **cluster generator** creates Argo CD Applications by iterating over Kubernetes clusters **already registered in Argo CD**. Clusters are selected using **labels**, and one Application is generated per matching cluster.

- Argo CD's cluster inventory is the source of truth
- Cluster labels drive Application generation
- Applications automatically appear or disappear as clusters are added, labeled, or removed

Best suited for infrastructure-driven GitOps, where applications are expected to follow clusters across regions, environments, or platforms.

```yaml
template:
    metadata:
      name: "app1-{{.metadata.labels.region}}"
    spec:
      project: default

      source:
        repoURL: https://github.com/CloudWithVarJosh/app1-config.git
        targetRevision: main
        path: "{{.metadata.labels.region}}/manifests"

      destination:
        name: "{{.name}}"
        namespace: "app1-{{.metadata.labels.region}}-ns"
```

### 8.1 Prerequisite: labeling clusters in Argo CD

Clusters must be labeled inside Argo CD, because labels are what the cluster generator uses as its input.

**External clusters** — labeled at onboarding time via CLI:

```bash
argocd cluster add <context> --label app=app1 --label region=nvirginia --upsert
```

> **Note:** `--upsert` is required when the cluster is already registered. It updates existing cluster metadata (labels) instead of failing on a spec mismatch.

**In-cluster** (where Argo CD itself runs) — implicitly registered at install time, so it isn't normally labeled with `argocd cluster add`. Instead, apply labels afterward via the UI:

> Settings → Clusters → in-cluster → Edit → Add Labels

This updates the metadata that the ApplicationSet controller reads for the in-cluster entry.

> **Note:** the in-cluster can also be labeled via CLI by editing Argo CD's internal cluster inventory, but the UI approach is preferred for clarity and safety in demos and learning environments.

Once applied, labels are available to both the cluster generator and the ApplicationSet template — Argo CD treats in-cluster and external clusters identically.

### 8.2 Production-friendly naming

```yaml
metadata:
  name: "app1-{{.metadata.labels.region}}"
```

Although `{{.name}}` is available, using it directly for Application naming is usually not ideal, since cluster names are often long and implementation-specific. Instead, use a **business-level identifier**, such as `region`, derived from cluster labels:

- `app1-mumbai`
- `app1-nvirginia`

### 8.3 Verifying `{{.metadata.labels.region}}`

Cross-check the value directly from the cluster-specific `Secret` Argo CD maintains:

```bash
kubectl get secrets -n argocd
```

Example entries:

```
cluster-9e43b85016537c5b4557806b2f581817.sk1.us-east-1.eks.amazonaws.com-499980605
cluster-kubernetes.default.svc-3396314289
```

Inspect the in-cluster `Secret`:

```bash
kubectl get secret -n argocd cluster-kubernetes.default.svc-3396314289 -o yaml
```

The relevant section the ApplicationSet template reads:

```yaml
metadata:
  labels:
    app: app1
    region: mumbai
```

This is exactly why `{{.metadata.labels.region}}` resolves correctly.

---

## 9. Demo 3 — Matrix Generator (Git × Clusters)

The **matrix generator** combines two (or more) generators, producing the **Cartesian product** of their outputs. This is the pattern to reach for once you need to deploy **N applications across M clusters** without writing N × M manifests by hand.

In this demo we combine:

- **Dimension 1 — Git directory generator:** one element per top-level folder in the repo (one folder = one app)
- **Dimension 2 — List generator:** one element per target cluster

### 9.1 Required repository layout

The Git dimension uses `directories: - path: "*"`, so every top-level directory in the repo is treated as one application. Each of those directories must contain a `manifests/` subfolder, matching the `path` used in the template:

```
Argocd-project/
├── frontend/
│   └── manifests/
├── backend/
│   └── manifests/
└── payment/
    └── manifests/
```

### 9.2 Required cluster naming

The list dimension's `clusterName` values (`mumbai-dev`, `us-prod`) are used directly in `destination.name`, so **they must exactly match the names Argo CD shows in `argocd cluster list`.** Register (or re-label) each cluster with a matching `--name`:

```bash
argocd cluster add <mumbai-context> --name mumbai-dev --upsert
argocd cluster add <nvirginia-context> --name us-prod --upsert
```

> If a `destination.name` doesn't match a registered cluster name exactly, the generated Application will fail to sync with a "cluster not found" style error — see [Troubleshooting](#14-troubleshooting).

### 9.3 ApplicationSet manifest

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: matrix-clusters
  namespace: argocd
spec:
  goTemplate: true
  goTemplateOptions:
    - missingkey=error
  generators:
    - matrix:
        generators:
          # Dimension 1: environments from Git
          - git:
              repoURL: https://github.com/Kiruthik25/Argocd-project.git
              revision: main
              directories:
                - path: "*"
          # Dimension 2: clusters (explicit, simple)
          - list:
              elements:
                - region: mumbai
                  clusterName: mumbai-dev
                - region: nvirginia
                  clusterName: us-prod
  template:
    metadata:
      name: "app-{{.path.basename}}-{{.region}}"
    spec:
      project: default
      source:
        repoURL: https://github.com/Kiruthik25/Argocd-project.git
        targetRevision: main
        path: "{{.path.basename}}/manifests"
      destination:
        name: "{{.clusterName}}"
        namespace: "app-{{.path.basename}}-ns"
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
```

### 9.4 What this produces

With 3 app directories (`frontend`, `backend`, `payment`) × 2 clusters (`mumbai-dev`, `us-prod`), the matrix generator produces **6 elements**, so the template renders **6 times**:

```
Application
├── app-frontend-mumbai     → cluster: mumbai-dev
├── app-frontend-nvirginia  → cluster: us-prod
├── app-backend-mumbai      → cluster: mumbai-dev
├── app-backend-nvirginia   → cluster: us-prod
├── app-payment-mumbai      → cluster: mumbai-dev
└── app-payment-nvirginia   → cluster: us-prod
```

Add a new app folder, or a new cluster to the list, and the matrix automatically expands — no manual manifest authoring.

### 9.5 Notes on this manifest's fields

| Field | Why it's here |
|---|---|
| `metadata.namespace: argocd` | The ApplicationSet resource itself must live in Argo CD's own namespace so the controller picks it up. |
| `goTemplate: true` + `missingkey=error` | Required for the `{{.path.basename}}` / `{{.region}}` / `{{.clusterName}}` dot-notation used throughout this template — see [Section 10](#10-gotemplate--gotemplateoptions). |
| `syncOptions: [CreateNamespace=true]` | Each app deploys into a namespace derived from its path (`app-<name>-ns`), which won't exist yet on a fresh cluster — this flag creates it automatically instead of failing the sync. |
| `syncPolicy.automated.prune / selfHeal` | Keeps every generated Application continuously reconciled with Git, and removes resources deleted from Git — standard for a matrix of many apps you don't want to babysit individually. |

---

## 10. goTemplate & goTemplateOptions

```yaml
spec:
  goTemplate: true
  goTemplateOptions:
    - missingkey=error
```

Enabling `goTemplate` unlocks **Go templating**, which is more powerful and stricter than basic variable substitution. If you're familiar with Helm, this syntax will look familiar — Helm charts use the same Go templates, hence the same `{{ }}` notation.

Go templating gives you:

- variable interpolation
- conditionals and functions
- stricter error handling

`missingkey=error` forces ApplicationSet rendering to **fail fast** when a variable is referenced in the template but not provided by the generator. Without this option, missing values silently render as empty strings, which leads to hard-to-detect misconfigurations. **This is a best practice, especially in production.**

---

## 11. Generator Decision Matrix

| Generator | Where Intent Lives | Best Fit | Primary Strength | Cost of Choosing It |
|---|---|---|---|---|
| **List** | Explicit YAML | Small scale, deliberate control | Predictable, reviewable | Manual, does not scale |
| **Cluster** | Argo CD cluster inventory | App must follow clusters automatically | Zero duplication | Tightly coupled to infra |
| **Git (Directory)** | Git repository structure | Environments are folder-defined | Simple, intuitive | Git layout becomes API |
| **Git (Files)** | Config data in Git | Governance, approval, auditability matter | Explicit and controlled | More configuration |
| **Matrix** | Multiple intent sources | Scale across independent dimensions | Compositional and scalable | Requires discipline |

---

## 12. Architectural Patterns

| Platform Reality | Generator Pattern |
|---|---|
| Few clusters, few environments | List |
| Platform-owned clusters | Cluster |
| App teams own environment lifecycle | Git (Directory) |
| Central SRE or governance model | Git (Files) |
| Many clusters and many environments | Matrix (composed generators) |

---

## 13. Application vs. ApplicationSet

| Application | ApplicationSet |
|---|---|
| Manages a single application | Manages many Applications |
| Created manually | Applications generated automatically |
| Best for a small number of apps | Best for many apps, clusters, or environments |
| No generators | Uses generators and templates |

**In short:** an Argo CD ApplicationSet is an automation layer that generates and manages multiple Argo CD `Application` resources from a single declarative configuration — ideal for multi-application, multi-environment, or multi-cluster GitOps.

---

## 14. Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Application shows `Unknown` / cluster error at sync time | `destination.name` doesn't match a registered cluster name | `argocd cluster list` → confirm exact name; re-register with `--name <alias> --upsert` if needed |
| ApplicationSet renders 0 Applications | Generator produced no elements (e.g. no matching directories, no clusters with the required label) | Check repo structure / `kubectl get secret -n argocd -l argocd.argoproj.io/secret-type=cluster --show-labels` |
| Template fails to render / controller logs `map has no entry for key` | A `{{ .field }}` referenced in the template isn't provided by the generator, and `missingkey=error` caught it | Add the missing field to the generator, or fix the template's field name |
| Sync fails with `namespaces "app-x-ns" not found` | Target namespace doesn't exist and wasn't allowed to be created | Add `CreateNamespace=true` to `syncOptions` |
| Cluster registration warns about "full cluster level privileges" | Expected — Argo CD needs cluster-admin-like access via the `argocd-manager` ServiceAccount to manage resources | No action needed unless your org requires scoped RBAC instead of the default |
