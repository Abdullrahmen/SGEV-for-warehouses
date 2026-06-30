.PHONY: start stop migrate seed logs daphne listener react docker infra clean

VENV = venv
PYTHON = $(VENV)/bin/python

start: ## Start everything
	@./start.sh

stop: ## Stop all background processes
	@./stop.sh

infra: ## Start Docker services
	docker compose up -d
	@echo "Waiting for PostgreSQL..."
	@sleep 3

daphne: ## Start ASGI server
	@$(PYTHON) -m daphne -b 0.0.0.0 -p 8000 warehouse_project.asgi:application

listener: ## Start MQTT Listener
	@$(PYTHON) manage.py run_mqtt_listener

react: ## Start React dev server
	@cd frontend && npm run dev

migrate: ## Run database migrations
	@$(PYTHON) manage.py migrate

seed: ## Seed demo data
	@$(PYTHON) manage.py seed_demo_data

logs: ## Tail all logs
	@tail -f logs/*.log

clean: ## Remove venv, pids, logs
	rm -rf $(VENV) .pids logs
	rm -f frontend/node_modules

docker-down: ## Stop Docker services
	docker compose down
