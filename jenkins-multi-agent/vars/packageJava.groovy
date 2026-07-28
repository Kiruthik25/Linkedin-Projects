def call() {
    sh '''
        echo "Packaging Java application..."
        mvn -B package -DskipTests
    '''

    archiveArtifacts artifacts: 'target/*.jar', fingerprint: true
}
