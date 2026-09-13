@Library('jenkins_pipeline_libs') _

pipeline {
    options {
        buildDiscarder(logRotator(numToKeepStr: '5'))
        timestamps()
        skipDefaultCheckout(true)
    }

    agent {
        docker {
            // ROS 2 Jazzy / Ubuntu 24.04 ARM64 构建环境
            image '10.51.33.201:30002/navi_project/orin_jazzy_base:1.0.0'
            label 'arm64-8-99'
            args '-u root --network=host --entrypoint=""'
        }
    }

    parameters {
        choice(name: 'BUILD_SOURCE', choices: ['BRANCH', 'TAG'], description: '选择构建来源类型')
        gitParameter(name: 'BRANCH', type: 'PT_BRANCH', branchFilter: 'origin/(.*)',
                     defaultValue: 'dev/jenkins', description: '选择构建分支',
                     quickFilterEnabled: true, sortMode: 'DESCENDING_SMART')
        gitParameter(name: 'TAG', type: 'PT_TAG', defaultValue: '', description: '选择构建 Tag（如需要）',
                     tagFilter: '*', sortMode: 'DESCENDING_SMART')
        choice(name: 'IS_PREJECT_NOTIFY', choices: ['False', 'True'], description: '是否进行飞书 hook 推送')
        choice(name: 'IS_BUILD_DOCKER_IMAGE', choices: ['False', 'True'], description: '是否构建 Docker 镜像')
    }

    environment {
        GITLAB_CREDS = 'gitlab_zhangjunjie'
        PACKAGE_NAME = 'media_play'
        ROS_DISTRO = 'jazzy'
        BASE_VERSION = '2.0.0'
    }

    stages {
        stage('Get Branch') {
            steps { zjhGetBranch(env, true) }
        }

        stage('Checkout Code') {
            steps {
                figlet 'Checkout Code'
                dir('src/project') { zjhCheckoutCode(env) }
            }
        }

        stage('Colcon Build') {
            steps {
                figlet 'Colcon Build'
                sh '''#!/bin/bash
                    set -euo pipefail
                    source /opt/ros/${ROS_DISTRO}/setup.bash
                    colcon build --base-paths "$WORKSPACE/src/project/src" \\
                        --build-base "$WORKSPACE/build" \\
                        --install-base "$WORKSPACE/install" \\
                        --log-base "$WORKSPACE/log"
                '''
            }
        }

        stage('Build Deb') {
            steps {
                figlet 'Build Deb'
                sh '''#!/bin/bash
                    set -euo pipefail

                    project="$WORKSPACE/src/project"
                    dist="$project/dist"
                    rm -rf "$dist"
                    mkdir -p "$dist"

                    branch="${branchName:-${BRANCH:-unknown}}"
                    branch="${branch#origin/}"
                    safe_branch="$(printf '%s' "$branch" | tr -cd '[:alnum:].+-')"
                    [ -n "$safe_branch" ] || safe_branch=unknown
                    commit="$(git -C "$project" rev-parse --short=8 HEAD)"
                    version="${BASE_VERSION}-${safe_branch}+${BUILD_NUMBER}-${commit}noble"
                    architecture="$(dpkg --print-architecture)"

                    build_deb() {
                        local ros_package="$1"
                        local deb_package="$2"
                        local depends="$3"
                        local description="$4"
                        local stage="$WORKSPACE/pkg_${ros_package}"
                        local install_root="$WORKSPACE/install/${ros_package}"

                        [ -d "$install_root" ] || { echo "Missing install tree: $install_root"; exit 1; }
                        rm -rf "$stage"
                        mkdir -p "$stage/DEBIAN" "$stage/opt/ros/${ROS_DISTRO}"
                        cp -a "$install_root/." "$stage/opt/ros/${ROS_DISTRO}/"
                        {
                            echo "Package: ${deb_package}"
                            echo "Version: ${version}"
                            echo "Architecture: ${architecture}"
                            echo 'Maintainer: ZJ Humanoid <dev@zj-humanoid.com>'
                            [ -n "$depends" ] && echo "Depends: ${depends}"
                            echo "Description: ${description}"
                        } > "$stage/DEBIAN/control"
                        dpkg-deb --build "$stage" "$dist/${deb_package}_${version}_${architecture}.deb"
                    }

                    build_deb media_play_msgs zj-humanoid-ros-jazzy-media-play-msgs '' \\
                        'ROS 2 interfaces for media_play'
                    build_deb media_play zj-humanoid-ros-jazzy-media-play \\
                        'zj-humanoid-ros-jazzy-media-play-msgs, mpv, python3-yaml' \\
                        'ROS 2 video playback, subtitle and upload service'

                    ls -lh "$dist"
                '''
            }
        }

        stage('Archive') {
            steps {
                sh 'fs_upload --package=${PACKAGE_NAME} --src=src/project/dist'
            }
        }

        stage('Clean Workspace') {
            steps { cleanWs() }
        }
    }
}
