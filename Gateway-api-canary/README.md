# Gateway API Canary Demo (kind + NGINX Gateway Fabric)

A local, reproducible demo of **progressive traffic shifting (canary deployment)** using the Kubernetes **Gateway API**, implemented with **NGINX Gateway Fabric (NGF)** on a **kind** cluster.

It demonstrates how `HTTPRoute` weighted `backendRefs` can split live traffic between two service versions, and outlines the operational workflow for rolling a canary out — and rolling it back — safely.

---

## Table of contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [1. Install kind](#1-install-kind)
- [2. Create the cluster](#2-create-the-cluster)
- [3. Install Helm](#3-install-helm)
- [4. Kustomize](#4-kustomize)
- [5. Install NGINX Gateway Fabric](#5-install-nginx-gateway-fabric)
- [6. How the pieces fit together](#6-how-the-pieces-fit-together)
- [7. Project layout](#7-project-layout)
- [8. Gateway and HTTPRoute manifests](#8-gateway-and-httproute-manifests)
- [9. Application manifests](#9-application-manifests)
- [10. Deploy](#10-deploy)
- [11. Verify the Gateway API resources](#11-verify-the-gateway-api-resources)
- [12. Expose the Gateway locally](#12-expose-the-gateway-locally)
- [13. Test the canary split](#13-test-the-canary-split)
- [14. Canary rollout workflow](#14-canary-rollout-workflow)
- [15. Troubleshooting](#15-troubleshooting)
- [16. Cleanup](#16-cleanup)
- [Roadmap / next steps](#roadmap--next-steps)

---

## Architecture

```
                    HTTP request
                         │
                         v
              ┌─────────────────────┐
              │   Gateway API        │
              │   (Gateway + Route)  │
              └──────────┬───────────┘
                         │
                     HTTPRoute
                  (weighted split)
                         │
              ┌──────────┴───────────┐
              │                      │
          weight 90              weight 10
              │                      │
              v                      v
        ┌───────────┐          ┌───────────┐
        │  demo-v1   │          │  demo-v2   │
        │  (stable)  │          │  (canary)  │
        └───────────┘          └───────────┘
```

Underneath, NGINX Gateway Fabric is the **controller** that watches `GatewayClass` / `Gateway` / `HTTPRoute` objects and configures a live NGINX data plane to match:

```
        Kubernetes API
              │
              v
         Gateway API
              │
     ┌────────┴────────┐
     │                 │
  Gateway          HTTPRoute
     │                 │
     └────────┬────────┘
              │
              v
   NGINX Gateway Fabric (controller)
              │
              v
            NGINX (data plane)
              │
              v
           Services
```

**Key distinction to know cold in an interview:** the **Gateway API** is a Kubernetes-native *API and object model* (`GatewayClass`, `Gateway`, `HTTPRoute`, etc.). **NGINX Gateway Fabric** is one *implementation* of that API — it's the controller/data-plane pair that turns those objects into running NGINX configuration. Swap NGF for another Gateway API implementation (e.g. Envoy Gateway, Istio) and the manifests above stay identical.

---

## Prerequisites

| Tool | Purpose | Check |
|---|---|---|
| [kind](https://kind.sigs.k8s.io/) | Local Kubernetes cluster in Docker | `kind version` |
| [kubectl](https://kubernetes.io/docs/tasks/tools/) | Cluster interaction | `kubectl version --client` |
| [Helm](https://helm.sh/) | Installs NGINX Gateway Fabric | `helm version` |
| Kustomize (bundled with kubectl) | Manages the manifest set | `kubectl kustomize --help` |
| Docker (or Podman) | kind's container runtime | `docker version` |

Kustomize ships inside modern `kubectl` — you generally don't need the standalone binary. Only install it separately if you specifically want the CLI outside of `kubectl`.

All commands below assume Linux/amd64. Substitute the appropriate binaries for macOS/Windows.

---

## 1. Install kind

```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.29.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
kind version
```

Expected output resembles:

```
kind v0.29.x
```

---

## 2. Create the cluster

A control-plane node plus three workers gives enough headroom to spread `demo-v1` and `demo-v2` replicas and observe realistic scheduling behavior.

```yaml
# kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4

nodes:
  - role: control-plane
  - role: worker
  - role: worker
  - role: worker
```

```bash
kind create cluster --name gateway-demo --config kind-config.yaml
kubectl get nodes
```

Expected:

```
NAME                        STATUS   ROLES
gateway-demo-control-plane  Ready    control-plane
gateway-demo-worker         Ready    <none>
gateway-demo-worker2        Ready    <none>
gateway-demo-worker3        Ready    <none>
```

---

## 3. Install Helm

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
helm version
```

---

## 4. Kustomize

Check whether `kubectl` already includes it:

```bash
kubectl kustomize --help
```

If that works, you're done — use `kubectl kustomize .` or `kubectl apply -k .` throughout this project. Only fetch the standalone binary if you have a specific reason to run `kustomize` outside of `kubectl`:

```bash
curl -s "https://api.github.com/repos/kubernetes-sigs/kustomize/releases/latest" \
  | grep browser_download_url \
  | grep linux_amd64 \
  | cut -d '"' -f 4 \
  | wget -i -
```

---

## 5. Install NGINX Gateway Fabric

```bash
helm repo add nginx https://helm.nginx.com/stable
helm repo update
helm search repo nginx/nginx-gateway-fabric

helm install ngf \
  oci://ghcr.io/nginx/charts/nginx-gateway-fabric \
  --create-namespace \
  -n nginx-gateway
```

Confirm the controller is running and that it registered a `GatewayClass`:

```bash
kubectl get pods -n nginx-gateway
kubectl get gatewayclass
```

Expected `GatewayClass` output (name may vary by chart version — **do not hard-code `nginx` in manifests until you've checked this**):

```
NAME    CONTROLLER
nginx   gateway.nginx.org/nginx-gateway-controller
```

Inspect the full object if you need the exact controller name:

```bash
kubectl get gatewayclass -o yaml
```

Look for:

```yaml
spec:
  controllerName: gateway.nginx.org/nginx-gateway-controller
```

> NGF creates the `GatewayClass` for you during install — your application manifests only need to *reference* it, not define it.

---

## 6. How the pieces fit together

| Layer | Object | Owned by |
|---|---|---|
| API model | `GatewayClass` | Created automatically by the NGF install |
| API model | `Gateway` | You (references the `GatewayClass`) |
| API model | `HTTPRoute` | You (references the `Gateway`, splits traffic) |
| Controller | NGINX Gateway Fabric | Watches the objects above |
| Data plane | NGINX | Configured by NGF to match the objects above |
| Workloads | `demo-v1` / `demo-v2` Deployments + Services | The `HTTPRoute` backends |

---

## 7. Project layout

```
gateway-canary-demo/
├── kind-config.yaml
├── namespace.yaml
├── app-v1-deployment.yaml
├── app-v1-service.yaml
├── app-v2-deployment.yaml
├── app-v2-service.yaml
├── gateway.yaml
├── httproute.yaml
└── kustomization.yaml
```

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: gateway-demo
```

---

## 8. Gateway and HTTPRoute manifests

### Gateway

```yaml
# gateway.yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: demo-gateway
  namespace: gateway-demo
spec:
  gatewayClassName: nginx   # confirm via `kubectl get gatewayclass`
  listeners:
    - name: http
      protocol: HTTP
      port: 80
      allowedRoutes:
        namespaces:
          from: Same
```

TLS is intentionally out of scope for this first pass — get the HTTP flow working end-to-end, then layer HTTPS on as a separate step (new listener + `ReferenceGrant`/certificate).

### HTTPRoute (the weighted split)

```yaml
# httproute.yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: demo-route
  namespace: gateway-demo
spec:
  parentRefs:
    - name: demo-gateway
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: demo-v1
          port: 80
          weight: 90
        - name: demo-v2
          port: 80
          weight: 10
```

`weight: 90` / `weight: 10` is the entire mechanism: Gateway API distributes matching requests across the listed `backendRefs` in proportion to their weights — 90% to `demo-v1`, 10% to `demo-v2`.

---

## 9. Application manifests

Both versions run the same lightweight [`hashicorp/http-echo`](https://github.com/hashicorp/http-echo) image so responses make it obvious which version served the request.

### v1 (stable)

```yaml
# app-v1-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-v1
  namespace: gateway-demo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: demo
      version: v1
  template:
    metadata:
      labels:
        app: demo
        version: v1
    spec:
      containers:
        - name: app
          image: hashicorp/http-echo:1.0
          args:
            - "-text=Hello from VERSION v1"
          ports:
            - containerPort: 5678
```

```yaml
# app-v1-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: demo-v1
  namespace: gateway-demo
spec:
  selector:
    app: demo
    version: v1
  ports:
    - port: 80
      targetPort: 5678
```

### v2 (canary)

```yaml
# app-v2-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-v2
  namespace: gateway-demo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: demo
      version: v2
  template:
    metadata:
      labels:
        app: demo
        version: v2
    spec:
      containers:
        - name: app
          image: hashicorp/http-echo:1.0
          args:
            - "-text=Hello from VERSION v2"
          ports:
            - containerPort: 5678
```

```yaml
# app-v2-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: demo-v2
  namespace: gateway-demo
spec:
  selector:
    app: demo
    version: v2
  ports:
    - port: 80
      targetPort: 5678
```

### Kustomization

```yaml
# kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - namespace.yaml
  - app-v1-deployment.yaml
  - app-v1-service.yaml
  - app-v2-deployment.yaml
  - app-v2-service.yaml
  - gateway.yaml
  - httproute.yaml
```

---

## 10. Deploy

```bash
kubectl apply -k .
```

Wait for everything to come up:

```bash
kubectl get pods -n gateway-demo -w
```

---

## 11. Verify the Gateway API resources

```bash
kubectl get gateway -n gateway-demo
kubectl describe gateway demo-gateway -n gateway-demo

kubectl get httproute -n gateway-demo
kubectl describe httproute demo-route -n gateway-demo
```

In both `describe` outputs, check the `Status.Conditions` block for:

- **`Programmed: True`** on the `Gateway` — NGF has actually configured the data plane.
- **`Accepted: True`** and **`ResolvedRefs: True`** on the `HTTPRoute` — the route is valid and its backends resolved.

If either is `False`, the `Message` field almost always names the exact problem (wrong `gatewayClassName`, missing `allowedRoutes`, unresolvable backend, etc.).

---

## 12. Expose the Gateway locally

Unlike a managed cluster (EKS/GKE/AKS), **kind does not provision a cloud load balancer** for the Gateway automatically:

```
Cloud cluster:  Gateway → Cloud LoadBalancer → Public IP
kind cluster:   Gateway → (needs manual exposure)
```

Find where NGF is actually listening before trying to curl anything:

```bash
kubectl get gateway -n gateway-demo demo-gateway -o wide
kubectl get gateway -n gateway-demo demo-gateway -o yaml
```

Look under `status.addresses` for the reachable address. The two common ways to reach it from your host:

- **Port-forward the NGF service** (simplest, good for a quick demo):

  ```bash
  kubectl -n nginx-gateway port-forward svc/ngf-nginx-gateway-fabric 8080:80
  curl -H "Host: demo.example.com" http://localhost:8080/
  ```

- **`extraPortMappings` in `kind-config.yaml`** (closer to production networking) — add a mapping from a host port to container port 80/443 on the node NGF's `Service` is bound to, then point `/etc/hosts` or your `curl -H "Host:"` header at it.

Don't assume `localhost:80` works until you've confirmed the address from `status.addresses`.

---

## 13. Test the canary split

With the Gateway reachable, hit it repeatedly and tally responses:

```bash
for i in $(seq 1 50); do
  curl -s -H "Host: demo.example.com" http://localhost:8080/
  echo
done | sort | uniq -c
```

Expected (approximately, given the 90/10 weight):

```
 45 Hello from VERSION v1
  5 Hello from VERSION v2
```

Small sample sizes will wobble around the target ratio — that's expected statistical noise, not a misconfiguration.

---

## 14. Canary rollout workflow

The manifests above are the mechanism. The workflow below is what actually makes this project interview-relevant — operating and troubleshooting the Gateway, not just installing it:

```
100% v1
   │
   v
deploy v2 (weight 0 or omitted)
   │
   v
shift to 5% v2
   │
   v
watch metrics / error rate
   │
   ├── healthy → shift to 25% v2 → 50% → 100% v2
   │
   └── elevated 5xx / latency detected
            │
            v
        roll back to 100% v1
```

To shift weight, edit `httproute.yaml` and reapply:

```bash
kubectl apply -k .
```

or patch it directly for a fast rollback:

```bash
kubectl patch httproute demo-route -n gateway-demo --type merge -p \
  '{"spec":{"rules":[{"matches":[{"path":{"type":"PathPrefix","value":"/"}}],"backendRefs":[{"name":"demo-v1","port":80,"weight":100},{"name":"demo-v2","port":80,"weight":0}]}]}}'
```

A minimal way to simulate a failing canary and validate this workflow end-to-end: point `demo-v2`'s container args at a nonzero exit code or an endpoint that 500s, shift weight to it, and confirm you can detect and roll back before moving on to a real observability stack (Prometheus/Grafana, or the k6 + metrics/logs/traces pipeline from the companion architecture diagram).

---

## 15. Troubleshooting

| Symptom | Likely cause | Check |
|---|---|---|
| `Gateway` stuck `Programmed: False` | Wrong `gatewayClassName`, or NGF controller not ready | `kubectl get gatewayclass`, `kubectl get pods -n nginx-gateway` |
| `HTTPRoute` `ResolvedRefs: False` | Service name/port typo, or Service in a different namespace without a `ReferenceGrant` | `kubectl describe httproute demo-route -n gateway-demo` |
| `curl` hangs or connection refused | Gateway not exposed from the host yet | Re-check `status.addresses`, confirm port-forward or `extraPortMappings` |
| Traffic split looks nowhere near 90/10 | Sample size too small, or both backends returning the same text (bad image tag) | Re-run with a larger `seq`; confirm `-text` args differ per Deployment |
| `kubectl apply -k .` fails on `GatewayClass` | Manifest tries to create a `GatewayClass` that NGF already owns | Remove any `GatewayClass` resource from your kustomization — reference NGF's, don't recreate it |

---

## 16. Cleanup

```bash
kubectl delete -k .
helm uninstall ngf -n nginx-gateway
kind delete cluster --name gateway-demo
```

---

## Roadmap / next steps

- [ ] Add a TLS listener (HTTPS) once the HTTP path is validated
- [ ] Replace manual `curl` loops with `k6` load-test scripts for repeatable traffic generation
- [ ] Wire up Prometheus + Grafana (or an existing observability stack) to watch error rate during a live weight shift
- [ ] Automate the weight-shift / rollback sequence in section 14 as a script or CI job
- [ ] Swap NGINX Gateway Fabric for a second Gateway API implementation (e.g. Envoy Gateway) to demonstrate the API/implementation split in practice
