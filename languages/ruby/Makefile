.PHONY: rust install test lint typecheck repl

rust:
	$(MAKE) -C ../.. rust-build

install:
	bundle install

test: install rust
	POLAR_IGNORE_NO_ALLOW_WARNING=1 bundle exec rake spec

lint: install
	bundle exec rubocop

typecheck: install
	bundle exec solargraph typecheck

repl: install rust
	bundle exec oso
