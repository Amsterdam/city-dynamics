#!groovy

def tryStep(String message, Closure block, Closure tearDown = null) {
    try {
        block();
    }
    catch (Throwable t) {
        slackSend message: "${env.JOB_NAME}: ${message} failure ${env.BUILD_URL}", channel: '#ci-channel', color: 'danger'

        throw t;
    }
    finally {
        if (tearDown) {
            tearDown();
        }
    }
}


node {

    stage("Checkout") {
        checkout scm
    }

#    stage("Test") {
#        tryStep "Test", {
#            sh "docker-compose -p test -f -f /web/deploy/test/docker-compose.yml up tests"
#	}, {
#            sh "docker-compose -p test -f -f /web/deploy/test/docker-compose.yml down"
#        }
#    }

    stage("Build dockers") {
        tryStep "build", {
            def kibana = docker.build("build.datapunt.amsterdam.nl:5000/datapunt/city_dynamics_importer:${env.BUILD_NUMBER}", "importer")
            kibana.push()
            kibana.push("acceptance")

	    def logstash = docker.build("build.datapunt.amsterdam.nl:5000/datapunt/city_dynamics_analyzer:${env.BUILD_NUMBER}", "analyzer")
            logstash.push()
            logstash.push("acceptance")

            def csvimporter = docker.build("build.datapunt.amsterdam.nl:5000/datapunt/city_dynamics:${env.BUILD_NUMBER}", "web")
            csvimporter.push()
            csvimporter.push("acceptance")
        }
    }
}

String BRANCH = "${env.BRANCH_NAME}"

if (BRANCH == "master") {

    node {
        stage('Push acceptance image') {
            tryStep "image tagging", {
                def image = docker.image("build.datapunt.amsterdam.nl:5000/datapunt/city_dynamics:${env.BUILD_NUMBER}")
                image.pull()
                image.push("acceptance")
            }
        }
    }

    node {
        stage("Deploy to ACC") {
            tryStep "deployment", {
                build job: 'Subtask_Openstack_Playbook',
                parameters: [
                    [$class: 'StringParameterValue', name: 'INVENTORY', value: 'acceptance'],
                    [$class: 'StringParameterValue', name: 'PLAYBOOK', value: 'deploy-citydynamics.yml'],
                ]
            }
        }
    }


    stage('Waiting for approval') {
        slackSend channel: '#ci-channel', color: 'warning', message: 'City dynamics is waiting for Production Release - please confirm'
        input "Deploy to Production?"
    }

    node {
        stage('Push production image') {
            tryStep "image tagging", {
                def kibana = docker.image("build.datapunt.amsterdam.nl:5000/datapunt/city_dynamics:${env.BUILD_NUMBER}")
                kibana.pull()
                kibana.push("production")
                kibana.push("latest")
            }
        }
    }

    node {
        stage("Deploy") {
            tryStep "deployment", {
                build job: 'Subtask_Openstack_Playbook',
                parameters: [
                        [$class: 'StringParameterValue', name: 'INVENTORY', value: 'production'],
                        [$class: 'StringParameterValue', name: 'PLAYBOOK', value: 'deploy-citydynamics.yml'],
                ]
            }
        }
    }
}
