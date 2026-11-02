.PHONY: up down logs seed eval test
up:        ; docker compose up -d --build
down:      ; docker compose down
logs:      ; docker compose logs -f api worker
seed:      ; docker compose exec api python -m scripts.seed
eval:      ; docker compose exec api python -m eval.run_eval
test:      ; cd backend && pytest -q
