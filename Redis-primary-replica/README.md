# Redis Primary–Replica Replication and Load Testing

A hands-on project to understand Redis replication, Docker networking, protected mode, load testing, monitoring, and debugging.

![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)
![Status](https://img.shields.io/badge/status-hands--on%20lab-brightgreen)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Setup Guide](#setup-guide)
  - [Step 1: Redis Primary Configuration](#step-1-create-redis-primary-configuration)
  - [Step 2: Redis Replica Configuration](#step-2-create-redis-replica-configuration)
  - [Step 3: Docker Compose File](#step-3-create-docker-compose-file)
  - [Step 4: Start the Environment](#step-4-start-the-environment)
  - [Step 5: Verify Docker Networking](#step-5-verify-docker-networking)
  - [Step 6: Verify Replication](#step-6-verify-replication)
  - [Step 7: Manually Configure Replication](#step-7-manually-configure-replication)
  - [Step 8: Test Data Replication](#step-8-test-data-replication)
  - [Step 9: Verify Replica Is Read-Only](#step-9-verify-replica-is-read-only)
  - [Step 10: Generate Test Data](#step-10-generate-test-data)
  - [Step 11: Load Test on Primary](#step-11-run-load-test-on-primary)
  - [Step 12: Load Test on Replica](#step-12-run-load-test-on-replica)
  - [Step 13: Mixed Workload Test](#step-13-mixed-workload-test)
- [Monitoring Redis](#monitoring-redis)
- [Troubleshooting Guide](#troubleshooting-guide)
- [RedisInsight Setup](#redisinsight-setup)
- [Experiment Flow](#experiment-flow)
- [Key Learnings](#key-learnings)
- [Cleanup](#cleanup)
- [Project Summary](#project-summary)
- [Final Architecture](#final-architecture)
- [Future Improvements](#future-improvements)
- [Repository Info](#repository-info)

---

## Overview

This project builds a Redis architecture with:

- 1 Redis Primary
- 1 Redis Replica
- Docker Compose
- Redis CLI
- RedisInsight
- `redis-benchmark` for load testing

The main goal is to understand:

- How Redis replication works
- How a replica connects to a primary
- How to verify replication
- How protected mode can block container-to-container communication
- How to generate read and write load
- How to monitor important Redis metrics
- How read traffic can be moved from a primary to a replica

---

## Architecture

```
                         WRITE
                           │
                           ▼
                    ┌──────────────┐
                    │ REDIS PRIMARY│
                    │   Port 6379  │
                    └──────┬───────┘
                           │
                           │ Replication
                           ▼
                    ┌──────────────┐
                    │ REDIS REPLICA│
                    │   Port 6380  │
                    └──────┬───────┘
                           ▲
                           │
                          READ
```

---

## Prerequisites

Install the following:

- Docker
- Docker Compose
- RedisInsight (optional)

Verify Docker:

```bash
docker --version
```

Verify Docker Compose:

```bash
docker compose version
```

---

## Project Structure

Create the project:

```bash
mkdir redis-replication-demo
cd redis-replication-demo
```

Create the following files:

```
redis-replication-demo/
│
├── docker-compose.yml
│
└── redis/
    ├── primary.conf
    └── replica.conf
```

Create the directory:

```bash
mkdir redis
```

---

## Setup Guide

### Step 1: Create Redis Primary Configuration

Create:

```bash
nano redis/primary.conf
```

Add:

```conf
port 6379

bind 0.0.0.0
protected-mode no

appendonly yes

maxmemory 512mb
maxmemory-policy allkeys-lru
```

**Important settings**

- `bind 0.0.0.0` — Allows Redis to listen on all network interfaces.
- `protected-mode no` — Allows the Redis replica container to connect to the primary in this local Docker lab.

> ⚠️ **Warning:** Do not expose a Redis server publicly with `protected-mode no` unless proper authentication and network security are configured.

### Step 2: Create Redis Replica Configuration

Create:

```bash
nano redis/replica.conf
```

Add:

```conf
port 6379

bind 0.0.0.0
protected-mode no

replicaof redis-primary 6379

appendonly yes

maxmemory 512mb
maxmemory-policy allkeys-lru
```

The important line is:

```conf
replicaof redis-primary 6379
```

This tells the replica to connect to:

- **Host:** `redis-primary`
- **Port:** `6379`

Docker Compose automatically provides DNS resolution between containers using service/container names on the same network.

### Step 3: Create Docker Compose File

Create:

```bash
nano docker-compose.yml
```

Add:

```yaml
services:

  redis-primary:
    image: redis/redis-stack-server:latest
    container_name: redis-primary
    ports:
      - "6379:6379"
    volumes:
      - ./redis/primary.conf:/redis-stack.conf
    command: redis-server /redis-stack.conf

  redis-replica:
    image: redis/redis-stack-server:latest
    container_name: redis-replica
    ports:
      - "6380:6379"
    volumes:
      - ./redis/replica.conf:/redis-stack.conf
    depends_on:
      - redis-primary
    command: redis-server /redis-stack.conf
```

### Step 4: Start the Environment

Start Redis:

```bash
docker compose up -d
```

Check containers:

```bash
docker ps
```

Expected:

```
redis-primary
redis-replica
```

Check that both Redis servers respond:

```bash
docker exec redis-primary redis-cli PING
```

Expected: `PONG`

Check replica:

```bash
docker exec redis-replica redis-cli PING
```

Expected: `PONG`

### Step 5: Verify Docker Networking

Test whether the replica can reach the primary:

```bash
docker exec redis-replica redis-cli -h redis-primary -p 6379 PING
```

Expected: `PONG`

This confirms:

```
redis-replica
      │
      │ Docker Network
      ▼
redis-primary:6379
      │
      ▼
     PONG
```

### Step 6: Verify Replication

Check the primary:

```bash
docker exec redis-primary redis-cli INFO replication
```

Expected:

```
role:master
connected_slaves:1
```

> Depending on the Redis version, the naming may use `connected_replicas`.

Check the replica:

```bash
docker exec redis-replica redis-cli INFO replication
```

Expected:

```
role:slave
master_host:redis-primary
master_port:6379
master_link_status:up
```

The important value is: `master_link_status:up`

### Step 7: Manually Configure Replication

If replication is not working automatically, configure it manually.

Run:

```bash
docker exec redis-replica redis-cli REPLICAOF redis-primary 6379
```

Expected: `OK`

Wait:

```bash
sleep 5
```

Check again:

```bash
docker exec redis-replica redis-cli INFO replication
```

Expected:

```
role:slave
master_link_status:up
```

Check the primary:

```bash
docker exec redis-primary redis-cli INFO replication
```

Expected:

```
role:master
connected_slaves:1
```

### Step 8: Test Data Replication

Write data to the primary:

```bash
docker exec redis-primary redis-cli SET user:1 "Redis Demo"
```

Expected: `OK`

Read from the primary:

```bash
docker exec redis-primary redis-cli GET user:1
```

Expected: `Redis Demo`

Now read from the replica:

```bash
docker exec redis-replica redis-cli GET user:1
```

Expected: `Redis Demo`

Data flow:

```
SET user:1
     │
     ▼
PRIMARY
     │
     │ Replication
     ▼
REPLICA
     │
     ▼
GET user:1
```

### Step 9: Verify Replica Is Read-Only

Try writing directly to the replica:

```bash
docker exec redis-replica redis-cli SET test:key "hello"
```

Expected behavior:

```
READONLY You can't write against a read only replica
```

Write to the primary instead:

```bash
docker exec redis-primary redis-cli SET test:key "hello"
```

Then read from the replica:

```bash
docker exec redis-replica redis-cli GET test:key
```

Expected: `hello`

### Step 10: Generate Test Data

Before running GET benchmarks, create data.

Run SET benchmark:

```bash
docker exec redis-primary redis-benchmark \
  -t set \
  -n 100000 \
  -c 50
```

**Parameters:**

| Flag | Meaning |
|------|---------|
| `-t set` | Run only SET operations |
| `-n 100000` | Total number of requests |
| `-c 50` | Use 50 concurrent clients |

### Step 11: Run Load Test on Primary

Run a GET benchmark against the primary:

```bash
docker exec redis-primary redis-benchmark \
  -t get \
  -n 1000000 \
  -c 100
```

Architecture:

```
100 Clients
     │
     ▼
GET Requests
     │
     ▼
REDIS PRIMARY
```

This simulates a scenario where the primary handles read traffic.

### Step 12: Run Load Test on Replica

Now send the read workload to the replica:

```bash
docker exec redis-replica redis-benchmark \
  -t get \
  -n 1000000 \
  -c 100
```

Architecture:

```
                 WRITES
                    │
                    ▼
                 PRIMARY
                    │
               Replication
                    │
                    ▼
                 REPLICA
                    ▲
                    │
                  READS
```

**The important lesson:** Redis replication does not automatically move reads to replicas. The application must intentionally send read requests to the replica.

### Step 13: Mixed Workload Test

Run write traffic against the primary:

```bash
docker exec redis-primary redis-benchmark \
  -t set \
  -n 5000000 \
  -c 50
```

At the same time, open another terminal and run read traffic against the replica:

```bash
docker exec redis-replica redis-benchmark \
  -t get \
  -n 5000000 \
  -c 100
```

Architecture:

```
                       WRITE
                         │
                         ▼
                  ┌─────────────┐
                  │   PRIMARY   │
                  └──────┬──────┘
                         │
                     Replication
                         │
                         ▼
                  ┌─────────────┐
READ ◄────────────│   REPLICA   │
                  └─────────────┘
```

---

## Monitoring Redis

The most important metrics for this project are:

1. Ops/sec
2. Connected Clients
3. Replication Status
4. Memory Usage
5. Latency

### Check Operations Per Second

Primary:

```bash
docker exec redis-primary redis-cli INFO stats | grep instantaneous_ops_per_sec
```

Replica:

```bash
docker exec redis-replica redis-cli INFO stats | grep instantaneous_ops_per_sec
```

Example:

```
instantaneous_ops_per_sec:50000
```

### Check Connected Clients

Primary:

```bash
docker exec redis-primary redis-cli INFO clients | grep connected_clients
```

Replica:

```bash
docker exec redis-replica redis-cli INFO clients | grep connected_clients
```

Example:

```
connected_clients:100
```

### Check Replication Status

Primary:

```bash
docker exec redis-primary redis-cli INFO replication
```

Look for:

```
role:master
connected_slaves:1
```

Replica:

```bash
docker exec redis-replica redis-cli INFO replication
```

Look for:

```
role:slave
master_link_status:up
```

### Check Memory Usage

Primary:

```bash
docker exec redis-primary redis-cli INFO memory
```

Important fields: `used_memory_human`, `used_memory_peak_human`, `mem_fragmentation_ratio`

Quick command:

```bash
docker exec redis-primary redis-cli INFO memory | grep -E "used_memory_human|used_memory_peak_human|mem_fragmentation_ratio"
```

### Monitor Latency

Primary:

```bash
docker exec redis-primary redis-cli --latency -i 1
```

Replica:

```bash
docker exec redis-replica redis-cli --latency -i 1
```

Stop with `Ctrl + C`.

### Monitor Metrics Continuously

Primary Ops/sec:

```bash
watch -n 1 'docker exec redis-primary redis-cli INFO stats | grep instantaneous_ops_per_sec'
```

Replica Ops/sec:

```bash
watch -n 1 'docker exec redis-replica redis-cli INFO stats | grep instantaneous_ops_per_sec'
```

Primary clients:

```bash
watch -n 1 'docker exec redis-primary redis-cli INFO clients | grep connected_clients'
```

Replica clients:

```bash
watch -n 1 'docker exec redis-replica redis-cli INFO clients | grep connected_clients'
```

### Get Primary and Replica Metrics Together

```bash
echo "===== REDIS PRIMARY =====" && \
echo "Ops/sec: $(docker exec redis-primary redis-cli INFO stats | grep instantaneous_ops_per_sec | cut -d: -f2)" && \
echo "Connected Clients: $(docker exec redis-primary redis-cli INFO clients | grep connected_clients | cut -d: -f2)" && \
echo "Replication: $(docker exec redis-primary redis-cli INFO replication | grep connected_slaves | cut -d: -f2)" && \
echo "" && \
echo "===== REDIS REPLICA =====" && \
echo "Ops/sec: $(docker exec redis-replica redis-cli INFO stats | grep instantaneous_ops_per_sec | cut -d: -f2)" && \
echo "Connected Clients: $(docker exec redis-replica redis-cli INFO clients | grep connected_clients | cut -d: -f2)" && \
echo "Replication: $(docker exec redis-replica redis-cli INFO replication | grep master_link_status | cut -d: -f2)"
```

Example output:

```
===== REDIS PRIMARY =====
Ops/sec: 150
Connected Clients: 2
Replication: 1

===== REDIS REPLICA =====
Ops/sec: 50000
Connected Clients: 100
Replication: up
```

---

## Troubleshooting Guide

### Problem 1: Replica is not connected

Primary:

```
role:master
connected_slaves:0
```

Replica:

```
role:slave
master_link_status:down
```

**Check connectivity:**

```bash
docker exec redis-replica redis-cli -h redis-primary -p 6379 PING
```

Expected: `PONG`

### Problem 2: Redis Protected Mode Error

You may see:

```
DENIED Redis is running in protected mode
```

For this local Docker lab, configure:

```conf
protected-mode no
```

Also ensure:

```conf
bind 0.0.0.0
```

Then recreate the environment:

```bash
docker compose down
docker compose up -d
```

Verify:

```bash
docker exec redis-replica redis-cli -h redis-primary -p 6379 PING
```

Expected: `PONG`

> ⚠️ This configuration is for a local learning environment. Production Redis deployments should use authentication/ACLs and network restrictions.

### Problem 3: Replica Cannot Resolve Primary Host

Test:

```bash
docker exec redis-replica getent hosts redis-primary
```

If both containers are managed by the same Compose project, they should share a Docker network.

Check networks:

```bash
docker inspect redis-primary --format '{{json .NetworkSettings.Networks}}'
docker inspect redis-replica --format '{{json .NetworkSettings.Networks}}'
```

Both containers should have a common network.

### Problem 4: Check Redis Logs

Primary logs:

```bash
docker logs redis-primary --tail 50
```

Replica logs:

```bash
docker logs redis-replica --tail 50
```

For live logs:

```bash
docker logs -f redis-replica
```

Look for: `MASTER`, `SYNC`, `connection`, `error`, `refused`

---

## RedisInsight Setup

If you use RedisInsight, add two database connections.

**Primary**

- Host: `localhost`
- Port: `6379`
- Name: `Redis Primary`

**Replica**

- Host: `localhost`
- Port: `6380`
- Name: `Redis Replica`

This allows you to inspect both Redis instances separately.

Useful commands in RedisInsight or `redis-cli`:

```
INFO stats
INFO clients
INFO memory
INFO replication
INFO persistence
INFO keyspace
DBSIZE
SLOWLOG GET 10
```

---

## Experiment Flow

### Experiment 1: Single Primary Read Load

```
100 Clients
     │
     ▼
 GET Load
     │
     ▼
 PRIMARY
```

Run:

```bash
docker exec redis-primary redis-benchmark \
  -t get \
  -n 1000000 \
  -c 100
```

Record: Ops/sec, Connected Clients, Latency, Memory

### Experiment 2: Read Load on Replica

```
                 PRIMARY
                    │
                Replication
                    │
                    ▼
100 Clients ───► REPLICA
```

Run:

```bash
docker exec redis-replica redis-benchmark \
  -t get \
  -n 1000000 \
  -c 100
```

Compare:

| Metric | Primary | Replica |
|--------|---------|---------|
| Ops/sec | Record result | Record result |
| Connected Clients | Record result | Record result |
| Latency | Record result | Record result |
| Replication | Connected | Up |

> Use your actual results rather than hardcoding benchmark numbers.

---

## Key Learnings

### Redis replication is asynchronous

Data written to the primary is replicated to replicas asynchronously.

```
Client
   │
   │ SET
   ▼
Primary
   │
   │ Replication
   ▼
Replica
```

This means replicas can have temporary replication lag.

### Replication does not automatically load balance

Simply adding a replica does not automatically reduce load on the primary.

This:

```
Application
     │
     ▼
Primary
```

will continue sending all requests to the primary unless the application explicitly uses the replica.

To distribute read traffic:

```
                 Writes
                    │
                    ▼
                 Primary
                    │
                Replication
                    │
                    ▼
Application ─────► Replica
                   Reads
```

### Replicas are useful for read-heavy workloads

A common pattern is:

```
WRITE → PRIMARY
READ  → REPLICA
```

This can reduce the read workload handled by the primary when the application architecture supports read splitting.

---

## Cleanup

Stop containers:

```bash
docker compose down
```

Stop and remove containers, networks, and volumes:

```bash
docker compose down -v
```

Check:

```bash
docker ps -a
```

---

## Project Summary

This project demonstrates:

- Running Redis in Docker
- Configuring a Redis Primary
- Configuring a Redis Replica
- Docker container networking
- Redis protected mode troubleshooting
- Verifying replication
- Testing replicated data
- Read-only replica behavior
- Load testing with `redis-benchmark`
- Monitoring Redis performance
- Comparing primary and replica workloads
- Understanding read/write splitting

---

## Final Architecture

```
                         ┌───────────┐
                         │  CLIENT   │
                         └─────┬─────┘
                               │
                  ┌────────────┴────────────┐
                  │                         │
                WRITE                      READ
                  │                         │
                  ▼                         ▼
           ┌─────────────┐           ┌─────────────┐
           │   PRIMARY   │──────────►│   REPLICA   │
           │   :6379     │ Replicate │   :6380     │
           └─────────────┘           └─────────────┘
```

---

## Future Improvements

Possible next steps:

- Add multiple replicas
- Measure replication lag
- Test replica failure
- Add Redis Sentinel
- Test automatic failover
- Explore Redis Cluster
- Test sharding
- Compare single-node and distributed Redis performance
- Add application-level read/write splitting
- Add Grafana and Prometheus monitoring

---

## Repository Info

**Suggested repository name:**

```
redis-primary-replica-load-testing
```

**Suggested description:**

> Hands-on Redis project demonstrating primary-replica replication, Docker networking, protected mode troubleshooting, load testing, and real-time monitoring.
