pipeline {
    options {
        timeout(time: 10, unit: 'MINUTES')
    }
    
    agent {
        kubernetes {
            yaml '''
apiVersion: v1
kind: Pod
spec:
  containers:
    - image: "jenkinsci/jnlp-slave"
      name: "jnlp"
      resources:
        requests:
          memory: "200Mi"
          cpu: "0.5"
'''
        }
    }
    stages {
        stage('check') {
            parallel {
                stage('pull code') {
                    steps {
                        container('jnlp') {
                            timestamps {
                                checkout([$class: 'GitSCM', branches: [[name: '*/master']], extensions: [], userRemoteConfigs: [[credentialsId: 'kyligence-git', url: 'https://github.com/Kyligence/devopslib.git']]])
                            }
                        }
                    }
                }
                stage(' nexus') {
                    steps {
                        container('jnlp') {
                            timestamps {
                                sh '''
                                for i in `seq 2`;do
                                curl -I http://repo-ofs.kyligence.com
                                sleep 2
                                done
                                '''
                            }
                        }
                    }
                }
            }
        }
    }
}
