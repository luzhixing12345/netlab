
.PHONY: init release

init:
	docker cp src/code/client.py client:/root
	docker cp src/code/config.py client:/root
	docker cp src/code/server.py server:/root
	docker cp src/code/config.py server:/root
	docker cp src/chunk_generator.py server:/root
	docker cp docker/tmux.sh monitor:/etc/

update:
	docker cp src/code/client.py client:/root
	docker cp src/code/config.py client:/root
	docker cp src/code/server.py server:/root
	docker cp src/code/config.py server:/root

restart:
	docker restart client server monitor
	docker exec -it client /usr/sbin/sshd
	docker exec -it server /usr/sbin/sshd
	docker exec -it monitor /usr/sbin/sshd

ssh:
	docker exec -it client /usr/sbin/sshd
	docker exec -it server /usr/sbin/sshd
	docker exec -it monitor /usr/sbin/sshd

test:
	docker cp src/GetScore.py monitor:/root
	docker cp src/code/run.json monitor:/root
	docker cp src/code/client.py monitor:/root
	docker cp src/code/config.py monitor:/root
	docker cp src/code/server.py monitor:/root
	docker cp src/chunk_generator.py monitor:/root

SERVER = micro:~/
CLIENT = test:~/

scp:
	scp src/code/client.py $(CLIENT)
	scp src/code/server.py $(SERVER)
	scp src/chunk_generator.py $(SERVER)
	scp src/code/config.py $(CLIENT)
	scp src/code/config.py $(SERVER)

run:
	docker exec -it monitor sh /etc/tmux.sh


ID = 23023xxx