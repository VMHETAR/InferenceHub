.PHONY: benchmark compare test
benchmark:
	@echo "Running benchmark..."
	python3 scripts/benchmark.py
	@echo ""
	@echo "Running baseline comparison..."
	python3 scripts/compare_baselines.py
	@echo ""
	cp results/benchmark_*.json results/latest.json
	@echo "All done — see results/ for numbers"
test:
	python3 -m pytest tests/performance_tests.py -v || echo "Run benchmark first (scripts/benchmark.py) to generate results/"
compare:
	python3 scripts/compare_baselines.py
