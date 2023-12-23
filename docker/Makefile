
DOCKER = docker
DOCKER_NETWORK_NAME = docker_cs_network
DOCKER_CONTAINER_NAME = client server monitor

build:
	docker-compose up -d
	docker restart $(DOCKER_CONTAINER_NAME)


clean:
	docker stop $(DOCKER_CONTAINER_NAME) && docker rm $(DOCKER_CONTAINER_NAME)
	docker network rm $(DOCKER_NETWORK_NAME)