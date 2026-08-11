# Kubernetes Observability Stack

A production-style monitoring setup for a 3-tier microservices application (`user`, `order`, `payment`) running on Kubernetes, built with **Prometheus**, **Grafana**, and **Alertmanager** via the `kube-prometheus-stack` Helm chart.

This project demonstrates real Kubernetes-native service discovery — no manually maintained scrape targets — using `ServiceMonitor` custom resources managed by the Prometheus Operator.

---

## Architecture

```
                        Kubernetes
                              │
              ┌───────────────┴──────────────┐
              │                              │
           apps                           monitoring
              │                              │
      ┌───────┼────────┐             ┌───────┼────────┐
      │       │        │             │       │        │
      ▼       ▼        ▼             ▼       ▼        ▼
    user    order   payment      Prometheus Grafana Alertmanager
      │       │        │             │
      └───────┼────────┘             │
              │                      │
          Services                   │
              │                      │
              ▼                      │
        ServiceMonitor ─────────────┘
              │
              ▼
           /metrics
```

**Monitoring data flow:**

```
Application → /metrics → Kubernetes Service → ServiceMonitor → Prometheus
→ PromQL → Recording Rules → Alerting Rules → Alertmanager → Notifications
```

---

## Stack

| Component | Role |
|---|---|
| Prometheus Operator | Manages Prometheus, Alertmanager, and CRDs |
| Prometheus | Scrapes and stores metrics |
| Alertmanager | Routes and deduplicates firing alerts |
| Grafana | Dashboards and visualization |
| kube-state-metrics | Kubernetes object state metrics |
| node-exporter | Host-level metrics |
| ServiceMonitor (CRD) | Declarative scrape configuration for app services |
| PrometheusRule (CRD) | Recording and alerting rule definitions |

---

## Prerequisites

- A running Kubernetes cluster (this project uses [kind](https://kind.sigs.k8s.io/))
- `kubectl` configured against the cluster
- [Helm](https://helm.sh/) 3.x
- The `user`, `order`, and `payment` Deployments and Services already applied in the `apps` namespace, each exposing a working `/metrics` endpoint

---

## Repository layout

```
.
├── monitoring/
│   ├── kube-prometheus-stack-values.yaml   # Helm values for the stack
│   ├── servicemonitor.yaml                 # Scrape config for app services
│   ├── prometheus-rules.yaml               # Recording + alerting rules
│   ├── grafana-dashboard-configmap.yaml    # Dashboard provisioned via sidecar
│   └── manual-scrape-example.yaml          # Reference only — not applied
└── README.md
```

---

## Setup

Apply components in this order to keep troubleshooting straightforward:

```
1. Helm / kube-prometheus-stack
2. Verify Prometheus / Grafana / Alertmanager are Running
3. Apply ServiceMonitor
4. Verify targets = UP
5. Apply PrometheusRule
6. Verify recording rules + alerts
7. Apply Grafana ConfigMap
8. Generate traffic
9. Simulate failures
10. Verify dashboard + alerts
```

### 1. Verify the cluster and applications

```bash
kubectl get nodes
kubectl get pods -n apps
kubectl get svc -n apps
```

All three services (`user-service`, `order-service`, `payment-service`) should be `Running`.

### 2. Verify `/metrics` before installing Prometheus

```bash
kubectl port-forward svc/user-service 8001:8000 -n apps
curl http://localhost:8001/metrics
```

Repeat for `order-service` (`8002`) and `payment-service` (`8003`). Confirm each returns metric output before continuing.

### 3. Install Helm

```bash
helm version || sudo snap install helm --classic
```

### 4. Add the Prometheus Community Helm repo

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm search repo prometheus-community
```

### 5. Create the monitoring namespace

```bash
kubectl create namespace monitoring
kubectl get namespaces
```

### 6. Install kube-prometheus-stack

`monitoring/kube-prometheus-stack-values.yaml` must include:

```yaml
prometheus:
  prometheusSpec:
    serviceMonitorSelectorNilUsesHelmValues: false
    ruleSelectorNilUsesHelmValues: false
    retention: 7d
    scrapeInterval: 30s
    evaluationInterval: 30s

grafana:
  enabled: true
  sidecar:
    dashboards:
      enabled: true
      searchNamespace: ALL
```

Install:

```bash
helm upgrade --install monitoring \
  prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  -f monitoring/kube-prometheus-stack-values.yaml
```

Wait until all pods are `Running`:

```bash
kubectl get pods -n monitoring -w
```

### 7. Apply the ServiceMonitor

A single `ServiceMonitor` covers all three applications:

```bash
kubectl apply -f monitoring/servicemonitor.yaml
kubectl get servicemonitor -n monitoring
```

Open Prometheus and confirm targets are `UP`:

```bash
kubectl port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090 -n monitoring
```

Navigate to `http://localhost:9090` → **Status → Targets**.

### 8. Apply recording and alerting rules

```bash
kubectl apply -f monitoring/prometheus-rules.yaml
kubectl get prometheusrule -n monitoring
```

Verify in Prometheus (**Graph**):

```promql
service:http_requests:rate5m
service:http_5xx_ratio:rate5m
service:http_request_duration_p95:5m
```

Check configured alerts under **Alerts** — they should be `INACTIVE` initially:

- `ApplicationHigh5xxRate`
- `ApplicationHighLatency`
- `ApplicationTargetDown`

### 9. Install the Grafana dashboard

```bash
kubectl apply -f monitoring/grafana-dashboard-configmap.yaml
kubectl get configmap -n monitoring | grep dashboard
```

The Grafana sidecar auto-discovers the ConfigMap via the `grafana_dashboard: "1"` label.

### 10. Access Grafana

```bash
kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring
```

Get the admin password:

```bash
kubectl get secret monitoring-grafana \
  -n monitoring \
  -o jsonpath="{.data.admin-password}" | base64 -d
```

Open `http://localhost:3000`, log in as `admin`, and open **Dashboards → Browse → Application Observability**.

---

## Generating traffic and incidents

Generate baseline traffic against each service (repeat per service after port-forwarding):

```bash
kubectl port-forward svc/user-service 8001:8000 -n apps
for i in $(seq 1 500); do curl -s http://localhost:8001/ >/dev/null; done
```

### Simulate a 5xx incident

```bash
kubectl set env deployment/payment-service FAILURE_RATE=0.30 -n apps
```

Generate traffic against `payment-service`, then check `service:http_5xx_ratio:rate5m` in Prometheus. After ~2 minutes, `ApplicationHigh5xxRate` should fire.

### Simulate a latency incident

```bash
kubectl set env deployment/order-service LATENCY_SPIKE_PROBABILITY=0.80 -n apps
```

Generate traffic against `order-service`, then check `service:http_request_duration_p95:5m`. `ApplicationHighLatency` should eventually fire.

### Restore normal behavior

```bash
kubectl set env deployment/payment-service FAILURE_RATE=0.02 -n apps
kubectl set env deployment/order-service LATENCY_SPIKE_PROBABILITY=0.05 -n apps
```

---

## Design notes

- **`serviceMonitorSelectorNilUsesHelmValues: false`** lets Prometheus discover any `ServiceMonitor` in the cluster, not just ones labeled for this Helm release.
- **One `ServiceMonitor` for all three services**, using `matchExpressions` on the `app` label, rather than three separate objects — demonstrates Kubernetes label-based discovery.
- **`manual-scrape-example.yaml` is reference-only** and is never applied. It illustrates the difference between a static `scrape_configs` block and the Kubernetes-native `Service → ServiceMonitor → Prometheus Operator → Prometheus` path used here.

---

## Common commands

```bash
# Applications
kubectl get pods -n apps
kubectl get svc -n apps

# Monitoring
kubectl get pods -n monitoring
kubectl get servicemonitor -n monitoring
kubectl get prometheusrule -n monitoring

# Prometheus
kubectl port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090 -n monitoring

# Grafana
kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring

# Helm
helm list -n monitoring
```

---

## License

MIT
