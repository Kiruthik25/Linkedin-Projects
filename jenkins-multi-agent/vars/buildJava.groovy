def call() {
    sh '''
        echo "Compiling Java project..."
        mvn -B clean compile
    '''
}
