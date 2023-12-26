
.PHONY: init

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

run:
	docker exec -it monitor sh /etc/tmux.sh