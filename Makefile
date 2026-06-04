.PHONY: install ingest service post poll draft test

install:
	pip install -r requirements.txt

# Stage A: read the New Company channel, qualify, notify good leads.
ingest:
	set -a && . ./.env && set +a && python -m scripts.slack_leads_reader

# Stage B for one lead: make service LEAD=<lead_id>
service:
	set -a && . ./.env && set +a && python -m scripts.service_lead --lead $(LEAD)

# Stage C (post): post variations for one lead. make post LEAD=<lead_id>
post:
	set -a && . ./.env && set +a && python -m scripts.slack_post_variations --lead $(LEAD)

# Stage C (pick): read reactions and create Gmail drafts for picks.
poll:
	set -a && . ./.env && set +a && python -m scripts.poll_picks

# Create the Gmail draft directly. make draft LEAD=<lead_id> VARIANT=<n>
draft:
	set -a && . ./.env && set +a && python -m scripts.gmail_draft --lead $(LEAD) --variant $(VARIANT)

test:
	pytest -q
