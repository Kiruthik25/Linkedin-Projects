# 📧 Jenkins Email Notification Setup Guide

This guide walks you through configuring **Email Notifications** in Jenkins using the **Email Extension Plugin (email-ext)**. By the end of this guide, Jenkins will be able to send email notifications automatically whenever a pipeline succeeds, fails, becomes unstable, or completes.

---

# Table of Contents

- [Prerequisites](#prerequisites)
- [Step 1: Install Required Plugins](#step-1-install-required-plugins)
- [Step 2: Generate a Gmail App Password](#step-2-generate-a-gmail-app-password)
- [Step 3: Configure System Admin Email Address](#step-3-configure-system-admin-email-address)
- [Step 4: Configure SMTP Settings](#step-4-configure-smtp-settings)
- [Step 5: Configure Extended Email Notification](#step-5-configure-extended-email-notification)
- [Step 6: Test Email Configuration](#step-6-test-email-configuration)
- [Step 7: Configure Email Notifications in a Pipeline](#step-7-configure-email-notifications-in-a-pipeline)
- [Step 8: Send Email for Every Build](#step-8-send-email-for-every-build)
- [Step 9: Send Email to Multiple Recipients](#step-9-send-email-to-multiple-recipients)
- [Step 10: Attach Console Logs](#step-10-attach-console-logs)
- [Step 11: Attach Build Artifacts](#step-11-attach-build-artifacts)
- [Step 12: Use Recipient Providers](#step-12-use-recipient-providers)
- [Useful Jenkins Environment Variables](#useful-jenkins-environment-variables)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

---

# Prerequisites

Before configuring email notifications, ensure you have:

- Jenkins installed and running
- Internet connectivity from the Jenkins server
- A valid email account (Gmail, Outlook, Office365, etc.)
- A Gmail **App Password** (recommended) instead of your regular Gmail password
- Administrator access to Jenkins

---

# Step 1: Install Required Plugins

Navigate to:

```
Manage Jenkins
    └── Plugins
```

Install the following plugins:

- ✅ Email Extension Plugin
- ✅ Mailer Plugin (usually installed by default)

Restart Jenkins after installation.

---

# Step 2: Generate a Gmail App Password

> **Note**
>
> Google no longer allows third-party applications to authenticate using your Gmail password.
>
> You must use an **App Password**.

## Enable Two-Factor Authentication

Open:

```
Google Account
    └── Security
          └── 2-Step Verification
```

Enable **2-Step Verification**.

---

## Generate an App Password

Navigate to:

```
Google Account
    └── Security
          └── App Passwords
```

Choose:

```
App: Mail

Device:
Other (Custom Name)

Example:
Jenkins
```

Google generates a 16-character password similar to:

```
abcd efgh ijkl mnop
```

Save this password.

You'll use it later in Jenkins.

---

# Step 3: Configure System Admin Email Address

Navigate to:

```
Manage Jenkins
        ↓
System
```

Locate:

```
System Admin e-mail address
```

Set it to the same email account that Jenkins uses for SMTP.

Example:

```
your-email@gmail.com
```

> **Important**
>
> If this field is left blank, Jenkins may send emails using:
>
> ```
> nobody@nowhere
> ```
>
> which Gmail rejects with:
>
> ```
> 530 Authentication Required
> ```

---

# Step 4: Configure SMTP Settings

Navigate to:

```
Manage Jenkins
        ↓
System
        ↓
E-mail Notification
```

Configure the following settings:

| Setting | Value |
|---------|-------|
| SMTP Server | smtp.gmail.com |
| SMTP Authentication | Enabled |
| Username | your-email@gmail.com |
| Password | Gmail App Password |
| Use SSL | Enabled |
| SMTP Port | 465 |

Example:

```
SMTP Server:
smtp.gmail.com

Username:
your-email@gmail.com

Password:
****************

SMTP Port:
465
```

---

# Step 5: Configure Extended Email Notification

Still under:

```
Manage Jenkins
        ↓
System
        ↓
Extended E-mail Notification
```

Configure the following:

| Setting | Value |
|---------|-------|
| SMTP Server | smtp.gmail.com |
| SMTP Port | 465 |
| SMTP Authentication | Enabled |
| Username | your-email@gmail.com |
| Password | Gmail App Password |
| Use SSL | Enabled |
| Default Content Type | text/html |
| Default Recipients | your-email@gmail.com |
| Default Subject | Build: $PROJECT_NAME - #$BUILD_NUMBER |
| Default From | your-email@gmail.com |

---

## Example Default Content

```html
<h2>Jenkins Build Notification</h2>

<b>Project:</b> $PROJECT_NAME

<b>Build Number:</b> $BUILD_NUMBER

<b>Status:</b> $BUILD_STATUS

<b>Triggered By:</b> $CAUSE

<b>Build URL:</b>

$BUILD_URL
```

---

# Step 6: Test Email Configuration

Click:

```
Test configuration by sending test e-mail
```

Enter:

```
your-email@gmail.com
```

Click:

```
Test configuration
```

If successful:

```
Email was successfully sent.
```

---

# Step 7: Configure Email Notifications in a Pipeline

```groovy
pipeline {

    agent any

    stages {

        stage('Build') {
            steps {
                sh 'echo Hello'
            }
        }

    }

    post {

        success {

            emailext(
                subject: "SUCCESS: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                body: """
                <h2>Build Successful</h2>

                Project:
                ${env.JOB_NAME}

                Build:
                ${env.BUILD_NUMBER}

                Build URL:
                ${env.BUILD_URL}
                """,
                to: 'your-email@gmail.com'
            )
        }

        failure {

            emailext(
                subject: "FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                body: """
                <h2>Build Failed</h2>

                Please check:

                ${env.BUILD_URL}
                """,
                to: 'your-email@gmail.com'
            )
        }
    }
}
```

---

# Step 8: Send Email for Every Build

```groovy
post {

    always {

        emailext(

            subject: "${currentBuild.currentResult}: ${env.JOB_NAME}",

            body: """
            Result:
            ${currentBuild.currentResult}

            Build URL:
            ${env.BUILD_URL}
            """,

            to: "your-email@gmail.com"
        )

    }

}
```

---

# Step 9: Send Email to Multiple Recipients

```groovy
emailext(

    subject: "Build Result",

    body: "Please check Jenkins.",

    to: "dev1@gmail.com,dev2@gmail.com,manager@gmail.com"

)
```

---

# Step 10: Attach Console Logs

```groovy
emailext(

    subject: "Build Failed",

    body: "Console log attached.",

    attachLog: true,

    compressLog: true,

    to: "your-email@gmail.com"

)
```

---

# Step 11: Attach Build Artifacts

```groovy
emailext(

    attachmentsPattern: "target/*.jar",

    subject: "Artifact",

    body: "Jar file attached.",

    to: "your-email@gmail.com"

)
```

---

# Step 12: Use Recipient Providers

Instead of hardcoding recipients, Jenkins can automatically send emails to developers involved in the build.

```groovy
emailext(
    subject: "Build Status",
    body: "Please check the build results.",
    recipientProviders: [
        developers(),
        requestor(),
        culprits()
    ]
)
```

Recipient providers:

- **developers()** → Developers who committed code
- **requestor()** → User who triggered the build
- **culprits()** → Developers responsible for the failing build

---

# Useful Jenkins Environment Variables

| Variable | Description |
|-----------|-------------|
| `${JOB_NAME}` | Job name |
| `${BUILD_NUMBER}` | Current build number |
| `${BUILD_ID}` | Build ID |
| `${BUILD_URL}` | Build URL |
| `${JENKINS_URL}` | Jenkins URL |
| `${NODE_NAME}` | Agent or controller name |
| `${WORKSPACE}` | Workspace directory |
| `${BUILD_TAG}` | Build tag |
| `${EXECUTOR_NUMBER}` | Executor number |
| `${GIT_BRANCH}` | Git branch |
| `${GIT_COMMIT}` | Git commit hash |

---

# Troubleshooting

## Authentication Failed

**Error**

```
Authentication failed
```

### Solution

- Use a Gmail App Password
- Do not use your Gmail account password
- Verify SMTP Authentication is enabled
- Ensure the username is your full email address

---

## Authentication Required

**Error**

```
530 Authentication Required
```

### Solution

This usually indicates one of the following:

- SMTP Authentication is disabled
- Gmail App Password is incorrect
- System Admin e-mail address is blank
- Default From address is not configured

---

## Connection Timed Out

**Error**

```
Connection timed out
```

### Solution

- Verify internet connectivity from the Jenkins server
- Ensure firewall rules allow outbound SMTP traffic
- Verify ports **465** or **587** are open

---

## Unknown Host

**Error**

```
Unknown host smtp.gmail.com
```

### Solution

- Verify DNS resolution
- Confirm internet connectivity

---

## SSL Handshake Error

**Error**

```
SSLHandshakeException
```

### Solution

Use the correct SMTP configuration:

| Encryption | Port |
|------------|------|
| SSL | 465 |
| TLS | 587 |

---

## Emails Not Sent During Pipeline

If the **Test Configuration** succeeds but pipeline emails fail:

Check the following:

- SMTP Authentication is enabled
- System Admin e-mail address is configured
- Default From address is configured
- Gmail App Password is being used
- Email Extension Plugin is properly configured

If your logs show:

```
MAIL FROM:<nobody@nowhere>
```

or

```
useAuth false
```

it means Jenkins is not using SMTP authentication correctly.

---

# Best Practices

- Store SMTP credentials securely using **Jenkins Credentials** whenever possible.
- Always use **Gmail App Passwords** instead of regular account passwords.
- Configure both **E-mail Notification** and **Extended E-mail Notification**.
- Set the **System Admin e-mail address** to a valid sender email.
- Configure the **Default From** address to match the SMTP account.
- Use the **Email Extension Plugin (`emailext`)** for advanced notifications.
- Include build status, build URL, job name, and build number in email notifications.
- Use the `post` section of your Jenkins pipeline to ensure notifications are sent after every build.
- Test the SMTP configuration before integrating email notifications into production pipelines.

---

## 🎉 Conclusion

You have now configured Jenkins to send automated email notifications for your CI/CD pipelines. By using the **Email Extension Plugin**, Gmail App Passwords, and proper SMTP authentication, you can notify developers and stakeholders about build results, deployment status, and pipeline failures efficiently.
