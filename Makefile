.PHONY: dev web build-frontend test test-backend test-frontend lint-frontend check

# Development mode: start both backend and frontend dev servers
dev:
	python main.py dev

# Production mode: build frontend and start server
web: build-frontend
	python main.py web

# Build frontend for production
build-frontend:
	cd web/frontend && npm run build

test: test-backend test-frontend

test-backend:
	uv run pytest -q

test-frontend:
	cd web/frontend && npm test

lint-frontend:
	cd web/frontend && npm run lint

check: test lint-frontend build-frontend
