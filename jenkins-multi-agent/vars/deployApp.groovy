// def call(Map config = [:]) {

//     def manifestPath = config.manifestPath ?: 'deployment/deployment.yaml'
//     def kubeCredentialsId = config.kubeCredentialsId ?: 'kubeconfig-creds'

//     withCredentials([file(credentialsId: kubeCredentialsId, variable: 'KUBECONFIG')]) {
//         sh """
//             echo "Deploying application to Kubernetes..."
//             kubectl apply -f ${manifestPath}
//             kubectl rollout status deployment/cvwj-devsecops-demo --timeout=120s
//         """
//     }
// }


def call(Map config = [:]) {

    def manifestPath = config.manifestPath ?: 'deployment/deployment.yaml'

    // Assumes the EC2 agent already has a working kubeconfig
    // (e.g. ~/.kube/config set up manually on the box, pointing at the cluster).
    sh """
        echo "Deploying application to Kubernetes..."
        kubectl apply -f ${manifestPath}
        kubectl rollout status deployment/maven-app-demo --timeout=120s
    """
}
