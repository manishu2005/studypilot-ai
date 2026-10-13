from __future__ import annotations
import argparse
import json
from pathlib import Path
from app.personalization.personalization_evaluation import evaluate_personalization

def main()->None:
    parser = argparse.ArgumentParser(description="Evaluate StudyPilot AI personalization.")
    parser.add_argument("--dataset", default="evaluation/personalization_cases.json")
    parser.add_argument("--output", default="evaluation/personalization_report.json")

    args = parser.parse_args()
    dataset_path = Path(args.dataset)
    output_path = Path(args.output)
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path.resolve()}"
        )

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))

    report = evaluate_personalization(
        difficulty_records=dataset["difficulty_records"],
        topic_mastery=dataset["topic_mastery"],
        recommended_topics=dataset["recommended_topics"],
        questions=dataset["questions"],
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReport saved to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
