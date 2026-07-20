"""[3] Markdown 렌더러: minutes.json → Markdown 문자열."""
import sys

from validate import load_minutes


def render_markdown(data: dict) -> str:
    lines = [f"# {data['title']}", ""]
    if data.get("date"):
        lines.append(f"**일시:** {data['date']}")
        lines.append("")

    lines.append("## 참석자")
    if data["attendees"]:
        lines.extend(f"- {a}" for a in data["attendees"])
    else:
        lines.append("- (없음)")
    lines.append("")

    lines.append("## 논의 내용")
    if data["discussion"]:
        for item in data["discussion"]:
            lines.append(f"### {item['topic']}")
            lines.extend(f"- {p}" for p in item["points"])
            lines.append("")
    else:
        lines.append("(없음)")
        lines.append("")

    lines.append("## 결정 사항")
    if data["decisions"]:
        lines.extend(f"- {d}" for d in data["decisions"])
    else:
        lines.append("- (없음)")
    lines.append("")

    lines.append("## Action Items")
    if data["action_items"]:
        lines.append("| 할 일 | 담당자 | 기한 |")
        lines.append("| --- | --- | --- |")
        for a in data["action_items"]:
            owner = a["owner"] or "-"
            due = a["due"] or "-"
            lines.append(f"| {a['task']} | {owner} | {due} |")
    else:
        lines.append("(없음)")
    lines.append("")

    lines.append("## 다음 회의 일정")
    lines.append(data["next_meeting"] or "(미정)")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    json_path, out_path = sys.argv[1], sys.argv[2]
    data = load_minutes(json_path)
    md = render_markdown(data)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Markdown 생성 완료: {out_path}")


if __name__ == "__main__":
    main()
