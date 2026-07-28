def call(Map config = [:]) {

    def recipients = config.to ?: 'devops-team@example.com'
    def status      = config.status ?: currentBuild.currentResult
    def subject     = "Jenkins Build ${status}: ${env.JOB_NAME} #${env.BUILD_NUMBER}"
    def body        = """
        <p>Build <b>${env.JOB_NAME} #${env.BUILD_NUMBER}</b> finished with status: <b>${status}</b></p>
        <p>Check console output: <a href="${env.BUILD_URL}">${env.BUILD_URL}</a></p>
    """

    emailext(
        to: recipients,
        subject: subject,
        body: body,
        mimeType: 'text/html'
    )
}
