
.PHONY: init

rsync:
	docker cp src/code/client.py client:/root
	docker cp src/code/config.py client:/root
	docker cp src/code/server.py server:/root
	docker cp src/code/config.py server:/root
	docker cp docker/tmux.sh monitor:/etc/
	

run:
	docker exec -it monitor sh /etc/tmux.sh