FROM jenkins/jenkins:lts-jdk17

ARG JENKINS_INSTALL_PLUGINS=false

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      python3 \
      python3-pip \
      python3-venv \
      tar \
    && ln -sf /usr/bin/python3 /usr/local/bin/python \
    && rm -rf /var/lib/apt/lists/*

USER jenkins

RUN if [ "${JENKINS_INSTALL_PLUGINS}" = "true" ]; then \
      jenkins-plugin-cli --plugins \
        git \
        allure-jenkins-plugin \
        branch-api \
        cloudbees-folder \
        locale \
        matrix-auth \
        matrix-project \
        workflow-aggregator \
        workflow-multibranch; \
    else \
      jenkins-plugin-cli --plugins locale; \
    fi
