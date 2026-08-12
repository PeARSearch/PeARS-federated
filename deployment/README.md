# PeARS-Federated Deployment Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
   - [Creating a Server](#creating-a-server)
     - [Hetzner](#hetzner)
     - [Scaleway](#scaleway)
   - [Deploying Docker and Docker Compose](#deploying-docker-and-docker-compose)
2. [Deployment](#deploying-pears-dedicated)
   - [Deploying your first PeARS-dedicated pod](#deploying-your-first-pears-dedicated-pod)
   - [Adding more pods to your deployment](#adding-more-pods-to-the-same-server)
3. [Management](#management)
   - [Backing Up Data](#backing-up-data)

## Prerequisites

### Creating a Server

To deploy PeARS-federated pod, you need to start by creating a server. Below are instructions for creating a server on Hetzner and Scaleway.

#### Hetzner

1. Visit [Hetzner](https://www.hetzner.com/cloud).
2. Create an account and log in.
3. Follow the [Hetzner Cloud Quickstart Guide](https://docs.hetzner.com/cloud/getting-started/quickstart/) to create a new server.

#### Scaleway

1. Visit [Scaleway](https://www.scaleway.com/).
2. Create an account and log in.
3. Follow the [Scaleway Getting Started Guide](https://www.scaleway.com/en/docs/compute/instances/quickstart/) to create a new server.

### Deploying Docker and Docker Compose

The following instructions are for Ubuntu. For other distributions, refer to the [official Docker documentation](https://docs.docker.com/engine/install/).

1. SSH into your server.
2. Install necessary packages and Docker:
    ```bash
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gettext vim
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    ```

## Deploying PeARS-dedicated


### Deploying your first PeARS-dedicated pod
---

- **SSH into your server**

- **Set the domain name and pod specific directory name**
    ```
    export DOMAIN=pears-pod-url.com # Provide the URL on which you want to reach your pears-federated pod
    export PEARS_DIR=~/pears-pod-name-1 # replace `pears-pod-name-1` with the name of your pod for ease of identification
    export STAGE=production # replace this with `staging` if you are just testing the setup, otherwise it will create a TLS certificate for you
    ```

- **Download the Docker-compose file and setup base directory for your pod**

    1. Download the `docker-compose.yml` from the Github repository to the base of your server:
        ```bash
        wget https://raw.githubusercontent.com/PeARSearch/PeARS-federated/nvn/add-deploy-files/deployment/docker-compose.yaml -O template.yaml
        ```
    2. Use the above variables in the docker-compose file
       ```
       envsubst < template.yaml > docker-compose.yaml
       rm -rf template.yaml
       ```
    2. Create a directory to store your instance details and to store persistent data for the instance:
        ```bash
        mkdir -p ${PEARS_DIR}/data
        ```

- **Configure the environmental details for your pod**
    1. Download the `env-template` files from the GitHub repository:
        ```bash
        wget https://raw.githubusercontent.com/PeARSearch/PeARS-federated/nvn/add-deploy-files/deployment/.env-template -O ${PEARS_DIR}/.env
        ```
    2. Update the values in the `.env` file to match your configuration ( Follow the instructions in the .env file to fill in the data):
        ```bash
        vim ${PEARS_DIR}/.env
        ```

- **Bring Up the Docker Compose**

    > This command assumes that you are running this command from the directory in which the `docker-compose.yaml` file exists

    1. Start the Docker Compose services:
        ```bash
        docker compose up -d
        ```

- **Point your DNS to the IP address of the server**

    Make sure you create an A name record pointing from your PeARS URL to the public IP address of the server




### Adding more pods to the same server
---


If you want to host another pod on the same server, we will have to re-use the same docker-compose file by adding new pod configurations and re-using the `https-portal` container that you will find in the `docker-compose` file to point to differnt pods for different domain names. Here are the step by step details for doing that:

> We assume you have already followed the above steps and have a single pod running already at this point

1. Create a new directory for the new pod and download the environment variable file
    ```bash
    export PEARS_DIR_2=~/pears-pod-name-2 # replace pears-pod-name-2 with your new pod name
    mkdir -p ${PEARS_DIR_2}/data 
    # You can also copy this file from your existing pod directory for ease of editing
    wget https://raw.githubusercontent.com/PeARSearch/PeARS-federated/nvn/add-deploy-files/deployment/.env-template -O ${PEARS_DIR_2}/.env
    ```
2. Change the environment details in the `.env` file:
    ```bash
    vim ${PEARS_DIR_2}/.env
    ```
3. Update the docker-compose to also bring up the second pod
   
   If you open your `docker-compose.yaml` file in the server at this point, you will find something like this:
   ```
   $ cat docker-compose.yaml

    version: '3.8'

    services:
        pears-federated:
            env_file:
            - pears-pod-name-1/.env
            image: pearsproject/pears-federated:latest
            volumes:
            - pears-pod-name-1/data/:/var/lib/pears/data

        https-portal:
            image: steveltn/https-portal:1
            environment:
            DOMAINS: 'pears-pod-url.com -> http://pears-federated:8000'
            STAGE: production
            ports:
            - "80:80"
            - "443:443"
            depends_on:
            - pears-federated
            volumes:
            - https-portal-data:/var/lib/https-portal
    ```

4. To add another pod, you will have to first copy the `pears-federed` container definition to a new definition in the file with appropriate names as follows:
    ```
    $ vim docker-compose.yaml

    version: '3.8'

    services:
        pears-federated: # if you want you can also rename this to have a more identifiable name
            env_file:
            - pears-pod-name-1/.env
            image: pearsproject/pears-federated:latest
            volumes:
            - pears-pod-name-1/data/:/var/lib/pears/data

        pears-federated-pod-2: # !! CHANGE rename this to have a more identifiable suffix
            env_file:
            - pears-pod-name-2/.env # !! CHANGE point to your new directory pears-pod-name-2
            image: pearsproject/pears-federated:latest
            volumes:
            - pears-pod-name-2/data/:/var/lib/pears/data # !! CHANGE point to your new directory pears-pod-name-2
        ...

    ```

5. Update `https-portal` pod to point to the new pod as well
    ```
    $ vim docker-compose.yaml

    version: '3.8'

    services:
        pears-federated:
            env_file:
            - pears-pod-name-1/.env
            image: pearsproject/pears-federated:latest
            volumes:
            - pears-pod-name-1/data/:/var/lib/pears/data

        pears-federated-pod-2:
            env_file:
            - pears-pod-name-2/.env
            image: pearsproject/pears-federated:latest
            volumes:
            - pears-pod-name-2/data/:/var/lib/pears/data

        https-portal:
            image: steveltn/https-portal:1
            environment:
                # !! CHANGE: point the URL you want to point to your new pod to the http://<name-of-the-new-pod-in-this-file>:8000
                # You use a comma to separate the entries; this can support any number of mappings
                DOMAINS: 'pears-pod-url.com -> http://pears-federated:8000, pears-pod-2-url.com -> http://pears-federated-pod-2:8000'
                STAGE: production
            ports:
            - "80:80"
            - "443:443"
            depends_on:
            - pears-federated
            - pears-federated-pod-2 # !! CHANGE: notice that it is not depending on the new pod as well
            volumes:
            - https-portal-data:/var/lib/https-portal
    ```

6. Bring Up the Docker Compose

    > This command assumes that you are running this command from the directory in which the `docker-compose.yaml` file exists

    1. Start the Docker Compose services:
        ```bash
        docker compose up -d
        ```
    2. Check the new pod is running by running the command:
        ```bash
        docker ps
        ```

7. Point your DNS to the IP address of the server

    Make sure you create an A name record pointing from your new PeARS URL to the public IP address of the server


> If you want to add a third pod, you can continue the same steps as above but for a third entry


## Management

### Backing Up Data

To avoid loss of data, regularly back up the `data` folder:

1. Create a backup directory:
    ```bash
    mkdir -p ~/pears-federated-backups
    ```
2. Copy the data directory to the backup directory:
    ```bash
    cp -r ~/pears-pod-name-1/data ~/pears-federated-backups/data_backup_$(date +%Y%m%d%H%M%S)
    ```

Regularly schedule this backup process using a cron job or other automation tools to ensure your data is safe. You can setup configurations to upload these directory to a remote cloud storage for maximum security.

