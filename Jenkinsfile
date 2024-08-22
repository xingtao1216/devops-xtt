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
                                checkout([$class: 'GitSCM', branches: [[name: '*/xtt-devops']], extensions: [], userRemoteConfigs: [[credentialsId: 'devops-xtttest', url: 'https://github.com/xingtao1216/devops-xtt.git']]])
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
