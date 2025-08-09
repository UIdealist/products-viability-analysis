init-shell:
	devbox shell
	source .venv/bin/activate

run_consume:
	spark-submit src\bronze\consume.py