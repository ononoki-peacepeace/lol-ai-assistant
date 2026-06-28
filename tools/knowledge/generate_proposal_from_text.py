import argparse
import json
import os
import re
import sys
from pathlib import Path

from jsonschema import Draft7Validator
from openai import OpenAI
import csv
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = PROJECT_ROOT / "configs" / "llm_config.json"
SCHEMA_DIR = PROJECT_ROOT / "knowledge" / "schemas"
PROPOSAL_DIR = PROJECT_ROOT / "knowledge" / "proposals"
ROOT_DIR = Path(__file__).resolve().parents[2]
GENERATE_SCRIPT = ROOT_DIR / "tools" / "knowledge" / "generate_proposal_from_sources.py"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config  # noqa: F401


KIND_CONFIG = {
    "counters": {
        "schema": "counters.schema.json",
        "proposal": "counters_candidates.json",
        "description": "英雄克制关系 counter_relation",
    },
    "strength": {
        "schema": "champion_strength.schema.json",
        "proposal": "champion_strength_candidates.json",
        "description": "英雄强度 champion_strength",
    },
    "team_combo": {
        "schema": "team_combo.schema.json",
        "proposal": "team_combo_candidates.json",
        "description": "二人/多人阵容配合 team_combo",
    },
}


def load_json(path: Path, default=None):
    if default is None:
        default = {}

    if not path.exists():
        return default

    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_text_from_file(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix in [".txt", ".md", ".log"]:
        return path.read_text(encoding="utf-8-sig")

    if suffix == ".json":
        data = load_json(path)
        return json.dumps(data, ensure_ascii=False, indent=2)

    if suffix == ".csv":
        lines = []
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                lines.append("\t".join(row))
        return "\n".join(lines)

    if suffix in [".html", ".htm"]:
        html = path.read_text(encoding="utf-8-sig")
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style"]):
            tag.decompose()

        return soup.get_text("\n", strip=True)

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise RuntimeError("读取 PDF 需要安装 pypdf：python -m pip install pypdf")

        reader = PdfReader(str(path))
        texts = []

        for page in reader.pages:
            text = page.extract_text() or ""
            texts.append(text)

        return "\n".join(texts)

    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError:
            raise RuntimeError("读取 docx 需要安装 python-docx：python -m pip install python-docx")

        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)

    if suffix in [".xlsx", ".xls"]:
        try:
            import pandas as pd
        except ImportError:
            raise RuntimeError("读取 Excel 需要安装 pandas/openpyxl：python -m pip install pandas openpyxl")

        sheets = pd.read_excel(path, sheet_name=None)
        parts = []

        for sheet_name, df in sheets.items():
            parts.append(f"===== Sheet: {sheet_name} =====")
            parts.append(df.to_csv(index=False))

        return "\n".join(parts)

    raise ValueError(f"暂不支持的文件格式：{suffix}")


def read_text_from_args(args) -> str:
    if args.text:
        return args.text.strip()

    if args.file:
        path = Path(args.file)

        if not path.exists():
            raise FileNotFoundError(f"找不到输入文件：{path}")

        return extract_text_from_file(path).strip()

    raise ValueError("必须提供 --text 或 --file")


def extract_json_array(text: str):
    text = text.strip()

    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")

        if start == -1 or end == -1 or end <= start:
            raise

        data = json.loads(text[start:end + 1])

    if not isinstance(data, list):
        raise ValueError("AI 输出必须是 JSON 数组，最外层必须是 []")

    return data


def validate_data(data, schema_path: Path):
    schema = load_json(schema_path)
    validator = Draft7Validator(schema)

    errors = sorted(
        validator.iter_errors(data),
        key=lambda e: list(e.path)
    )

    if not errors:
        return True, []

    formatted = []
    for error in errors:
        path = "$"
        for part in error.path:
            if isinstance(part, int):
                path += f"[{part}]"
            else:
                path += f".{part}"

        formatted.append(f"{path}: {error.message}")

    return False, formatted


def build_extra_instruction(kind: str) -> str:
    if kind == "counters":
        return """
当前抽取类型：counter_relation

你需要抽取：
- X 好打 Y
- X 难打 Y
- X 克制 Y
- X 被 Y 克制
- X 对线 Y 难受
- X 面对 Y 有风险

判断规则：
1. 如果文本表达「A 好打 B / A 克制 B」，输出 candidate=A, target=B, direction=good_against。
2. 如果文本表达「A 难打 B / A 被 B 克制」，输出 candidate=A, target=B, direction=bad_against。
3. 如果文本说「亚索对线小法打不过」，可以理解为 Yasuo bad_against Veigar，或者 Veigar good_against Yasuo，优先输出更清晰的一条。
4. 单条玩家评论 confidence 必须是 low。
5. 如果只是骂玩家操作差，不要强行当成英雄克制；除非文本明确提到对线英雄关系。
""".strip()

    if kind == "strength":
        return """
当前抽取类型：champion_strength

你需要抽取：
- 某英雄某位置强
- 某英雄某位置弱
- 某英雄对线压力大
- 某英雄后期强
- 某英雄低分段/高分段强
- 某英雄版本热门

判断规则：
1. 单条玩家评论只能作为 subjective_strength，confidence 必须是 low。
2. 如果文本只是说某个玩家菜，不要当成英雄弱。
3. 如果文本说某英雄「难打、压制力强、前期猛、后期强」，可以生成 champion_strength。
4. 不要编造胜率、登场率、版本号、段位。
""".strip()

    if kind == "team_combo":
        return """
当前抽取类型：team_combo

你需要抽取：
- 两个英雄配合
- 三个英雄配合
- 四个英雄配合
- 五人阵容体系
- 强开体系、保护体系、poke体系、冲阵体系、正面团体系

判断规则：
1. 二人配合也属于 team_combo。
2. 如果文本只提到一个英雄，不要生成 team_combo。
3. 如果文本提到「发条配石头人」「卢锡安娜美」「霞洛」「青钢影加里奥」这类组合，可以生成 team_combo。
4. 单条玩家评论 confidence 通常是 low；攻略/数据/职业资料可以 medium 或 high。
""".strip()

    return ""


def build_prompt(kind: str, schema: dict, source_text: str) -> str:
    kind_desc = KIND_CONFIG[kind]["description"]
    extra_instruction = build_extra_instruction(kind)

    return f"""
你是一个英雄联盟 BP 知识库信息抽取器。

你的任务：
从用户提供的原始文本中，抽取和「{kind_desc}」有关的信息，并严格按照给定 JSON Schema 输出候选 JSON。

重要规则：
1. 只输出 JSON 数组，不要输出解释、Markdown、代码块。
2. 如果文本没有足够信息，输出 []。
3. 不要编造胜率、样本量、版本号、段位。
4. 如果文本只有主观评价，confidence 通常用 low。
5. 如果是论坛/评论/玩家观点，source_type 用 forum_text 或 manual_text。
6. raw_evidence 必须放原文中的关键证据句。
7. reason 用中文解释你为什么这样抽取。
8. 英雄 ID 使用英文 Riot/DataDragon 风格，例如 Darius、Malphite、MonkeyKing、Kaisa、JarvanIV、Veigar。
9. 位置只允许：上单、打野、中单、下路、辅助、unknown。
10. score 必须按 schema 范围填写。
11. 每条候选都必须包含 review_status 字段，默认值为 "pending"。
12. 可以理解口语化、情绪化、论坛化表达，但不能把纯玩家操作问题强行当成英雄知识。
13. 如果只能得到很弱的主观信息，也可以生成低置信度候选，不要过度保守。
14. 每次最多输出 3 条候选。
15. raw_evidence 每条尽量不超过 80 字。
16. reason 尽量不超过 80 字。
17. evidence 里没有明确数字就填 null，不要编造。

{extra_instruction}

JSON Schema：
{json.dumps(schema, ensure_ascii=False, indent=2)}

原始文本：
{source_text}
""".strip()


def call_llm(prompt: str) -> str:
    import json
    import os
    from pathlib import Path

    root_dir = Path(__file__).resolve().parents[2]
    config_path = root_dir / "configs" / "llm_config.json"

    with open(config_path, "r", encoding="utf-8-sig") as f:
        config = json.load(f)

    provider = config.get("provider", "openai_compatible")
    model = config.get("model", "deepseek-v4-flash")
    temperature = float(config.get("temperature", 0.2))
    max_tokens = int(config.get("max_tokens", 2000))

    if provider == "ollama":
        return call_ollama(
            prompt=prompt,
            model=model,
            host=config.get("host", "http://127.0.0.1:11434"),
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider == "openai_compatible":
        return call_openai_compatible(
            prompt=prompt,
            model=model,
            base_url=config.get("base_url", "https://api.deepseek.com"),
            api_key_env=config.get("api_key_env", "DEEPSEEK_API_KEY"),
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise ValueError(f"不支持的 LLM provider: {provider}")


def call_ollama(
    prompt: str,
    model: str,
    host: str,
    temperature: float,
    max_tokens: int,
) -> str:
    from ollama import Client

    client = Client(host=host)

    response = client.chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "你是严格的 JSON 生成器。只输出合法 JSON，不要输出 Markdown，不要解释。",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        options={
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    )

    return response["message"]["content"]


def call_openai_compatible(
        prompt: str,
        model: str,
        base_url: str,
        api_key_env: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
    import os
    from openai import OpenAI

    api_key = os.getenv(api_key_env)

    if not api_key:
        raise RuntimeError(f"环境变量 {api_key_env} 没有设置。")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "你是严格的 JSON 生成器。只输出合法 JSON，不要输出 Markdown，不要解释。",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content

def normalize_items(items: list, kind: str):
    """
    给 AI 输出做一点兜底清洗：
    - 补 review_status=pending
    - 补 source_refs=[]
    """
    normalized = []

    for item in items:
        if not isinstance(item, dict):
            continue

        item.setdefault("review_status", "pending")
        item.setdefault("source_refs", [])

        normalized.append(item)

    return normalized


def append_to_proposal_file(proposal_path: Path, new_items: list):
    old_items = load_json(proposal_path, default=[])

    if not isinstance(old_items, list):
        raise ValueError(f"{proposal_path} 不是 JSON 数组。")

    existing_ids = {item.get("id") for item in old_items if isinstance(item, dict)}
    merged = old_items[:]
    added = 0

    for item in new_items:
        item_id = item.get("id")

        if item_id and item_id in existing_ids:
            print(f"[跳过] 已存在 id：{item_id}")
            continue

        merged.append(item)
        added += 1

        if item_id:
            existing_ids.add(item_id)

    save_json(proposal_path, merged)

    return added


def generate_for_kind(kind: str, source_text: str, dry_run: bool = False):
    kind_info = KIND_CONFIG[kind]
    schema_path = SCHEMA_DIR / kind_info["schema"]
    proposal_path = PROPOSAL_DIR / kind_info["proposal"]

    if not schema_path.exists():
        raise FileNotFoundError(f"找不到 schema：{schema_path}")

    schema = load_json(schema_path)
    prompt = build_prompt(kind, schema, source_text)

    print("\n" + "=" * 70)
    print(f"[生成] kind={kind}")
    print(f"[Schema] {schema_path.relative_to(PROJECT_ROOT)}")

    raw_output = call_llm(prompt)

    print("\n===== AI 原始输出 =====")
    print(raw_output)

    try:
        data = extract_json_array(raw_output)
    except Exception as e:
        print("\n[失败] AI 输出不是合法 JSON，跳过本类别。")
        print(f"[错误] {e}")
        return 0, False

    data = normalize_items(data, kind)

    ok, errors = validate_data(data, schema_path)
    if not ok:
        print("\n[失败] AI 输出不符合 schema：")
        for err in errors:
            print("-", err)
        return 0, False

    print(f"\n[通过] AI 输出 {len(data)} 条候选。")

    if dry_run:
        print("[dry-run] 不写入 proposals。")
        return len(data), True

    added = append_to_proposal_file(proposal_path, data)

    print(f"[写入] {proposal_path.relative_to(PROJECT_ROOT)}")
    print(f"[新增] {added} 条。")

    return added, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--kind",
        required=True,
        choices=["auto", *KIND_CONFIG.keys()],
        help="生成哪类候选：auto / counters / strength / team_combo"
    )
    parser.add_argument(
        "--text",
        help="直接输入一段文本"
    )
    parser.add_argument(
        "--file",
        help="从 txt 文件读取文本"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印 AI 结果，不写入 proposals"
    )

    args = parser.parse_args()

    source_text = read_text_from_args(args)

    if args.kind == "auto":
        total_added = 0
        all_ok = True

        print("[AUTO] 将对同一段文本分别抽取 counters / strength / team_combo。")

        for kind in KIND_CONFIG.keys():
            added, ok = generate_for_kind(
                kind=kind,
                source_text=source_text,
                dry_run=args.dry_run,
            )
            total_added += added

            if not ok:
                all_ok = False

        print("\n" + "=" * 70)
        print(f"[AUTO 完成] 总新增 {total_added} 条候选。")

        if not all_ok:
            print("[警告] 有部分类别生成失败，请查看上面的错误。")
            sys.exit(1)

        return

    generate_for_kind(
        kind=args.kind,
        source_text=source_text,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()