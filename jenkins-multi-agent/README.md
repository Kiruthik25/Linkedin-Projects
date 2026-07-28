# 🚀 Jenkins CI/CD Pipeline with Shared Library and Multi-Agent Architecture

[![Jenkins](https://img.shields.io/badge/Jenkins-CI%2FCD-D24939?logo=jenkins&logoColor=white)](https://www.jenkins.io/)
[![Java](https://img.shields.io/badge/Java-21-orange?logo=openjdk)](https://openjdk.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Deployed-326CE5?logo=kubernetes&logoColor=white)](https://kubernetes.io/)
[![Maven](https://img.shields.io/badge/Maven-Build-C71A36?logo=apachemaven)](https://maven.apache.org/)

---

# 📖 Overview

This project demonstrates a **production-style Jenkins CI/CD pipeline** using:

- ✅ Jenkins Shared Libraries
- ✅ Multi-Agent Pipeline Execution
- ✅ SSH-based Jenkins Agents on AWS EC2
- ✅ Maven Build & Unit Testing
- ✅ Docker Image Build & Push
- ✅ Kubernetes Deployment
- ✅ Pipeline Artifact Sharing using `stash` / `unstash`

Instead of executing every stage on a single Jenkins controller, workloads are distributed across dedicated agents, making the pipeline more scalable, maintainable, and production-ready.

---

# 🏗 Architecture

```
                     GitHub Repository
                            │
                            ▼
                  Jenkins Controller
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
   Linux Agent         Docker Agent      Kubernetes Agent
  (Compile/Test)      (Build & Push)      (Deployment)
         │                  │                  │
         ▼                  ▼                  ▼
    Maven Build        Docker Hub         Kubernetes Cluster
```

---

# 📂 Repository Structure

```
.
├── Jenkinsfile
├── vars/
│   ├── buildJava.groovy
│   ├── runTests.groovy
│   ├── packageJava.groovy
│   ├── dockerBuild.groovy
│   └── deployApp.groovy
├── src/
├── deployment/
│   └── deployment.yaml
└── pom.xml
```

---

# 🚀 Pipeline Workflow

The pipeline performs the following stages:

```
Checkout Source Code
        │
        ▼
Compile Java Project
        │
        ▼
Run Unit Tests
        │
        ▼
Package Maven Artifact
        │
        ▼
Stash Build Artifact
        │
        ▼
Docker Image Build
        │
        ▼
Push Image to Docker Hub
        │
        ▼
Deploy to Kubernetes
```

---

# ⚙️ Jenkins Shared Library

## Why Shared Libraries?

A Shared Library allows reusable pipeline code to be written once and shared across multiple Jenkins pipelines.

Instead of placing all shell commands directly inside every Jenkinsfile, common tasks are abstracted into reusable functions.

### Benefits

- Reusable pipeline code
- Cleaner Jenkinsfiles
- Easier maintenance
- Consistent CI/CD implementation
- Centralized pipeline logic
- Reduced code duplication

---

## Library Declaration

```groovy
@Library('kiruthik-library') _
```

---

## Shared Library Functions

The following reusable functions are implemented inside the shared library:

| Function | Purpose |
|----------|---------|
| `buildJava()` | Compiles the Maven project |
| `runTests()` | Executes unit tests |
| `packageJava()` | Packages the application |
| `dockerBuild()` | Builds and pushes Docker images |
| `deployApp()` | Deploys the application to Kubernetes |

---

## Example

Instead of writing

```groovy
sh '''
mvn clean compile
'''
```

the Jenkinsfile simply calls

```groovy
buildJava()
```

Similarly,

```groovy
runTests()
packageJava()
dockerBuild()
deployApp()
```

This makes the Jenkinsfile responsible only for **pipeline orchestration**, while the implementation remains inside the shared library.

---

# 🤖 Multi-Agent Pipeline

The pipeline uses **multiple Jenkins agents**, each dedicated to a specific responsibility.

| Agent | Responsibility |
|--------|---------------|
| **linux-agent** | Checkout, Compile, Unit Test, Package |
| **docker-agent** | Docker Build & Push |
| **kubernets-agent** | Kubernetes Deployment |

Example:

```groovy
stage('Compile') {
    agent { label 'linux-agent' }

    steps {
        buildJava()
    }
}
```

Docker stages execute on the Docker agent:

```groovy
stage('Docker Build & Push') {

    agent {
        label 'docker-agent'
    }

    steps {
        dockerBuild(
            imageName: 'kiruthik067/maveen-demo',
            imageTag: env.BUILD_NUMBER,
            credentialsId: 'dockerhub-creds'
        )
    }
}
```

Deployment executes on the Kubernetes agent:

```groovy
stage('Deploy') {

    agent {
        label 'kubernets-agent'
    }

    steps {
        deployApp(
            manifestPath: 'deployment/deployment.yaml'
        )
    }
}
```

---

# 📦 Artifact Sharing Between Agents

Since every stage runs on different agents, the Maven artifact must be transferred between nodes.

This is accomplished using:

```groovy
stash name: 'app', includes: 'target/*.jar,Dockerfile'
```

Later, on the Docker agent:

```groovy
unstash 'app'
```

This eliminates the need to rebuild the application on another node.

---

# 🔐 Setting Up an SSH-Based Jenkins Agent on AWS EC2

## Step 1 — Launch an EC2 Instance

Create an Ubuntu instance with the following configuration:

| Property | Value |
|----------|------|
| AMI | Ubuntu 24.04 LTS |
| Instance Type | c7i-flex.large |
| Root Volume | 30 GB or more |
| SSH | Allow only from Jenkins Controller |

> **Security Recommendation**
>
> Do not expose port **8080** on the agent.
>
> Only SSH (22) should be accessible from the Jenkins controller.

---

## Step 2 — Connect to the Instance

```bash
ssh -i <your-key>.pem ubuntu@<agent-public-ip>
```

Secure the private key:

```bash
chmod 600 ~/.ssh/<your-key>.pem
```

---

## Step 3 — Configure Hostname

```bash
sudo hostnamectl set-hostname linux-agent
exec bash
```

Verify:

```bash
hostname
```

---

## Step 4 — Configure Timezone

```bash
sudo timedatectl set-timezone Asia/Kolkata
timedatectl status
```

---

## Step 5 — Install Java

```bash
sudo apt update

sudo apt install openjdk-21-jdk -y

java -version

javac -version
```

---

## Step 6 — Create Jenkins User

```bash
sudo useradd -m -s /bin/bash jenkins
```

---

# 🔑 Configure SSH Authentication

## Generate SSH Key on Jenkins Controller

Switch to Jenkins user:

```bash
sudo su - jenkins
```

Generate key:

```bash
ssh-keygen \
-t ed25519 \
-f /var/lib/jenkins/.ssh/jenkins-agent-key \
-C "jenkins-agent-access"
```

Files created:

```
Private Key

/var/lib/jenkins/.ssh/jenkins-agent-key
```

```
Public Key

/var/lib/jenkins/.ssh/jenkins-agent-key.pub
```

Display the public key:

```bash
cat ~/.ssh/jenkins-agent-key.pub
```

---

## Copy Public Key to Agent

On the agent:

```bash
sudo su - jenkins

mkdir -p ~/.ssh

vim ~/.ssh/authorized_keys
```

Paste the public key.

Set permissions:

```bash
chmod 700 ~/.ssh

chmod 600 ~/.ssh/authorized_keys
```

---

## Verify SSH Connectivity

Run from the controller:

```bash
sudo su - jenkins

ssh \
-i /var/lib/jenkins/.ssh/jenkins-agent-key \
jenkins@<agent-ip> hostname
```

Expected output:

```
linux-agent
```

---

# 🖥 Configure Jenkins Agent

Navigate to:

```
Manage Jenkins

↓

Nodes

↓

New Node
```

Configuration:

| Setting | Value |
|---------|------|
| Node Type | Permanent Agent |
| Remote Root Directory | /home/jenkins |
| Launch Method | Launch Agents via SSH |
| SSH Username | jenkins |
| Labels | docker-maven-trivy |
| Usage | Use this node as much as possible |

---

## SSH Credentials

Create a new credential:

```
Kind:
SSH Username with Private Key
```

Username

```
jenkins
```

Private Key

Paste:

```
/var/lib/jenkins/.ssh/jenkins-agent-key
```

---

# Host Key Verification

Recommended:

```
Known Hosts Verification Strategy
```

Populate the known hosts file:

```bash
sudo -u jenkins ssh \
-i /var/lib/jenkins/.ssh/jenkins-agent-key \
jenkins@<agent-ip> hostname
```

Or:

```bash
ssh-keyscan <agent-ip> | sudo -u jenkins tee -a /var/lib/jenkins/.ssh/known_hosts
```

---

# Launch the Agent

Click:

```
Save

↓

Launch Agent
```

Expected status:

```
✔ Agent Successfully Connected

✔ Online
```

---

# Pipeline Highlights

✔ Shared Library Architecture

✔ Multi-Agent Execution

✔ Maven Build Automation

✔ Docker Image Build & Push

✔ Kubernetes Deployment

✔ Artifact Transfer Using Stash/Unstash

✔ Modular Jenkins Pipeline

✔ SSH-Based Secure Agent Connectivity

---

# Technologies Used

- Jenkins
- Jenkins Shared Library
- Jenkins SSH Agents
- Java 21
- Maven
- Docker
- Docker Hub
- Kubernetes
- GitHub
- AWS EC2
- Ubuntu 24.04

---

# Key Takeaways

- Centralized reusable pipeline logic using **Jenkins Shared Libraries**
- Distributed workload across **multiple Jenkins agents**
- Secure SSH-based communication between Jenkins controller and agents
- Efficient artifact transfer using **stash/unstash**
- Production-ready CI/CD workflow with Docker and Kubernetes deployment
- Clean, modular, and maintainable Jenkins pipelines
