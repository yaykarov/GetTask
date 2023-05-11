test:
	python -m pytest -vv the_redhuman_is/tests/test_talk_bank.py
test-coverage:
	python -m pytest --cov=the_redhuman_is/tests/test_talk_bank.py
lint:
	python -m flake8 the_redhuman_is/async_utils/talk_bank

.PHONY: test test-coverage lint