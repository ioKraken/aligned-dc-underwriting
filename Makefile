# One-command Phase 2 rebuild. Requires populated data_raw/deal_universe_raw.csv (see README).
PY ?= python3

phase2: dictionary collect stage2 validate audit

collect:
	$(PY) src/01_collect.py
stage2:
	$(PY) src/02b_build_stage2.py
validate:
	$(PY) src/02_validate_raw.py
audit:
	$(PY) src/02c_coverage_audit.py
dictionary:
	$(PY) src/data_dictionary_spec.py
test:
	$(PY) src/tests/test_pipeline.py

phase3-prep:
	$(PY) src/03a_prepare_coding.py
phase3-agree:
	$(PY) src/03b_agreement_adjudicate.py
phase3-nlp:
	$(PY) src/03c_nlp_screen.py
phase3-final:
	$(PY) src/03d_finalize.py
phase3-audit:
	$(PY) src/03d_finalize.py --make-audit
phase3-freeze:
	$(PY) src/03d_finalize.py --freeze
phase3-verify:
	$(PY) src/03d_finalize.py --verify-freeze
test3:
	$(PY) src/tests/test_phase3.py

phase4:
	$(PY) src/04_descriptives.py
test4:
	$(PY) src/tests/test_phase4.py

workbook:
	$(PY) src/00_excel_workbook.py --build
import-excel:
	$(PY) src/00_excel_workbook.py --import $(FILE)

.PHONY: workbook import-excel phase4 test4 phase3-prep phase3-agree phase3-nlp phase3-final phase3-audit phase3-freeze phase3-verify test3 phase2 collect stage2 validate audit dictionary test

phase5:
	$(PY) src/05_regressions.py
phase6:
	$(PY) src/06_matching.py && $(PY) src/07_robustness.py
phase7:
	$(PY) src/08_interpretation.py
test567:
	$(PY) src/tests/test_phase567.py
.PHONY: phase5 phase6 phase7 test567
