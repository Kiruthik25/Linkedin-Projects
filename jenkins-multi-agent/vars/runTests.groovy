def call() {
    sh '''
        echo "Running unit tests..."
        mvn -B test
    '''

    // Publish JUnit test results
    junit testResults: 'target/surefire-reports/*.xml', allowEmptyResults: true

    // Publish Jacoco coverage report, if the plugin generated one
    script {
        if (fileExists('target/site/jacoco/index.html')) {
            publishHTML(target: [
                reportDir            : 'target/site/jacoco',
                reportFiles          : 'index.html',
                reportName           : 'Jacoco Coverage Report',
                keepAll              : true,
                alwaysLinkToLastBuild: true,
                allowMissing         : true
            ])
        }
    }
}
