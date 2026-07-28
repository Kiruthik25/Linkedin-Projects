// def call(Map config = [:]) {

//     copyArtifacts(
//         projectName: config.projectName ?: env.JOB_NAME,
//         selector: config.selector ?: lastSuccessful(),
//         fingerprintArtifacts: true
//     )
// }

def call(Map config = [:]) {

    step([
        $class: 'CopyArtifact',
        projectName: config.projectName ?: env.JOB_NAME,
        selector: [$class: 'StatusBuildSelector', stable: false],
        fingerprintArtifacts: true
    ])
}
