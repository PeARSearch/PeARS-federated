FROM python:3.11-slim

# Avoid warnings by switching to noninteractive
ENV DEBIAN_FRONTEND=noninteractive

# Install Docker
RUN apt-get update \
    && apt-get -y install --no-install-recommends apt-utils dialog 2>&1 \
    && apt-get -y install git procps lsb-release wget build-essential \
    ca-certificates curl gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

# Switch back to dialog for any ad-hoc use of apt
ENV DEBIAN_FRONTEND=dialog

# Set up Python environment
RUN python -m pip install --upgrade pip \
    && python -m pip install pylint pytest black mypy isort

# Create a non-root user to use if preferred - see https://aka.ms/vscode-remote/containers/non-root-user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Create the user
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME \
    # Add sudo support
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    # Add Docker group membership
    && groupadd -f docker \
    && usermod -aG docker $USERNAME \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

# Create Python tool folder and link common tools
ENV PIPX_HOME=/usr/local/py-utils
ENV PIPX_BIN_DIR=${PIPX_HOME}/bin
ENV PATH=${PATH}:${PIPX_BIN_DIR}

RUN mkdir -p ${PIPX_BIN_DIR} \
    && ln -s /usr/local/bin/pylint ${PIPX_BIN_DIR}/pylint \
    && ln -s /usr/local/bin/pytest ${PIPX_BIN_DIR}/pytest \
    && ln -s /usr/local/bin/black ${PIPX_BIN_DIR}/black \
    && ln -s /usr/local/bin/mypy ${PIPX_BIN_DIR}/mypy \
    && ln -s /usr/local/bin/isort ${PIPX_BIN_DIR}/isort

# Set the default user
USER $USERNAME

# Set a default workspace directory
WORKDIR /workspace