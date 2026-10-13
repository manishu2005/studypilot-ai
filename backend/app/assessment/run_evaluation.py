from __future__ import annotations

import argparse
import json
from pathlib import Path
from app.assessment.evaluation import evaluate_dataset, evaluate_live_retrieval_case, save_report

def main()->int:
    parser = argparse.ArgumentParser(description="Run StudyPilot AI offline evaluation.")
    parser.add_argument("--mode", choices=("answer", "retrieval"), default="answer")
    parser.add_argument("--dataset", default="evaluation/test_cases.json")
    parser.add_argument("--output", default="evaluation/report.json")
    args=parser.parse_args()
    dataset_path = Path(args.dataset)
    if args.mode == "answers":
        report = evaluate_dataset(dataset_path)
    else:
        from app.service import get_study_service

        with dataset_path.open("r", encoding="utf-8") as file:
            cases = json.load(file)

        if not isinstance(cases, list):
            raise ValueError("Retrieval dataset must be a JSON array.")

        service = get_study_service()
        results = [
            evaluate_live_retrieval_case(service, case)
            for case in cases
        ]
        passed = sum(1 for item in results if item["passed"])

        report = {
            "dataset": dataset_path.name,
            "mode": "live_retrieval",
            "total_cases": len(results),
            "passed_cases": passed,
            "failed_cases": len(results) - passed,
            "pass_rate": round(
                passed / len(results) if results else 0.0,
                4,
            ),
            "results": results,
            "limitations": [
                "Retrieval labels are only as reliable as the supplied labels.",
                "Expected-term coverage is lexical, not semantic recall.",
            ],
        }

    save_report(report, args.output)

    print(f"Mode: {args.mode}")
    print(f"Total cases: {report['total_cases']}")
    print(f"Passed: {report['passed_cases']}")
    print(f"Failed: {report['failed_cases']}")
    print(f"Pass rate: {report['pass_rate']:.1%}")
    print(f"Report saved to: {args.output}")

    return 0 if report["failed_cases"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
